"""Penyimpanan "agent" (instance channel: nama, platform, kredensial,
status aktif) -- menggantikan .env sebagai sumber konfigurasi per-channel.

Kenapa dibutuhkan: `app/config.py` sengaja cuma menyimpan setting LINTAS
channel (lihat docstring di sana). Setting per-channel dulunya dibaca
langsung dari env var di masing-masing adapter (mis. `SYNOLOGY_OUTGOING_TOKEN`)
-- cukup untuk satu instance per platform, tapi dua batasan itu yang bikin
UI panel kontrol (lihat TODO.md "Panel kontrol multi-agent") tidak mungkin:
  1. Env var + restart manual = tidak bisa diubah dari UI saat runtime.
  2. Satu env var global = tidak bisa dua Synology Chat / dua Telegram bot
     berjalan sekaligus dengan kredensial berbeda.

Modul ini TIDAK mengubah cara adapter membaca config-nya sendiri secara
default (constructor adapter tetap fallback ke env var kalau `config=None`,
lihat app/channels/synology.py) -- jadi kalau ADIT_AGENT_SECRET_KEY belum
diset sama sekali, database ini juga belum dipakai dan perilaku identik
0.4.x. Fitur ini murni ADDITIVE.

Kredensial disimpan terenkripsi (Fernet/AES). Key enkripsi datang dari env
var `ADIT_AGENT_SECRET_KEY`, sengaja TIDAK ikut disimpan di database --
kalau database dicuri/dibocorkan tanpa key ini, kredensial di dalamnya
tetap tidak terbaca.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("adit-agent.store")

DB_PATH = Path(os.environ.get("ADIT_AGENT_DB_PATH", "data/adit-agent.db"))


class SecretKeyMissing(RuntimeError):
    """ADIT_AGENT_SECRET_KEY belum diset -- database agent belum bisa dipakai.

    Dilempar sebagai exception (bukan diam-diam pakai key kosong/default)
    supaya gagalnya EKSPLISIT: kalau ini sampai lolos, kredensial akan
    "terenkripsi" pakai key yang berubah-ubah tiap proses start, artinya
    tidak bisa didekripsi lagi setelah restart -- lebih baik gagal cepat
    di sini daripada kredensial jadi rusak diam-diam."""


def _get_fernet() -> Fernet:
    key = os.environ.get("ADIT_AGENT_SECRET_KEY", "")
    if not key:
        raise SecretKeyMissing(
            "ADIT_AGENT_SECRET_KEY belum diset. Generate sekali lalu simpan sebagai "
            "env var permanen (JANGAN generate ulang tiap deploy -- kredensial yang "
            "sudah tersimpan jadi tidak bisa dibaca lagi kalau key berubah):\n"
            "  python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise SecretKeyMissing(
            "ADIT_AGENT_SECRET_KEY tidak valid (harus base64 32-byte hasil "
            "Fernet.generate_key())."
        ) from exc


@dataclass
class AgentRecord:
    """Satu baris agent, kredensial SUDAH terdekripsi -- bentuk ini yang
    dipakai kode lain (channels/__init__.py, api_admin.py), bukan row DB
    mentah."""

    id: str
    platform: str
    name: str
    creds: dict[str, str]
    active: bool
    webhook_path: str
    created_at: str


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id              TEXT PRIMARY KEY,
            platform        TEXT NOT NULL,
            name            TEXT NOT NULL,
            creds_encrypted BLOB NOT NULL,
            active          INTEGER NOT NULL DEFAULT 0,
            webhook_path    TEXT NOT NULL UNIQUE,
            created_at      TEXT NOT NULL
        )
        """
    )
    return conn


