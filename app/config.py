"""Konfigurasi adit-agent, semua lewat env var (lihat .env.example)."""
from __future__ import annotations

import os


def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- server adit (sumber jawaban) ---
    adit_base_url: str = os.environ.get("ADIT_BASE_URL", "http://localhost:8000")
    adit_api_key: str = os.environ.get("ADIT_API_KEY", "")
    adit_max_tokens: int = int(os.environ.get("ADIT_MAX_TOKENS", "150"))
    adit_temperature: float = float(os.environ.get("ADIT_TEMPERATURE", "0.8"))
    adit_top_k: int = int(os.environ.get("ADIT_TOP_K", "20"))
    adit_request_timeout: float = float(os.environ.get("ADIT_REQUEST_TIMEOUT", "120"))

    # --- Synology Chat ---
    # Token dari "Outgoing Webhook" yang dibuat di Integration > Bot -- dipakai
    # untuk verifikasi request masuk BENAR dari Synology, bukan sumber lain.
    synology_outgoing_token: str = os.environ.get("SYNOLOGY_OUTGOING_TOKEN", "")

    # URL lengkap dari "Incoming Webhook" (format:
    # https://<nas>/webapi/entry.cgi?api=SYNO.Chat.External&method=incoming&version=2&token=...)
    # dipakai untuk mengirim balasan akhir setelah model selesai generate.
    synology_incoming_webhook_url: str = os.environ.get("SYNOLOGY_INCOMING_WEBHOOK_URL", "")

    # verifikasi TLS ke NAS -- boleh dimatikan untuk NAS lokal dengan
    # sertifikat self-signed, TAPI hanya kalau jaringan tsb dipercaya.
    synology_verify_ssl: bool = _get_bool("SYNOLOGY_VERIFY_SSL", True)

    # pesan ACK instan yang dibalas ke request webhook (biar UI Synology Chat
    # tidak macet di "Processing...") sebelum jawaban asli menyusul lewat
    # Incoming Webhook.
    ack_message: str = os.environ.get("ADIT_ACK_MESSAGE", "🤖 sedang mikir…")

    host: str = os.environ.get("ADIT_AGENT_HOST", "0.0.0.0")
    port: int = int(os.environ.get("ADIT_AGENT_PORT", "9000"))


settings = Settings()
