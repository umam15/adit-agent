"""Helper untuk integrasi Synology Chat: verifikasi token outgoing webhook,
dan kirim balasan lewat incoming webhook.

Referensi format resmi: https://kb.synology.com/en-global/DSM/help/Chat/chat_integration
"""
from __future__ import annotations

import hmac
import logging

import httpx

from .config import settings

logger = logging.getLogger("adit-agent.synology")


def verify_token(received_token: str | None) -> bool:
    """Bandingkan token outgoing webhook dari Synology dengan token yang
    dikonfigurasi, pakai constant-time compare supaya tidak bocor lewat
    timing attack. Kalau SYNOLOGY_OUTGOING_TOKEN belum diisi di env,
    verifikasi otomatis gagal (fail closed, bukan malah mengizinkan semua)."""
    if not settings.synology_outgoing_token:
        logger.warning("SYNOLOGY_OUTGOING_TOKEN belum diset -- menolak semua request masuk.")
        return False
    if not received_token:
        return False
    return hmac.compare_digest(received_token, settings.synology_outgoing_token)


async def send_incoming_webhook(text: str) -> None:
    """Kirim pesan ke channel Synology Chat lewat Incoming Webhook URL.
    Dipanggil setelah jawaban dari adit selesai (bukan bagian dari respons
    sinkron ke outgoing webhook)."""
    if not settings.synology_incoming_webhook_url:
        logger.error("SYNOLOGY_INCOMING_WEBHOOK_URL belum diset, tidak bisa kirim balasan: %s", text)
        return

    payload = {"text": text}
    async with httpx.AsyncClient(verify=settings.synology_verify_ssl, timeout=30) as client:
        try:
            res = await client.post(settings.synology_incoming_webhook_url, json=payload)
            if res.status_code >= 400:
                logger.error(
                    "Incoming webhook Synology membalas HTTP %s: %s", res.status_code, res.text
                )
        except httpx.HTTPError as exc:
            logger.error("Gagal mengirim ke incoming webhook Synology: %s", exc)
