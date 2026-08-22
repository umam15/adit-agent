# Arsitektur adit-agent

Dokumen ini untuk pengembang yang ingin memahami/mengubah kode adit-agent
— kalau kamu cuma ingin memakainya (tambah agent chat, dst), cukup baca
`README.md` di root repo dan buka panel `/admin`.

## Alur pesan

```
Synology Chat --(outgoing webhook, form-urlencoded)--> adit-agent
adit-agent    --(balas ACK instan, JSON)--------------> Synology Chat (langsung, sinkron)
adit-agent    --(POST /v1/chat/completions, non-stream)-> server adit
adit-agent    --(incoming webhook, setelah selesai)----> Synology Chat (async, pesan baru)
```

**Kenapa ACK instan + async, bukan sinkron langsung:** outgoing webhook
Synology Chat butuh respons cepat di request itu sendiri. Model `adit`
jalan di CPU dan generate token demi token bisa berdurasi lebih lama dari
timeout webhook, apalagi dengan `max_tokens` besar — kalau ditunggu
sinkron, UI Synology Chat bisa macet di "Processing...". Jadi `adit-agent`
langsung balas pesan ACK (`ADIT_ACK_MESSAGE`), lalu generate di background
dan kirim jawaban aslinya sebagai pesan **baru** lewat Incoming Webhook
begitu selesai.

**Kenapa non-streaming, bukan streaming token-per-token:** Synology Chat
tidak menyediakan API publik untuk mengedit pesan yang sudah terkirim
(beda dari Slack `chat.update`), jadi tidak ada tempat berlabuh yang wajar
untuk menampilkan token yang muncul bertahap. `adit-agent` menunggu server
`adit` selesai generate penuh (`stream: false`), baru mengirim satu pesan.

## Struktur

```
adit-agent/
├── app/
│   ├── main.py             # webhook_dispatch dinamis (satu route, lookup DB per request) + mount /admin + /api/agents
│   ├── orchestrator.py      # logika inti: IncomingMessage -> ask_adit -> adapter.send_reply
│   ├── adit_client.py       # panggil /v1/chat/completions (non-stream)
│   ├── config.py            # setting INTI lintas channel (ADIT_BASE_URL dkk) -- level admin/server
│   ├── store.py             # penyimpanan agent (kredensial terenkripsi) -- diisi lewat /admin
│   ├── api_admin.py         # router GET/POST/PATCH/DELETE /api/agents + tes koneksi
│   ├── web/
│   │   └── index.html       # panel admin (disajikan di /admin), murni HTML+JS, fetch ke /api/agents
│   └── channels/
│       ├── base.py                       # kontrak ChannelAdapter + IncomingMessage + AuthError
│       ├── synology_chat_listener.py     # SynologyChatListener: verifikasi token + parse_request()
│       ├── synology_chat_bot.py          # SynologyChatBot: format payload + send_reply() + test_connection()
│       ├── synology.py                   # SynologyAdapter: delegasi tipis ke Listener+Bot di atas
│       └── __init__.py                   # load_channels(): baca agent aktif dari store.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Kredensial channel murni dari database, bukan env var

Sejak v0.4.4, satu-satunya tempat mengisi kredensial per-agent (token,
URL webhook, dst) adalah panel `/admin` → tersimpan terenkripsi
(`app/store.py`, Fernet) di database SQLite. Env var di adit-agent sekarang
khusus untuk setting admin/server: koneksi ke server `adit`, key enkripsi
database (`ADIT_AGENT_SECRET_KEY`), token akses panel admin, dan bind
address. Lihat `.env.example` untuk daftar lengkapnya.

Konsekuensi penting: **`ADIT_AGENT_SECRET_KEY` wajib diisi** supaya
adit-agent bisa start sama sekali (lihat `app/channels/__init__.py`) —
kalau belum, proses akan berhenti dengan pesan error yang jelas, bukan
fallback diam-diam ke perilaku lama.

**Webhook dispatch dinamis -- tidak perlu restart setelah menambah/mengubah
agent lewat UI (sejak v0.4.5):** `app/main.py` cuma punya SATU route
(`webhook_dispatch`, pola `POST /webhook/{platform}/{slug}`) yang lookup
agent dari database per request (`store.get_agent_by_webhook_path()`),
bukan route statis per agent yang dihitung sekali saat startup. Jadi
create/update/delete/toggle agent lewat panel `/admin` langsung live.
Restart proses cuma masih relevan untuk perubahan level infra (env var
murni: `ADIT_AGENT_HOST`, `ADIT_AGENT_PORT`, `ADIT_AGENT_SECRET_KEY`,
`ADIT_AGENT_DB_PATH`), bukan untuk kelola agent.

## Menambah JENIS channel baru (bukan instance baru dari yang sudah ada)

Setiap channel = satu file baru yang mengimplementasikan `ChannelAdapter`
(`app/channels/base.py`) + didaftarkan di `_PLATFORM_ADAPTERS`
(`app/channels/__init__.py`) dan `_WEBHOOK_PREFIX` (`app/api_admin.py`).
Tidak ada bagian lain (`main.py`, `orchestrator.py`, `adit_client.py`) yang
perlu disentuh — route webhook otomatis terdaftar lewat `webhook_path`
tiap agent yang tersimpan di database.

Kontrak yang wajib diimplementasikan:

```python
class ChannelAdapter(ABC):
    name: str            # unik per instance -- prefix session_id & logging
    webhook_path: str    # unik per instance -- di-generate otomatis oleh api_admin.py

    async def parse_request(self, request: Request) -> IncomingMessage:
        """Verifikasi + ekstrak pesan masuk. WAJIB raise AuthError kalau
        verifikasi (token/signature) gagal."""

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        """Kirim jawaban akhir ke channel, dipanggil dari background task."""

    # opsional, override kalau perlu format berbeda dari default:
    def ack_response(self, message) -> Any: ...       # default: {}
    def reject_response(self) -> Any: ...              # default: {}
    def empty_text_response(self, message) -> Any: ...  # default: {"text": "Kirim pertanyaan dulu ya."}
    async def test_connection(self) -> tuple[bool, str]: ...  # default: (False, "belum didukung")
