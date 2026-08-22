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

import httpx

from .base import IncomingMessage

logger = logging.getLogger("adit-agent.channels.synology_chat_bot")


def _get_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _normalize_user_id(raw) -> int | None:
    """Synology tidak konsisten soal bentuk `user_id` yang dikirim balik ke
    kita lewat Outgoing Webhook -- kadang angka polos, kadang string angka,
    kadang (tergantung versi DSM) string berbentuk JSON-array satu elemen
    seperti '["8"]'. `int()` langsung gagal untuk kasus terakhir, dan
    kegagalan itu SILENT (cuma warning log) -- gejalanya identik dengan bug
    kritis `reply_to_user`, jadi diperlakukan sama seriusnya. Terima semua
    bentuk berikut, kembalikan None kalau benar-benar tidak bisa diartikan:
      - 8, "8" -> 8
      - '["8"]', ["8"], [8] -> 8 (ambil elemen pertama)
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        return _normalize_user_id(raw[0]) if raw else None
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
            except (ValueError, TypeError):
                return None
            return _normalize_user_id(parsed)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class SynologyChatBot:
    """Kirim balasan akhir sebagai pesan baru lewat Incoming Webhook Synology
    Chat.

    Semua field di bawah datang dari `config` (diisi lewat panel admin
    `/admin`), tidak ada fallback ke env var:
      - `incoming_webhook_url` (wajib)
      - `verify_ssl` (opsional, default True -- matikan kalau NAS pakai
        sertifikat self-signed)
      - `reply_to_user` (opsional, default False -- lihat penjelasan di
        `_build_payload()`)
    """

    def __init__(self, config: dict[str, str] | None = None) -> None:
        config = config or {}
        self.incoming_webhook_url = config.get("incoming_webhook_url", "")
        self.verify_ssl = _get_bool(config.get("verify_ssl"), True)
        # Ada DUA jenis tujuan yang sama-sama disebut "incoming webhook URL"
        # di Synology Chat, dan payload-nya BEDA:
        #   - "Incoming Webhook" polos (Profile > Integration > Incoming
        #     Webhook): terikat ke SATU channel tetap, payload cukup
        #     {"text": ...} -- default, backward-compatible dengan v0.1-v0.4.
        #   - URL milik sebuah "Bot" (Profile > Integration > Bot; method
        #     Synology-nya "chatbot"): tidak terikat ke channel manapun,
        #     payload WAJIB menyertakan "user_ids" (daftar penerima) atau
        #     balasan tidak sampai ke siapa pun. Lihat docs/channels/synology-chat.md.
        self.reply_to_user = _get_bool(config.get("reply_to_user"), False)

    def _build_payload(self, message: IncomingMessage, text: str) -> dict:
        body: dict = {"text": text}
        if self.reply_to_user:
            user_id = _normalize_user_id(message.user_id)
            if user_id is not None:
                body["user_ids"] = [user_id]
            else:
                logger.warning(
                    "reply_to_user aktif tapi user_id %r tidak bisa dinormalisasi jadi "
                    "angka -- kirim tanpa user_ids (kemungkinan tidak sampai ke user "
                    "manapun kalau URL ini memang milik Bot/method=chatbot).",
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

    async def test_connection(self) -> tuple[bool, str]:
        """Kirim SATU pesan uji sungguhan dan laporkan sukses/gagal secara
        eksplisit -- beda dari send_reply() yang sengaja diam (cuma log)
        supaya proses background pengiriman pesan normal tidak pernah crash.
        Dipakai HANYA oleh endpoint admin 'Tes koneksi' (app/api_admin.py),
        tidak pernah dipanggil dari alur pesan biasa."""
        if not self.incoming_webhook_url:
            return False, "URL incoming webhook/Bot belum diisi."

        test_message = IncomingMessage(channel="test", session_id="test", text="", user_id="0")
        payload = self._build_payload(test_message, "✅ Tes koneksi dari adit-agent berhasil.")
        form_data = {"payload": json.dumps(payload, ensure_ascii=False)}
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as client:
            try:
                res = await client.post(self.incoming_webhook_url, data=form_data)
            except httpx.HTTPError as exc:
                return False, f"Gagal terhubung ke URL webhook: {exc}"

        if res.status_code >= 400:
            return False, f"Server membalas HTTP {res.status_code}: {res.text[:200]}"
        return True, "Pesan uji terkirim -- cek channel/DM Synology Chat terkait."