def _row_to_record(row: tuple, fernet: Fernet) -> AgentRecord:
    agent_id, platform, name, creds_encrypted, active, webhook_path, created_at = row
    try:
        creds = json.loads(fernet.decrypt(creds_encrypted).decode())
    except InvalidToken as exc:
        # Paling sering terjadi karena ADIT_AGENT_SECRET_KEY berubah sejak
        # baris ini disimpan -- pesan error diarahkan ke situ, bukan cuma
        # "gagal dekripsi" yang tidak actionable.
        raise RuntimeError(
            f"Gagal dekripsi kredensial agent '{name}' ({agent_id}). "
            "ADIT_AGENT_SECRET_KEY kemungkinan berbeda dari saat agent ini "
            "disimpan -- kredensial perlu diisi ulang dari UI kalau key memang berubah."
        ) from exc
    return AgentRecord(
        id=agent_id,
        platform=platform,
        name=name,
        creds=creds,
        active=bool(active),
        webhook_path=webhook_path,
        created_at=created_at,
    )


def list_agents(active_only: bool = False) -> list[AgentRecord]:
    """Raise SecretKeyMissing kalau ADIT_AGENT_SECRET_KEY belum diset --
    pemanggil (channels/__init__.py) menangkap ini untuk fallback ke
    perilaku env-var lama, lihat docstring modul."""
    fernet = _get_fernet()
    query = (
        "SELECT id, platform, name, creds_encrypted, active, webhook_path, created_at "
        "FROM agents"
    )
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY created_at"
    with _connect() as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_record(row, fernet) for row in rows]


def get_agent(agent_id: str) -> AgentRecord | None:
    fernet = _get_fernet()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, platform, name, creds_encrypted, active, webhook_path, created_at "
            "FROM agents WHERE id = ?",
            (agent_id,),
        ).fetchone()
    return _row_to_record(row, fernet) if row else None


def get_agent_by_webhook_path(webhook_path: str) -> AgentRecord | None:
    """Dipakai `main.py` untuk dispatch webhook dinamis (satu route generik,
    lookup per-request) -- lihat TODO.md "Webhook dispatch dinamis"."""
    fernet = _get_fernet()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, platform, name, creds_encrypted, active, webhook_path, created_at "
            "FROM agents WHERE webhook_path = ?",
            (webhook_path,),
        ).fetchone()
    return _row_to_record(row, fernet) if row else None


def create_agent(
    *, platform: str, name: str, creds: dict[str, str], webhook_path: str, active: bool = False
) -> AgentRecord:
    fernet = _get_fernet()
    agent_id = uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).isoformat()
    creds_encrypted = fernet.encrypt(json.dumps(creds).encode())
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO agents "
                "(id, platform, name, creds_encrypted, active, webhook_path, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, platform, name, creds_encrypted, int(active), webhook_path, created_at),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"webhook_path '{webhook_path}' sudah dipakai agent lain") from exc
    logger.info("Agent baru dibuat: id=%s platform=%s name=%r", agent_id, platform, name)
    return AgentRecord(
        id=agent_id, platform=platform, name=name, creds=creds,
        active=active, webhook_path=webhook_path, created_at=created_at,
    )


def update_agent(
    agent_id: str,
    *,
    name: str | None = None,
    creds: dict[str, str] | None = None,
    active: bool | None = None,
) -> AgentRecord:
    existing = get_agent(agent_id)
    if existing is None:
        raise KeyError(f"Agent {agent_id} tidak ditemukan")

    fernet = _get_fernet()
    new_name = existing.name if name is None else name
    new_creds = existing.creds if creds is None else creds
    new_active = existing.active if active is None else active
    creds_encrypted = fernet.encrypt(json.dumps(new_creds).encode())

    with _connect() as conn:
        conn.execute(
            "UPDATE agents SET name = ?, creds_encrypted = ?, active = ? WHERE id = ?",
            (new_name, creds_encrypted, int(new_active), agent_id),
        )
        conn.commit()
    logger.info("Agent diupdate: id=%s active=%s", agent_id, new_active)
    return AgentRecord(
        id=agent_id, platform=existing.platform, name=new_name, creds=new_creds,
        active=new_active, webhook_path=existing.webhook_path, created_at=existing.created_at,
    )


def delete_agent(agent_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        conn.commit()
    logger.info("Agent dihapus: id=%s", agent_id)
