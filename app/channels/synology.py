"""Adapter Synology Chat untuk ChannelAdapter (app/channels/base.py).

Class ini sengaja TIPIS -- cuma mendelegasikan ke dua concern yang sudah
dipisah eksplisit:
  - `SynologyChatListener` (synology_chat_listener.py): listener,
    verifikasi token + parse Outgoing Webhook masuk.
  - `SynologyChatBot` (synology_chat_bot.py): sender, format & kirim
    balasan lewat Incoming Webhook / Bot.

Kenapa dipisah padahal sama-sama "Synology Chat": dua integrasi ini pakai
halaman setting, token, dan bentuk payload yang sama sekali berbeda di sisi
Synology Chat sendiri (lihat tabel di TODO.md). Menggabungkannya jadi satu
class membuat asumsi format yang salah di satu sisi (sender) tidak ketahuan
hanya dengan mengetes sisi lain (listener) -- persis penyebab bug format
payload di v0.3 (lihat CHANGELOG.md).

Kontrak `ChannelAdapter` yang dipakai `main.py`/`orchestrator.py` TIDAK
berubah lewat refactor ini -- perilaku fungsional identik dengan v0.3.
"""
from __future__ import annotations

from fastapi import Request

from ..config import settings
from .base import ChannelAdapter, IncomingMessage
from .synology_chat_bot import SynologyChatBot
from .synology_chat_listener import SynologyChatListener


class SynologyAdapter(ChannelAdapter):
    name = "synology"
    webhook_path = "/webhook/synology"

    def __init__(self) -> None:
        self._listener = SynologyChatListener()
        self._bot = SynologyChatBot()

    async def parse_request(self, request: Request) -> IncomingMessage:
        return await self._listener.parse_request(request)

    def ack_response(self, message: IncomingMessage):
        return {"text": settings.ack_message}

    def reject_response(self):
        return {"text": ""}

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        await self._bot.send_reply(message, text)
