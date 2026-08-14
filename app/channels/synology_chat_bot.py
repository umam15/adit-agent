"""Sisi *sender* (bot) integrasi Synology Chat: format & kirim balasan lewat
Incoming Webhook / Bot (kita -> Synology Chat).

Sengaja dipisah dari `synology_chat_listener.py` (sisi *listener*, Outgoing
Webhook, Synology Chat -> kita) -- lihat docstring di sana untuk latar
belakang. Manfaat konkret pemisahan ini: `SynologyChatBot.send_reply()`
bisa dites sendiri (format payload benar/salah) tanpa perlu mock request
webhook masuk sama sekali -- persis skenario yang kalau dilakukan dari awal
kemungkinan besar membuat bug format payload di v0.3 ketahuan lebih cepat.
"""
from __future__ import annotations

import json
import logging
import os

import httpx

from .base import IncomingMessage

logger = logging.getLogger("adit-agent.channels.synology_chat_bot")


def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class SynologyChatBot:
    """Kirim balasan akhir sebagai pesan baru lewat Incoming Webhook Synology
    Chat.

    Setting: Profile > Integration > Incoming Webhook -- URL lengkap
    (termasuk `?token=...`) di `SYNOLOGY_INCOMING_WEBHOOK_URL`.
    """

    def __init__(self) -> None:
        self.incoming_webhook_url = os.environ.get("SYNOLOGY_INCOMING_WEBHOOK_URL", "")
        self.verify_ssl = _get_bool("SYNOLOGY_VERIFY_SSL", True)
        # Ada DUA jenis tujuan yang sama-sama disebut "incoming webhook URL"
        # di Synology Chat, dan payload-nya BEDA:
        #   - "Incoming Webhook" polos (Profile > Integration > Incoming
        #     Webhook): terikat ke SATU channel tetap, payload cukup
        #     {"text": ...} -- default, backward-compatible dengan v0.1-v0.4.
        #   - URL milik sebuah "Bot" (Profile > Integration > Bot; method
        #     Synology-nya "chatbot"): tidak terikat ke channel manapun,
        #     payload WAJIB menyertakan "user_ids" (daftar penerima) atau
        #     balasan tidak sampai ke siapa pun. Lihat README.md "Konfigurasi".
        self.reply_to_user = _get_bool("SYNOLOGY_REPLY_TO_USER", False)

    def _build_payload(self, message: IncomingMessage, text: str) -> dict:
        body: dict = {"text": text}
        if self.reply_to_user:
            try:
                body["user_ids"] = [int(message.user_id)]
            except (TypeError, ValueError):
                logger.warning(
                    "SYNOLOGY_REPLY_TO_USER aktif tapi user_id '%s' bukan angka -- "
                    "kirim tanpa user_ids (kemungkinan tidak sampai ke user manapun "
                    "kalau URL ini memang milik Bot/method=chatbot).",
                    message.user_id,
                )
        return body

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        if not self.incoming_webhook_url:
            logger.error(
                "SYNOLOGY_INCOMING_WEBHOOK_URL belum diset, tidak bisa kirim balasan: %s", text
            )
            return

        # PENTING: Incoming Webhook Synology butuh application/x-www-form-urlencoded
        # dengan field "payload" berisi STRING JSON -- bukan Content-Type
        # application/json dengan body JSON mentah. Lihat tutorial resmi:
        # https://kb.synology.com/en-global/DSM/tutorial/How_to_configure_webhooks_and_slash_commands_in_Chat_Integration
        # Salah format ini bikin request diterima (kadang 200) tapi pesan
        # tidak pernah benar-benar muncul di channel, atau ditolak diam-diam.
        # (Bug ini kejadian persis di v0.3 -- lihat CHANGELOG.md.)
        form_data = {"payload": json.dumps(self._build_payload(message, text), ensure_ascii=False)}
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            try:
                res = await client.post(self.incoming_webhook_url, data=form_data)
                if res.status_code >= 400:
                    logger.error(
                        "Incoming webhook Synology membalas HTTP %s: %s", res.status_code, res.text
                    )
            except httpx.HTTPError as exc:
                logger.error("Gagal mengirim ke incoming webhook Synology: %s", exc)
