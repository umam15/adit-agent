"""Konfigurasi INTI adit-agent (lintas channel), semua lewat env var.
Setting yang spesifik ke satu channel (mis. token/URL Synology) sengaja
TIDAK di sini -- lihat masing-masing app/channels/<nama>.py supaya tiap
channel self-contained (lihat README.md bagian "Menambah channel baru")."""
from __future__ import annotations

import os


class Settings:
    # --- server adit (sumber jawaban) ---
    adit_base_url: str = os.environ.get("ADIT_BASE_URL", "http://localhost:8000")
    adit_api_key: str = os.environ.get("ADIT_API_KEY", "")
    adit_max_tokens: int = int(os.environ.get("ADIT_MAX_TOKENS", "150"))
    adit_temperature: float = float(os.environ.get("ADIT_TEMPERATURE", "0.8"))
    adit_top_k: int = int(os.environ.get("ADIT_TOP_K", "20"))
    adit_request_timeout: float = float(os.environ.get("ADIT_REQUEST_TIMEOUT", "120"))

    # pesan ACK instan (dipakai lintas channel sebagai default; adapter boleh
    # override lewat ack_response() kalau butuh format berbeda)
    ack_message: str = os.environ.get("ADIT_ACK_MESSAGE", "🤖 sedang mikir…")

    host: str = os.environ.get("ADIT_AGENT_HOST", "0.0.0.0")
    port: int = int(os.environ.get("ADIT_AGENT_PORT", "9000"))


settings = Settings()

