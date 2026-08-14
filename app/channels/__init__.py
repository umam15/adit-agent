"""Registry channel yang aktif. Untuk menambah channel baru:

  1. Buat app/channels/<nama>.py yang mengimplementasikan ChannelAdapter
     (lihat base.py untuk kontraknya, synology.py untuk contoh nyata).
  2. Import class adapter-nya di sini, tambahkan instance-nya ke CHANNELS.

main.py otomatis mendaftarkan route webhook untuk setiap adapter di CHANNELS
lewat `webhook_path` masing-masing -- tidak ada bagian lain yang perlu diubah.
"""
from .base import AuthError, ChannelAdapter, IncomingMessage
from .synology import SynologyAdapter

CHANNELS: list[ChannelAdapter] = [
    SynologyAdapter(),
    # TelegramAdapter(),  # contoh: tinggal import + tambahkan di sini
]

__all__ = ["ChannelAdapter", "IncomingMessage", "AuthError", "CHANNELS"]
