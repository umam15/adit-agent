"""Sisi *listener* integrasi Synology Chat: terima & verifikasi Outgoing
Webhook (Synology Chat -> kita).

Sengaja dipisah dari `synology_chat_bot.py` (sisi *sender*, Incoming
Webhook/Bot, kita -> Synology Chat) meskipun sama-sama bagian dari
"Synology Chat" -- keduanya pakai halaman setting, token, dan bentuk
payload yang sama sekali berbeda. Lihat TODO.md "Prioritas tinggi" untuk
latar belakang kenapa pemisahan ini penting (bug format payload di v0.3
salah satunya disebabkan dua konsep ini digabung jadi satu class).

Nama class sengaja "SynologyChatListener", bukan "SynologyChannel" --
"channel" bukan istilah yang dipakai dokumentasi resmi Synology Chat untuk
integrasi ini (dan malah bentrok dengan istilah "channel" chat itu
sendiri), jadi lebih mudah dicari referensinya pakai istilah "Synology
Chat" langsung.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Request

from .base import AuthError, IncomingMessage

logger = logging.getLogger("adit-agent.channels.synology_chat_listener")


class SynologyChatListener:
    """Verifikasi Outgoing Webhook Synology Chat + parse jadi IncomingMessage.

    Kredensial (`outgoing_token`) WAJIB datang dari `config` (diisi lewat
    panel admin `/admin`, disimpan `app/store.py`) -- tidak ada fallback ke
    env var. Kalau `config` kosong/tidak diisi, `outgoing_token` kosong dan
    `_verify_token()` fail closed (tolak semua request), bukan diam-diam
    mengizinkan.
    """

    def __init__(self, config: dict[str, str] | None = None, channel_id: str = "synology") -> None:
        config = config or {}
        # `channel_id` dipakai sebagai `IncomingMessage.channel` & prefix
        # session_id -- WAJIB unik per agent kalau ada >1 instance Synology
        # Chat, supaya session_id (dan riwayat percakapan per session_id di
        # server adit) dua agent berbeda tidak numpuk jadi satu.
        self.name = channel_id
        self.outgoing_token = config.get("outgoing_token", "")

    def _verify_token(self, received_token: str | None) -> bool:
        """Constant-time compare, fail closed kalau token belum dikonfigurasi."""
        if not self.outgoing_token:
            logger.warning(
                "SYNOLOGY_OUTGOING_TOKEN belum diset -- menolak semua request masuk."
            )
            return False
        if not received_token:
            return False
        return hmac.compare_digest(received_token, self.outgoing_token)

    async def parse_request(self, request: Request) -> IncomingMessage:
        # Synology default kirim application/x-www-form-urlencoded; beberapa
        # setup/proxy bisa kirim JSON -- dukung dua-duanya biar tidak rapuh.
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)

        token = payload.get("token") or request.query_params.get("token")
        if not self._verify_token(token):
            raise AuthError("token Synology tidak valid/hilang")

        text = str(payload.get("text") or "").strip()
        user_id = str(payload.get("user_id", "unknown"))
        channel_name = str(payload.get("channel_name", "unknown"))

        # session_id per agent+channel+user -- selaras dengan alur klarifikasi
        # server adit yang di-track per session_id. Pakai self.name (bukan
        # "synology" hardcode) supaya dua instance Synology Chat berbeda
        # (mis. "Tim Support" vs "Channel Alerting") tidak numpuk histori.
        session_id = f"{self.name}:{channel_name}:{user_id}"[:200]  # server batasi maks 200 char

        return IncomingMessage(
            channel=self.name, session_id=session_id, text=text, user_id=user_id, raw=payload
        )
