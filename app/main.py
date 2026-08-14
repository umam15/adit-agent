"""adit-agent -- jembatan antara channel chat (Synology Chat, dan channel
lain di masa depan) dan server adit.

Untuk menambah channel baru, lihat README.md bagian "Menambah channel baru"
-- singkatnya: buat app/channels/<nama>.py yang mengimplementasikan
ChannelAdapter (app/channels/base.py), daftarkan di app/channels/__init__.py.
Route webhook-nya otomatis terdaftar di bawah lewat `webhook_path` adapter
-- main.py sendiri tidak perlu diubah sama sekali.

Jalankan:
    uvicorn app.main:app --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from .channels import CHANNELS
from .channels.base import AuthError, ChannelAdapter
from .orchestrator import handle_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("adit-agent")

app = FastAPI(title="adit-agent", description="Jembatan channel chat <-> server adit")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "channels": [c.name for c in CHANNELS]}


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


for _adapter in CHANNELS:
    app.add_api_route(
        _adapter.webhook_path,
        _make_webhook_handler(_adapter),
        methods=["POST"],
        name=f"webhook_{_adapter.name}",
    )

