"""adit-agent -- jembatan antara Synology Chat dan server adit.

Alur:
  1. Synology Chat kirim outgoing webhook (form-urlencoded: token, user_id,
     username, text, channel_name, post_id, ...) tiap kali bot ditrigger.
  2. adit-agent verifikasi token, langsung balas JSON {"text": ack_message}
     supaya UI Synology Chat tidak macet di "Processing..." -- generate di
     server adit (CPU, token-per-token) bisa lebih lama dari timeout webhook.
  3. Di background, adit-agent panggil /v1/chat/completions (non-streaming)
     ke server adit, lalu kirim jawaban aslinya lewat Incoming Webhook URL
     begitu selesai -- muncul sebagai pesan baru di channel yang sama.

Jalankan:
    uvicorn app.main:app --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from .adit_client import AditError, ask_adit
from .config import settings
from .synology import send_incoming_webhook, verify_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("adit-agent")

app = FastAPI(title="adit-agent", description="Jembatan Synology Chat <-> server adit")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


async def _handle_and_reply(text: str, session_id: str) -> None:
    """Dipanggil sebagai background task -- tidak menahan respons webhook."""
    try:
        reply = await ask_adit(text, session_id=session_id)
    except AditError as exc:
        reply = f"⚠️ {exc}"
    except Exception:  # noqa: BLE001 -- jangan sampai background task diam-diam mati tanpa jejak
        logger.exception("Error tak terduga saat memproses pesan dari session %s", session_id)
        reply = "⚠️ Terjadi error tak terduga di adit-agent. Cek log server untuk detail."

    await send_incoming_webhook(reply)


@app.post("/webhook/synology")
async def synology_webhook(request: Request, background_tasks: BackgroundTasks):
    # Synology mengirim application/x-www-form-urlencoded secara default;
    # beberapa setup/proxy bisa mengirim JSON -- coba dua-duanya biar tidak
    # rapuh (lihat catatan kompatibilitas di README.md).
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    token = payload.get("token") or request.query_params.get("token")
    if not verify_token(token):
        logger.warning("Request ditolak: token tidak valid/hilang.")
        # Tetap balas 200 dengan JSON kosong -- Synology tidak butuh detail
        # kegagalan auth ditampilkan ke user chat, cukup dicatat di log server.
        return JSONResponse({"text": ""}, status_code=200)

    text = (payload.get("text") or "").strip()
    user_id = payload.get("user_id", "unknown")
    channel_name = payload.get("channel_name", "unknown")

    if not text:
        return JSONResponse({"text": "Kirim pertanyaan dulu ya."}, status_code=200)

    # session_id per user+channel -- selaras dengan alur klarifikasi server
    # adit yang di-key per session_id (lihat docs server: get_pending_clarification).
    session_id = f"synology:{channel_name}:{user_id}"[:200]  # server membatasi max 200 char

    background_tasks.add_task(_handle_and_reply, text, session_id)

    return JSONResponse({"text": settings.ack_message}, status_code=200)
