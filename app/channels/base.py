"""Kontrak yang harus dipenuhi tiap integrasi channel (Synology Chat,
Telegram, Slack, dst). Satu file baru yang mengimplementasikan
ChannelAdapter + didaftarkan di channels/__init__.py = satu channel baru.
Tidak ada bagian lain di adit-agent yang perlu diubah.

Lihat channels/synology.py untuk contoh implementasi nyata, dan README.md
bagian "Menambah channel baru" untuk panduan langkah-demi-langkah.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request


class AuthError(Exception):
    """Dilempar adapter dari parse_request() kalau verifikasi request masuk
    gagal (token/signature salah atau hilang, dst)."""


@dataclass
class IncomingMessage:
    """Bentuk pesan masuk yang sudah dinormalisasi -- sama untuk semua
    channel. orchestrator.py dan adit_client.py tidak perlu tahu channel
    asalnya sama sekali, cukup pakai field di sini."""

    channel: str
    session_id: str
    text: str
    user_id: str
    raw: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(ABC):
    """Implementasikan class ini untuk menambah channel baru."""

    #: identitas singkat channel, dipakai untuk prefix session_id & logging
    name: str
    #: path route webhook yang akan didaftarkan otomatis oleh main.py
    webhook_path: str

    @abstractmethod
    async def parse_request(self, request: Request) -> IncomingMessage:
        """Ekstrak & verifikasi request masuk jadi IncomingMessage.
        WAJIB raise AuthError kalau verifikasi (token/signature/dst) gagal
        -- jangan biarkan request tak terverifikasi lolos ke handle_message."""

    @abstractmethod
    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        """Kirim jawaban akhir (dari server adit) ke channel. Dipanggil dari
        background task -- TIDAK menahan respons webhook, jadi boleh makan
        waktu selama perlu (batasi sendiri lewat timeout di sisi HTTP client
        adapter, seperti SynologyAdapter)."""

    def ack_response(self, message: IncomingMessage) -> Any:
        """Body respons SINKRON langsung ke webhook (dict, akan di-JSON-kan).
        Default dict kosong -- override kalau channel butuh format/pesan ACK
        spesifik (lihat SynologyAdapter yang balas {"text": ack_message})."""
        return {}

    def reject_response(self) -> Any:
        """Body respons kalau AuthError. Default dict kosong -- sengaja
        tidak membocorkan detail kegagalan auth ke pengirim request."""
        return {}

    def empty_text_response(self, message: IncomingMessage) -> Any:
        """Body respons kalau teks pesan kosong setelah di-strip."""
        return {"text": "Kirim pertanyaan dulu ya."}

    async def test_connection(self) -> tuple[bool, str]:
        """OPSIONAL (bukan bagian kontrak wajib) -- implementasikan kalau
        channel ini ingin didukung tombol "Tes koneksi" di panel admin
        (app/api_admin.py). Default: dianggap tidak didukung. Beda dari
        send_reply(): harus melaporkan sukses/gagal secara eksplisit, tidak
        boleh cuma log lalu diam. Lihat SynologyAdapter.test_connection()."""
        return False, "Channel ini belum mendukung tes koneksi."