```

Contoh stub Telegram (ilustrasi pola, belum diimplementasikan penuh —
Telegram Bot API pakai webhook + `sendMessage`, beda detail verifikasi
dari Synology tapi bentuk adapternya sama):

```python
# app/channels/telegram.py
import httpx
from fastapi import Request
from .base import AuthError, ChannelAdapter, IncomingMessage

class TelegramAdapter(ChannelAdapter):
    def __init__(self, agent_id="telegram", display_name="Telegram",
                 webhook_path="/webhook/telegram", config=None):
        config = config or {}
        self.name = agent_id
        self.display_name = display_name
        self.webhook_path = webhook_path
        self.bot_token = config.get("bot_token", "")
        self.webhook_secret = config.get("webhook_secret", "")

    async def parse_request(self, request: Request) -> IncomingMessage:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != self.webhook_secret:
            raise AuthError("secret token Telegram tidak cocok")
        update = await request.json()
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", "unknown"))
        text = (msg.get("text") or "").strip()
        return IncomingMessage(
            channel=self.name, session_id=f"{self.name}:{chat_id}",
            text=text, user_id=chat_id, raw=update,
        )

    async def send_reply(self, message: IncomingMessage, text: str) -> None:
        chat_id = message.raw["message"]["chat"]["id"]
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(url, json={"chat_id": chat_id, "text": text})
```

```python
# app/channels/__init__.py
from .telegram import TelegramAdapter

_PLATFORM_ADAPTERS = {
    "synology_chat": SynologyAdapter,
    "synology_bot": SynologyAdapter,
    "telegram": TelegramAdapter,
}
```

```python
# app/api_admin.py
_WEBHOOK_PREFIX = {"synology_chat": "synology", "synology_bot": "synology", "telegram": "telegram"}
```

Selesai — begitu ada agent bertipe `"telegram"` tersimpan aktif di
database, route webhook-nya langsung live (dispatch dinamis, tidak perlu
restart), `/healthz` otomatis menampilkannya di daftar channel, dan
`handle_message()` di `orchestrator.py` bekerja sama persis untuk semua
channel tanpa modifikasi.

Tambahkan juga entri `PLATFORMS.telegram` di `app/web/index.html` (field
kredensial apa saja yang perlu diminta panel) supaya UI-nya ikut mendukung.

## Keamanan

- Token outgoing webhook diverifikasi dengan `hmac.compare_digest`
  (constant-time, tidak bocor lewat timing attack) — lihat
  `app/channels/synology_chat_listener.py`. Pola yang sama dianjurkan untuk
  adapter channel baru.
- Kalau token/secret channel belum diisi lewat panel admin, adapter
  **wajib** fail closed (tolak semua request) — bukan malah mengizinkan
  semua orang. Lihat `SynologyChatListener._verify_token()`.
- Kredensial disimpan terenkripsi di database (`app/store.py`, Fernet),
  key-nya (`ADIT_AGENT_SECRET_KEY`) terpisah dari file database.
- `/api/agents/*` bisa dikunci dengan token (`ADIT_AGENT_ADMIN_TOKEN`) —
  sangat disarankan diisi begitu adit-agent bisa dijangkau dari luar
  jaringan lokal terpercaya.
- `adit-agent` sendiri tidak menyimpan riwayat chat ke disk — stateless
  per request (lihat "Batasan yang diketahui" di bawah soal konsekuensinya).

## Batasan yang diketahui

- **Single-turn per pesan**: setiap pesan dikirim ke server adit sebagai
  satu `messages: [{role: user, content: ...}]`, TANPA riwayat percakapan
  sebelumnya. Alur klarifikasi (`clarification_pending` → `clarified`)
  tetap otomatis jalan karena itu di-track server-side lewat `session_id`,
  tapi percakapan umum di luar itu tidak "ingat" konteks turn sebelumnya.
  Lihat `TODO.md`.
- Belum ada rate limiting/anti-spam di level `adit-agent` sendiri.
- Verifikasi end-to-end penuh (tiga proses hidup bersamaan: Synology asli
  → adit-agent → server adit) belum sempat dites di lingkungan
  pengembangan awal karena keterbatasan sandbox untuk proses latar
  belakang jangka panjang. **Disarankan sanity-check sekali lagi terhadap
  server adit & Synology Chat sungguhan sebelum dipakai produksi** — pakai
  tombol "Tes koneksi" di panel admin sebagai langkah pertama.

Lihat `TODO.md` untuk daftar item terbuka dan `CHANGELOG.md` untuk riwayat
perubahan tiap versi.
