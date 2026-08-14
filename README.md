# adit-agent

Jembatan (bot) antara channel chat (**Synology Chat**, dan channel lain di
masa depan) dan server **adit** (`/v1/chat/completions`). Repo terpisah dari
`adit-client` karena perannya beda kelas: `adit-client` jalan di browser
orang, `adit-agent` adalah server yang harus terus hidup mendengarkan
webhook masuk.

Arsitekturnya berbasis **adapter per channel** — logika inti (panggil model,
manajemen background task) sama sekali tidak tahu channel mana yang dipakai.
Lihat bagian "Menambah channel baru" di bawah.

## Alur kerja

```
Synology Chat --(outgoing webhook, form-urlencoded)--> adit-agent
adit-agent    --(balas ACK instan, JSON)--------------> Synology Chat (langsung, sinkron)
adit-agent    --(POST /v1/chat/completions, non-stream)-> server adit
adit-agent    --(incoming webhook, setelah selesai)----> Synology Chat (async, pesan baru)
```

**Kenapa ACK instan + async, bukan sinkron langsung:** outgoing webhook
Synology Chat butuh respons cepat di request itu sendiri. Model `adit` jalan
di CPU dan generate token demi token bisa berdurasi lebih lama dari timeout
webhook, apalagi dengan `max_tokens` besar — kalau ditunggu sinkron, UI
Synology Chat bisa macet di "Processing...". Jadi `adit-agent` langsung
balas pesan ACK (`ADIT_ACK_MESSAGE`, default "🤖 sedang mikir…"), lalu
generate di background dan kirim jawaban aslinya sebagai pesan **baru**
lewat Incoming Webhook URL begitu selesai.

**Kenapa non-streaming, bukan streaming token-per-token:** Synology Chat
tidak menyediakan API publik untuk mengedit pesan yang sudah terkirim
(beda dari Slack `chat.update`), jadi tidak ada tempat berlabuh yang wajar
untuk menampilkan token yang muncul bertahap. `adit-agent` menunggu server
`adit` selesai generate penuh (`stream: false`), baru mengirim satu pesan.

## Setup

### 1. Server adit

`adit-agent` butuh server `adit` yang sudah punya checkpoint terlatih dan
bisa diakses (lihat `ADIT_BASE_URL`). Server ini **tidak perlu** diekspos ke
internet — cukup dijangkau dari mesin/container tempat `adit-agent` jalan.

### 2. Synology Chat — Outgoing Webhook (masuk ke adit-agent)

Di Synology Chat: **Profile → Integration → Bot → Buat Outgoing Webhook**.
- Isi URL ke: `http://<host-adit-agent>:9000/webhook/synology`
- Salin token yang digenerate ke `SYNOLOGY_OUTGOING_TOKEN`

### 3. Synology Chat — kirim balasan dari adit-agent

Ada **dua jenis integrasi** Synology Chat yang bisa dipakai untuk sisi
kirim, dan formatnya beda — pilih salah satu:

**a) Incoming Webhook polos** (paling sederhana, balasan selalu muncul di
satu channel tetap, bukan DM ke pengirim): **Profile → Integration →
Incoming Webhook → Buat webhook baru** untuk channel tujuan. Salin URL
lengkapnya (sudah termasuk `?token=...`) ke `SYNOLOGY_INCOMING_WEBHOOK_URL`,
biarkan `SYNOLOGY_REPLY_TO_USER=false` (default).

**b) URL milik Bot** (kalau kamu pakai `Bot` yang sama untuk Outgoing
Webhook di langkah 2 — Synology Chat menyebut mekanisme kirimnya
`method=chatbot`): balasan **tidak** otomatis tahu harus dikirim ke siapa —
payload wajib menyertakan `user_ids` (daftar penerima), kalau tidak,
balasan bisa tidak sampai ke siapa pun meski request-nya sukses. Salin URL
incoming milik Bot tersebut ke `SYNOLOGY_INCOMING_WEBHOOK_URL`, lalu set
`SYNOLOGY_REPLY_TO_USER=true` — `adit-agent` akan otomatis menyertakan
`user_ids: [<user_id pengirim>]` (diambil dari `user_id` di payload
Outgoing Webhook langkah 2, sama untuk kedua opsi di atas).

