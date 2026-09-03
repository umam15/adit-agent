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

v0.4.5: constructor sekarang terima `platform` -- dipakai untuk memaksa
`reply_to_user=True` saat platform adalah `"synology_bot"`, TIDAK
diserahkan ke pengguna mengisi toggle. Ini perbaikan bug kritis (lihat
TODO.md, laporan pengujian 2026-08-22 M3): payload ke URL Bot
(`method=chatbot`) wajib menyertakan `user_ids`, dan sebelum ini tidak ada
jalur apa pun yang membuat `reply_to_user` bernilai `true` secara otomatis
-- request tetap sukses (HTTP 200) tapi pesan tidak sampai ke siapa pun.

v0.6.2: `config["ack_message"]` (opsional, per-agent, diisi lewat panel
admin) -- kalau diisi, dipakai sebagai pesan ACK instan untuk agent ini
saja, menimpa default global `settings.ack_message` (`ADIT_ACK_MESSAGE`).
Kosong/tidak diisi = tetap pakai default global, perilaku identik versi
sebelumnya.
"""
from __future__ import annotations

from fastapi import Request

from ..config import settings
from .base import ChannelAdapter, IncomingMessage
from .synology_chat_bot import SynologyChatBot
from .synology_chat_listener import SynologyChatListener

#: Platform yang WAJIB reply_to_user=True karena secara definisi memakai
#: method=chatbot Synology (URL Bot, bukan Incoming Webhook polos). Bukan
#: sesuatu yang boleh dikonfigurasi berbeda oleh pengguna -- ini properti
#: platform itu sendiri, bukan pilihan.
_FORCE_REPLY_TO_USER = {"synology_bot"}


class SynologyAdapter(ChannelAdapter):
    def __init__(
        self,
        agent_id: str = "synology",
        display_name: str = "Synology Chat",
        webhook_path: str = "/webhook/synology",
        config: dict[str, str] | None = None,
        platform: str = "synology_chat",
    ) -> None:
        # `name`: kontrak ChannelAdapter, dipakai prefix session_id & log --
        # HARUS unik per instance kalau ada >1 agent Synology Chat.
        self.name = agent_id
        # `display_name`: label untuk UI/log manusia, bukan bagian kontrak
        # ChannelAdapter -- boleh diubah bebas tanpa memengaruhi session_id.
        self.display_name = display_name
        self.webhook_path = webhook_path

        config = dict(config or {})
        if platform in _FORCE_REPLY_TO_USER:
            # Override, BUKAN setdefault -- kalau suatu saat ada nilai
            # `false` tersimpan dari versi lama (sebelum fix ini), override
            # tetap harus menang, bukan dihormati.
            config["reply_to_user"] = True

        # Pesan ACK per-agent (opsional) -- string kosong/tidak diisi berarti
        # pakai default global `settings.ack_message` (ADIT_ACK_MESSAGE).
        # Lihat ack_response() di bawah & TODO.md "Pesan ACK bisa custom".
        self._ack_message = (config.get("ack_message") or "").strip() or None

        self._listener = SynologyChatListener(config, channel_id=agent_id)
        self._bot = SynologyChatBot(config)

    async def parse_request(self, request: Request) -> IncomingMessage:
        return await self._listener.parse_request(request)

    def ack_response(self, message: IncomingMessage):
        return {"text": self._ack_message or settings.ack_message}

    def reject_response(self):
        return {"text": ""}

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        await self._bot.send_reply(message, text)

    async def test_connection(self) -> tuple[bool, str]:
        """Dipakai endpoint admin 'Tes koneksi' -- lihat docstring
        SynologyChatBot.test_connection()."""
        return await self._bot.test_connection()
