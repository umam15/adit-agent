"""Orkestrasi generik: terima IncomingMessage dari channel apa pun, panggil
server adit, kirim balasan lewat adapter yang sama. Ini satu-satunya tempat
yang mengimpor adit_client -- adapter channel (Synology, Telegram, dst)
sama sekali tidak perlu tahu soal server adit, cukup implementasikan
ChannelAdapter.send_reply().
"""
from __future__ import annotations

import logging

from .adit_client import AditError, ask_adit
from .channels.base import ChannelAdapter, IncomingMessage

logger = logging.getLogger("adit-agent.orchestrator")


async def handle_message(adapter: ChannelAdapter, message: IncomingMessage) -> None:
    """Dipanggil sebagai background task oleh main.py -- tidak menahan
    respons webhook channel manapun."""
    try:
        reply = await ask_adit(message.text, session_id=message.session_id)
    except AditError as exc:
        reply = f"⚠️ {exc}"
    except Exception:  # noqa: BLE001 -- jangan sampai background task diam-diam mati tanpa jejak
        logger.exception(
            "Error tak terduga saat memproses pesan channel=%s session=%s",
            adapter.name,
            message.session_id,
        )
        reply = "⚠️ Terjadi error tak terduga di adit-agent. Cek log server untuk detail."

    await adapter.send_reply(message, reply)