### 4. Konfigurasi

```bash
cp .env.example .env
# isi ADIT_BASE_URL, SYNOLOGY_OUTGOING_TOKEN, SYNOLOGY_INCOMING_WEBHOOK_URL
```

### 5. Jalankan

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 9000
```

Atau dengan Docker Compose (sekalian jalankan server `adit`, lihat
`docker-compose.yml` — sesuaikan `context: ../adit` ke lokasi repo server):

```bash
docker compose up --build
```

Kalau `adit-agent` tidak bisa dijangkau langsung dari internet publik (mis.
NAS di jaringan lokal, Synology Chat cloud perlu mencapainya), perlu
reverse-proxy/tunnel (Cloudflare Tunnel, Tailscale Funnel, dsb.) — di luar
lingkup repo ini.

## Konfigurasi (env var)

| Var | Default | Keterangan |
|---|---|---|
| `ADIT_BASE_URL` | `http://localhost:8000` | Base URL server adit |
| `ADIT_API_KEY` | *(kosong)* | Isi kalau server adit pakai `ADIT_API_KEYS` |
| `ADIT_MAX_TOKENS` | `150` | Diteruskan ke `/v1/chat/completions` |
| `ADIT_TEMPERATURE` | `0.8` | idem |
| `ADIT_TOP_K` | `20` | idem |
| `ADIT_REQUEST_TIMEOUT` | `120` (detik) | Timeout HTTP ke server adit |
| `SYNOLOGY_OUTGOING_TOKEN` | *(wajib diisi)* | Verifikasi request masuk benar dari Synology |
| `SYNOLOGY_INCOMING_WEBHOOK_URL` | *(wajib diisi)* | Tujuan kirim balasan akhir — Incoming Webhook polos atau URL Bot, lihat setup 3 |
| `SYNOLOGY_REPLY_TO_USER` | `false` | `true` kalau `SYNOLOGY_INCOMING_WEBHOOK_URL` adalah URL Bot (`method=chatbot`) — menyertakan `user_ids` di payload supaya balasan sampai ke pengirim, bukan cuma channel |
| `SYNOLOGY_VERIFY_SSL` | `true` | Matikan kalau NAS pakai sertifikat self-signed |
| `ADIT_ACK_MESSAGE` | `🤖 sedang mikir…` | Pesan instan sebelum jawaban asli menyusul |
| `ADIT_AGENT_HOST` / `ADIT_AGENT_PORT` | `0.0.0.0` / `9000` | Bind address |

## Struktur

```
adit-agent/
├── app/
│   ├── main.py             # daftar route otomatis dari CHANNELS + handler generik
│   ├── orchestrator.py       # logika inti: IncomingMessage -> ask_adit -> adapter.send_reply
│   ├── adit_client.py         # panggil /v1/chat/completions (non-stream)
│   ├── config.py                # setting INTI lintas channel (ADIT_BASE_URL dkk)
│   └── channels/
│       ├── base.py                       # kontrak ChannelAdapter + IncomingMessage + AuthError
│       ├── synology_chat_listener.py     # SynologyChatListener: verifikasi token + parse_request()
│       ├── synology_chat_bot.py          # SynologyChatBot: format payload + send_reply()
│       ├── synology.py                   # SynologyAdapter: delegasi tipis ke Listener+Bot di atas
│       └── __init__.py                   # CHANNELS = [...] <- daftarkan channel baru di sini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Menambah channel baru

Setiap channel = satu file baru yang mengimplementasikan `ChannelAdapter`
(`app/channels/base.py`) + satu baris pendaftaran di `app/channels/__init__.py`.
Tidak ada bagian lain (`main.py`, `orchestrator.py`, `adit_client.py`) yang
perlu disentuh — route webhook-nya otomatis terdaftar lewat `webhook_path`.

Kontrak yang wajib diimplementasikan:

```python
class ChannelAdapter(ABC):
    name: str            # mis. "telegram"
    webhook_path: str    # mis. "/webhook/telegram"

    async def parse_request(self, request: Request) -> IncomingMessage:
        """Verifikasi + ekstrak pesan masuk. WAJIB raise AuthError kalau
        verifikasi (token/signature) gagal."""

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        """Kirim jawaban akhir ke channel, dipanggil dari background task."""

    # opsional, override kalau perlu format berbeda dari default:
    def ack_response(self, message) -> Any: ...       # default: {}
    def reject_response(self) -> Any: ...              # default: {}
    def empty_text_response(self, message) -> Any: ...  # default: {"text": "Kirim pertanyaan dulu ya."}
