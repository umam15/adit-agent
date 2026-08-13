"""Client tipis untuk memanggil /v1/chat/completions di server adit.
Selalu non-streaming (lihat README.md bagian "Kenapa non-streaming") --
adit-agent menunggu jawaban penuh baru mengirimkannya sekali lewat
Incoming Webhook Synology.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger("adit-agent.adit_client")


class AditError(Exception):
    """Error yang sudah diterjemahkan jadi pesan ramah untuk ditampilkan ke user Synology Chat."""


def _build_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.adit_api_key:
        headers["Authorization"] = f"Bearer {settings.adit_api_key}"
    return headers


def _describe_error(status_code: int, body: dict | None) -> str:
    if status_code == 400:
        msg = (body or {}).get("error", {}).get("message", "input ditolak server")
        return f"Pertanyaan ditolak server (400): {msg}"
    if status_code == 401:
        return "Tidak terautentikasi ke server adit (401) -- cek ADIT_API_KEY di adit-agent."
    if status_code == 429:
        return "Server adit sedang sibuk (rate limit 429), coba lagi sebentar lagi."
    if status_code == 503:
        return "Server adit belum punya checkpoint model terlatih (503)."
    return f"Server adit membalas HTTP {status_code}."


async def ask_adit(text: str, session_id: str) -> str:
    """Kirim satu pertanyaan ke adit (single-turn -- lihat catatan di README
    soal riwayat percakapan) dan kembalikan teks jawabannya.

    Bisa berupa jawaban model biasa, jawaban dari cache, ATAU pertanyaan
    klarifikasi balik dari server -- ketiganya sama-sama teks yang layak
    dikirim apa adanya ke user, cukup dibedakan lewat adit_meta.source kalau
    perlu ditandai (lihat _format_reply di webhook.py).
    """
    body = {
        "model": "adit-mini-v0.1",
        "messages": [{"role": "user", "content": text}],
        "max_tokens": settings.adit_max_tokens,
        "temperature": settings.adit_temperature,
        "top_k": settings.adit_top_k,
        "session_id": session_id,
        "stream": False,
    }

    url = settings.adit_base_url.rstrip("/") + "/v1/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=settings.adit_request_timeout) as client:
            res = await client.post(url, headers=_build_headers(), json=body)
    except httpx.HTTPError as exc:
        logger.error("Gagal menghubungi server adit di %s: %s", url, exc)
        raise AditError("Tidak bisa menghubungi server adit -- cek ADIT_BASE_URL dan pastikan server jalan.") from exc

    if res.status_code != 200:
        try:
            error_body = res.json()
        except ValueError:
            error_body = None
        raise AditError(_describe_error(res.status_code, error_body))

    data = res.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    source = data.get("adit_meta", {}).get("source", "model")

    return _annotate_reply(content, source)


def _annotate_reply(content: str, source: str) -> str:
    """Tandai balasan yang bukan jawaban langsung, biar user Synology Chat
    tahu konteksnya (server tidak lagi menjawab, tapi menunggu klarifikasi)."""
    if source == "clarification_pending":
        return f"❓ {content}"
    return content
