"""Router admin untuk panel kontrol multi-agent (UI: app/web/index.html,
disajikan di /admin). Endpoint di sini yang membuat kredensial channel bisa
dikelola dari UI, bukan cuma `.env`.

Webhook dispatch dinamis (sejak v0.4.5): create/update/delete/toggle agent
di sini LANGSUNG live -- `app/main.py` (`webhook_dispatch`) lookup agent
dari database per request webhook masuk, bukan dari daftar statis yang
dihitung sekali saat startup. Restart proses TIDAK diperlukan untuk operasi
CRUD agent apa pun. Restart hanya masih relevan untuk perubahan level
infra (`ADIT_AGENT_HOST`/`ADIT_AGENT_PORT`/`ADIT_AGENT_SECRET_KEY`, env var
murni, lihat TODO.md "Runtime settings").

Auth: kalau env var ADIT_AGENT_ADMIN_TOKEN diset, semua endpoint di sini
wajib header `Authorization: Bearer <token>`. Kalau BELUM diset, endpoint
tetap bisa diakses tanpa auth sama sekali -- cukup untuk coba-coba di
jaringan lokal terpercaya, tapi WAJIB diisi sebelum panel ini dibuka ke
jaringan yang tidak sepenuhnya dipercaya (lihat README.md/TODO.md).
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, Header, HTTPException

from . import store
from .channels import _PLATFORM_ADAPTERS, build_adapter  # reuse pemetaan & builder yang sama dipakai loader

import os

logger = logging.getLogger("adit-agent.api_admin")

router = APIRouter(prefix="/api/agents", tags=["admin"])

_WEBHOOK_PREFIX = {
    "synology_chat": "synology",
    "synology_bot": "synology",
    "telegram": "telegram",
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "agent"


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("ADIT_AGENT_ADMIN_TOKEN", "")
    if not expected:
        # Belum dikonfigurasi -- lihat catatan auth di docstring modul.
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Token admin tidak valid/hilang.")


def _record_to_public_dict(record: store.AgentRecord, *, include_creds: bool) -> dict:
    data = {
        "id": record.id,
        "platform": record.platform,
        "name": record.name,
        "active": record.active,
        "webhook_path": record.webhook_path,
        "created_at": record.created_at,
    }
    if include_creds:
        data["creds"] = record.creds
    return data


@router.get("", dependencies=[Depends(_require_admin)])
def list_agents() -> list[dict]:
    """Untuk grid dashboard -- sengaja TIDAK menyertakan kredensial, lihat
    GET /api/agents/{id} untuk itu."""
    try:
        records = store.list_agents()
    except store.SecretKeyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_record_to_public_dict(r, include_creds=False) for r in records]


@router.get("/{agent_id}", dependencies=[Depends(_require_admin)])
def get_agent(agent_id: str) -> dict:
    """Untuk panel detail/kredensial -- ini yang menyertakan kredensial asli,
    dipakai UI untuk mengisi field yang bisa di-toggle tampil/sembunyi."""
    try:
        record = store.get_agent(agent_id)
    except store.SecretKeyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Agent tidak ditemukan.")
    return _record_to_public_dict(record, include_creds=True)


@router.post("", dependencies=[Depends(_require_admin)], status_code=201)
def create_agent(body: dict) -> dict:
    """Body: {"platform": str, "name": str, "creds": dict, "active": bool?}.

    Pakai `dict` polos (bukan model pydantic) sengaja supaya field kredensial
    tetap fleksibel per platform tanpa perlu skema baru tiap ada channel baru
    -- validasi minimal cukup di level ini, validasi bentuk field per
    platform sebaiknya di frontend (lihat mockup: PLATFORMS.<key>.fields)."""
    platform = body.get("platform")
    name = (body.get("name") or "").strip()
    creds = body.get("creds") or {}
    active = bool(body.get("active", False))

    if platform not in _PLATFORM_ADAPTERS:
        raise HTTPException(
            status_code=400,
            detail=f"Platform '{platform}' tidak dikenal. Pilihan: {sorted(_PLATFORM_ADAPTERS)}.",
        )
    if not name:
        raise HTTPException(status_code=400, detail="Nama agent wajib diisi.")
    if not isinstance(creds, dict) or not creds:
        raise HTTPException(status_code=400, detail="Kredensial wajib diisi.")

    prefix = _WEBHOOK_PREFIX[platform]
    slug = _slugify(name)

    # webhook_path harus unik (constraint di store.py) -- coba slug polos
    # dulu, kalau bentrok tambahkan angka. Self-host, jumlah agent kecil,
    # jadi loop pendek ini cukup daripada minta user pilih path manual.
    for attempt in range(1, 6):
        candidate = f"/webhook/{prefix}/{slug}" if attempt == 1 else f"/webhook/{prefix}/{slug}-{attempt}"
        try:
            record = store.create_agent(
                platform=platform, name=name, creds=creds, webhook_path=candidate, active=active
            )
            break
        except ValueError:
            continue
        except store.SecretKeyMissing as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    else:
        raise HTTPException(
            status_code=409, detail="Gagal membuat webhook_path unik, coba nama lain."
        )

    return _record_to_public_dict(record, include_creds=True)


@router.patch("/{agent_id}", dependencies=[Depends(_require_admin)])
def update_agent(agent_id: str, body: dict) -> dict:
    """Body (semua opsional): {"name": str, "creds": dict, "active": bool}.
    `creds` di sini MENIMPA SELURUH dict lama (bukan merge per-key) --
    UI wajib mengirim semua field kredensial platform tsb tiap kali update,
    sesuai perilaku form di panel admin (semua field kredensial selalu
    tampil sekaligus di panel detail). Berlaku langsung -- lihat docstring
    modul soal webhook dispatch dinamis."""
    name = body.get("name")
    creds = body.get("creds")
    active = body.get("active")

    try:
        record = store.update_agent(
            agent_id,
            name=name.strip() if isinstance(name, str) else None,
            creds=creds if isinstance(creds, dict) else None,
            active=bool(active) if active is not None else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent tidak ditemukan.") from exc
    except store.SecretKeyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _record_to_public_dict(record, include_creds=True)


@router.delete("/{agent_id}", dependencies=[Depends(_require_admin)], status_code=204)
def delete_agent(agent_id: str) -> None:
    try:
        if store.get_agent(agent_id) is None:
            raise HTTPException(status_code=404, detail="Agent tidak ditemukan.")
    except store.SecretKeyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.delete_agent(agent_id)


@router.post("/{agent_id}/test", dependencies=[Depends(_require_admin)])
async def test_agent_connection(agent_id: str) -> dict:
    """Bangun adapter SEMENTARA (tidak disimpan lagi, cuma dipakai sekali
    untuk tes ini) dari kredensial yang sudah tersimpan, lalu panggil
    test_connection() -- lihat SynologyAdapter.test_connection(). Pakai
    `build_adapter()` yang sama dipakai `webhook_dispatch` (app/main.py) --
    PENTING supaya `platform` ikut diteruskan (bukan diinstansiasi manual di
    sini), karena itu yang memicu override `reply_to_user=True` untuk
    `synology_bot` (lihat _FORCE_REPLY_TO_USER di app/channels/synology.py).
    Melewatkan ini di endpoint tes berarti tes koneksi bisa "berhasil"
    padahal pesan sungguhan tetap tidak akan sampai -- persis bug kritis
    yang sedang diperbaiki."""
    try:
        record = store.get_agent(agent_id)
    except store.SecretKeyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Agent tidak ditemukan.")

    adapter = build_adapter(record)
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"Platform '{record.platform}' tidak dikenal.")

    success, detail = await adapter.test_connection()
    if not success:
        logger.warning("Tes koneksi gagal untuk agent %s (%s): %s", record.name, record.id, detail)
    return {"success": success, "detail": detail}