```

Contoh stub Telegram (ilustrasi pola, belum diimplementasikan penuh —
Telegram Bot API pakai `getUpdates`/webhook + `sendMessage`, beda detail
verifikasi dari Synology tapi bentuk adapternya sama):

```python
# app/channels/telegram.py
import os
import httpx
from fastapi import Request
from .base import AuthError, ChannelAdapter, IncomingMessage

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")  # header X-Telegram-Bot-Api-Secret-Token

class TelegramAdapter(ChannelAdapter):
    name = "telegram"
    webhook_path = "/webhook/telegram"

    async def parse_request(self, request: Request) -> IncomingMessage:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
            raise AuthError("secret token Telegram tidak cocok")
        update = await request.json()
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", "unknown"))
        text = (msg.get("text") or "").strip()
        return IncomingMessage(
            channel=self.name,
            session_id=f"telegram:{chat_id}",
            text=text,
            user_id=chat_id,
            raw=update,
        )

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        chat_id = message.raw["message"]["chat"]["id"]
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(url, json={"chat_id": chat_id, "text": text})
```

```python
# app/channels/__init__.py
from .telegram import TelegramAdapter

CHANNELS: list[ChannelAdapter] = [
    SynologyAdapter(),
    TelegramAdapter(),
]
```

Selesai — `/webhook/telegram` otomatis terdaftar, `/healthz` otomatis
menampilkan `"telegram"` di daftar channel, dan `handle_message()` di
`orchestrator.py` bekerja sama persis untuk kedua channel tanpa modifikasi.

## Keamanan

- Token outgoing webhook diverifikasi dengan `hmac.compare_digest`
  (constant-time, tidak bocor lewat timing attack) — lihat
  `app/channels/synology_chat_listener.py`. Pola yang sama dianjurkan untuk adapter
  channel baru (verifikasi signature/secret di `parse_request()`, jangan
  pernah skip meskipun cuma untuk testing).
- Kalau token/secret channel belum dikonfigurasi di env, adapter **wajib**
  fail closed (tolak semua request) — bukan malah mengizinkan semua orang.
  Lihat `SynologyAdapter` sebagai contoh.
- `adit-agent` sendiri tidak menyimpan riwayat chat ke disk — stateless per
  request (lihat "Batasan" di bawah soal konsekuensinya).

## Batasan yang diketahui

- **Single-turn per pesan**: setiap pesan dari Synology Chat dikirim ke
  server adit sebagai satu `messages: [{role: user, content: ...}]`, TANPA
  riwayat percakapan sebelumnya (beda dari `adit-client` yang mengirim
  seluruh history tab). Alur klarifikasi (`clarification_pending` →
  `clarified`) tetap otomatis jalan karena itu di-track server-side lewat
  `session_id`, tapi percakapan umum di luar itu tidak "ingat" konteks turn
  sebelumnya. Lihat `TODO.md`.
- Belum ada rate limiting/anti-spam di level `adit-agent` sendiri (server
  adit sudah punya rate limit sendiri per API key, tapi kalau auth adit
  mati, semua request dari agent dianggap satu "klien" yang sama).
- Verifikasi end-to-end penuh (tiga proses hidup bersamaan: Synology asli →
  adit-agent → server adit) belum sempat dites di lingkungan pengembangan
  ini karena keterbatasan sandbox untuk proses latar belakang jangka
  panjang. Yang sudah diverifikasi nyata: seluruh logika `adit-agent`
  (verifikasi token, ACK, background task, format error) lewat
  `TestClient` end-to-end dengan `ask_adit`/`send_incoming_webhook` di-mock,
  ditambah satu jalur nyata (`send_incoming_webhook` betul-betul mengirim
  HTTP POST ke penerima terpisah, diverifikasi payload-nya diterima).
  **Disarankan sanity-check sekali lagi terhadap server adit & Synology
  Chat sungguhan sebelum dipakai produksi.**

Lihat `TODO.md` untuk daftar item terbuka.
