"""Registry channel yang aktif.

Sumber CHANNELS **murni dari database** (app/store.py), diisi lewat panel
admin di `/admin` -- lihat app/api_admin.py. Tidak ada fallback ke env var
untuk kredensial channel; env var di adit-agent sekarang khusus setting
admin/server (lihat app/config.py & README.md), bukan tempat mengisi token
per-agent.

Konsekuensi: `ADIT_AGENT_SECRET_KEY` (key enkripsi kredensial di database)
WAJIB diisi supaya adit-agent bisa start sama sekali -- kalau belum diisi,
`load_channels()` sengaja MEMBIARKAN `SecretKeyMissing` menjalar ke atas
(bukan ditangkap diam-diam) supaya kegagalannya eksplisit di log startup,
bukan berupa "kok webhook tidak jalan" yang membingungkan belakangan.

Kalau database belum punya agent aktif sama sekali (instalasi baru,
ADIT_AGENT_SECRET_KEY sudah diisi tapi belum ada agent ditambah lewat UI),
CHANNELS akan kosong -- adit-agent tetap start normal, `/healthz` dan
`/admin` tetap bisa diakses, cuma belum ada route webhook terdaftar sampai
agent pertama ditambah + proses di-restart.

Untuk menambah JENIS channel baru (bukan instance baru dari jenis yang
sudah ada):
  1. Buat app/channels/<nama>.py yang mengimplementasikan ChannelAdapter
     (lihat base.py untuk kontraknya, synology.py untuk contoh nyata).
  2. Import class adapter-nya di sini, daftarkan di _PLATFORM_ADAPTERS
     dengan key nama platform yang dipakai UI/database (mis. "telegram").
  3. Tambahkan juga di _WEBHOOK_PREFIX (app/api_admin.py) supaya webhook_path
     yang di-generate otomatis saat agent dibuat dari UI masuk akal.

main.py otomatis mendaftarkan route webhook untuk setiap adapter yang
dikembalikan load_channels() lewat `webhook_path` masing-masing -- tidak
ada bagian lain yang perlu diubah.
"""
from __future__ import annotations

import logging

from .base import AuthError, ChannelAdapter, IncomingMessage
from .synology import SynologyAdapter

logger = logging.getLogger("adit-agent.channels")

#: platform (string yang disimpan di kolom `platform` tabel agents) -> class
#: adapter yang dipakai. "synology_chat" dan "synology_bot" sengaja dipetakan
#: ke class yang SAMA (SynologyAdapter) -- bedanya cuma field kredensial mana
#: yang diisi lewat `config` (lihat app/web -- dua platform ini beda field,
#: sama-sama diproses SynologyChatListener/SynologyChatBot di baliknya).
_PLATFORM_ADAPTERS: dict[str, type[ChannelAdapter]] = {
    "synology_chat": SynologyAdapter,
    "synology_bot": SynologyAdapter,
    # "telegram": TelegramAdapter,  # TODO.md "Panel kontrol multi-agent" prioritas menengah
}


def build_adapter(record) -> ChannelAdapter | None:
    """Bangun satu instance adapter dari `AgentRecord` (app/store.py).
    Dipakai `load_channels()` di bawah, dan `api_admin.py` (endpoint tes
    koneksi) untuk membangun adapter sekali-pakai tanpa lewat CHANNELS.
    Return `None` kalau platform-nya tidak dikenal (pemanggil yang
    memutuskan mau log warning atau raise HTTPException)."""
    adapter_cls = _PLATFORM_ADAPTERS.get(record.platform)
    if adapter_cls is None:
        return None
    # `platform` cuma relevan untuk adapter yang dipakai lintas >1 platform
    # (kasus SynologyAdapter, lihat _FORCE_REPLY_TO_USER di synology.py) --
    # adapter lain (mis. TelegramAdapter di masa depan, lihat
    # docs/architecture.md) tidak wajib menerima parameter ini.
    try:
        return adapter_cls(
            agent_id=record.id,
            display_name=record.name,
            webhook_path=record.webhook_path,
            config=record.creds,
            platform=record.platform,
        )
    except TypeError:
        return adapter_cls(
            agent_id=record.id,
            display_name=record.name,
            webhook_path=record.webhook_path,
            config=record.creds,
        )


def load_channels() -> list[ChannelAdapter]:
    from .. import store

    # Sengaja TIDAK di-try/except di sini -- lihat docstring modul soal
    # kenapa SecretKeyMissing harus menjalar ke atas dan menghentikan start,
    # bukan fallback diam-diam.
    records = store.list_agents(active_only=True)

    channels: list[ChannelAdapter] = []
    for record in records:
        adapter = build_adapter(record)
        if adapter is None:
            logger.warning(
                "Agent '%s' (id=%s) pakai platform '%s' yang belum didukung -- dilewati.",
                record.name, record.id, record.platform,
            )
            continue
        channels.append(adapter)

    if not channels:
        logger.info(
            "Belum ada agent aktif di database. Buka http://<host>:<port>/admin "
            "untuk menambah agent (Synology Chat, Synology Bot, dst)."
        )

    return channels


CHANNELS: list[ChannelAdapter] = load_channels()

__all__ = ["ChannelAdapter", "IncomingMessage", "AuthError", "CHANNELS", "load_channels", "build_adapter"]
