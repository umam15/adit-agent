"""adit-agent -- jembatan antara channel chat (Synology Chat, dan channel
lain di masa depan) dan server adit.

Untuk menambah channel baru, lihat docs/architecture.md -- singkatnya: buat
app/channels/<nama>.py yang mengimplementasikan ChannelAdapter
(app/channels/base.py), daftarkan di app/channels/__init__.py
(_PLATFORM_ADAPTERS) dan app/api_admin.py (_WEBHOOK_PREFIX). main.py sendiri
tidak perlu diubah -- lihat "Webhook dispatch dinamis" di bawah.

Webhook dispatch dinamis: route webhook TIDAK didaftarkan satu-satu per
adapter saat startup. Sebagai gantinya ada SATU route generik
(`webhook_dispatch` di bawah) yang lookup agent dari database per request.
Konsekuensinya: tambah/ubah/aktifkan/nonaktifkan agent lewat panel admin
langsung live, TANPA restart proses -- lihat docstring `webhook_dispatch`
untuk detail & alasannya (TODO.md "Webhook dispatch dinamis").

CORS: hanya relevan untuk /api/agents/* (dipanggil dari browser oleh UI
panel kontrol). Endpoint /webhook/* TIDAK butuh CORS -- itu dipanggil
server-to-server oleh Synology/Telegram, bukan dari browser. Kalau UI
dihosting di origin terpisah dari adit-agent (domain lain, atau port lain
sekalipun sama-sama localhost), isi ADIT_AGENT_UI_ORIGINS supaya browser
tidak memblokir fetch()-nya.

Jalankan:
    uvicorn app.main:app --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, store
from .channels import build_adapter  # import ini juga memicu validasi
# ADIT_AGENT_SECRET_KEY (lewat CHANNELS = load_channels() di
# app/channels/__init__.py), gagal cepat saat startup kalau belum diisi --
# bukan nanti pertama kali ada webhook masuk.
from .channels.base import AuthError, ChannelAdapter
from .orchestrator import handle_message
from .api_admin import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("adit-agent")

app = FastAPI(
    title="adit-agent",
    description="Jembatan channel chat <-> server adit",
    version=__version__,
)

# Sengaja TIDAK default ke "*" -- /api/agents/* membaca & menulis kredensial
# channel (plus header Authorization admin kalau ADIT_AGENT_ADMIN_TOKEN
# diset), jadi origin yang boleh akses harus eksplisit di-whitelist.
# ADIT_AGENT_UI_ORIGINS: daftar origin dipisah koma, mis.
#   ADIT_AGENT_UI_ORIGINS=https://panel.rumah.local,http://localhost:8080
_ui_origins = [
    origin.strip()
    for origin in os.environ.get("ADIT_AGENT_UI_ORIGINS", "").split(",")
    if origin.strip()
]
if _ui_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ui_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
else:
    logger.info(
        "ADIT_AGENT_UI_ORIGINS belum diset -- /api/agents/* hanya bisa diakses "
        "dari origin yang sama dengan adit-agent sendiri (mis. dibuka lewat "
        "file:// atau disajikan dari proses ini juga). Kalau UI dijalankan di "
        "server/port terpisah, isi env var ini atau browser akan memblokirnya."
    )

app.include_router(admin_router)

# Panel admin (tambah/kelola agent, isi kredensial) -- disajikan langsung
# oleh adit-agent sendiri di /admin, same-origin dengan /api/agents/* jadi
# TIDAK butuh ADIT_AGENT_UI_ORIGINS untuk pemakaian default ini. Env var
# itu baru relevan kalau file app/web/index.html di-hosting terpisah
# (lihat komentar API_BASE di file itu).
app.mount("/admin", StaticFiles(directory="app/web", html=True), name="admin")


@app.get("/healthz")
def healthz():
    # Query fresh ke database tiap dipanggil (bukan baca list statis) --
    # supaya /healthz selalu mencerminkan status agent yang sebenarnya,
    # konsisten dengan webhook_dispatch yang juga selalu baca database.
    records = store.list_agents(active_only=True)
    return {"status": "ok", "version": __version__, "channels": [r.name for r in records]}


def _make_webhook_handler(adapter: ChannelAdapter):
    """Handler generik yang sama untuk semua channel -- logikanya (verifikasi
    -> ACK sinkron -> proses di background -> kirim balasan) tidak berubah
    channel apa pun yang dipakai, cuma parse_request/ack_response/send_reply
    yang beda-beda per adapter."""

    async def handler(request: Request, background_tasks: BackgroundTasks):
        try:
            message = await adapter.parse_request(request)
        except AuthError:
            logger.warning("[%s] Request ditolak: verifikasi gagal.", adapter.name)
            # Tetap balas 200 -- pengirim webhook tidak perlu tahu detail
            # kegagalan auth, cukup dicatat di log server.
            return JSONResponse(adapter.reject_response(), status_code=200)

        if not message.text.strip():
            return JSONResponse(adapter.empty_text_response(message), status_code=200)

        background_tasks.add_task(handle_message, adapter, message)
        return JSONResponse(adapter.ack_response(message), status_code=200)

    return handler


@app.post("/webhook/{platform}/{slug}")
async def webhook_dispatch(
    platform: str, slug: str, request: Request, background_tasks: BackgroundTasks
):
    """Satu route generik untuk SEMUA agent -- lookup dari database per
    request, bukan route statis per adapter yang didaftarkan sekali saat
    startup (perilaku 0.4.4 dan sebelumnya). Ini yang menghapus kebutuhan
    restart proses tiap kali agent ditambah/diubah/diaktifkan lewat panel
    admin (TODO.md "Webhook dispatch dinamis", laporan pengujian
    2026-08-22 M5).

    `{platform}`/`{slug}` di path TIDAK dipakai untuk menentukan adapter
    class -- itu cuma dua segmen yang direkonstruksi jadi `webhook_path`
    lengkap, lalu dicocokkan APA ADANYA ke kolom `webhook_path` di
    database. Platform sesungguhnya datang dari `record.platform`
    (tersimpan saat agent dibuat, lihat app/api_admin.py), bukan ditebak
    dari URL -- jadi walau `_WEBHOOK_PREFIX` (app/api_admin.py) memetakan
    `synology_chat`/`synology_bot` ke prefix path yang SAMA ("synology"),
    dispatch tetap benar karena look-up-nya berdasar `webhook_path` utuh,
    bukan segmen `{platform}`.

    404 generik untuk "tidak ada" maupun "ada tapi nonaktif" -- sengaja
    tidak dibedakan, supaya request tak dikenal tidak bisa dipakai untuk
    menebak-nebak agent mana saja yang terdaftar (enumeration).
    """
    webhook_path = f"/webhook/{platform}/{slug}"
    record = store.get_agent_by_webhook_path(webhook_path)
    if record is None or not record.active:
        raise HTTPException(status_code=404)

    adapter = build_adapter(record)
    if adapter is None:
        # Platform tersimpan di database tapi tidak ada/tidak lagi
        # didukung kode saat ini (mis. bekas percobaan channel yang
        # dihapus dari _PLATFORM_ADAPTERS) -- 404, bukan 500, karena dari
        # sudut pandang pengirim webhook, agent ini memang "tidak ada".
        raise HTTPException(status_code=404)

    handler = _make_webhook_handler(adapter)
    return await handler(request, background_tasks)

