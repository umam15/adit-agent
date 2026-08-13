# adit-agent

Jembatan (bot) antara **Synology Chat** dan server **adit**
(`/v1/chat/completions`). Repo terpisah dari `adit-client` karena perannya
beda kelas: `adit-client` jalan di browser orang, `adit-agent` adalah server
yang harus terus hidup mendengarkan webhook masuk dari Synology.

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

### 3. Synology Chat — Incoming Webhook (balasan dari adit-agent)

**Profile → Integration → Incoming Webhook → Buat webhook baru** untuk
channel tujuan. Salin URL lengkapnya (sudah termasuk `?token=...`) ke
`SYNOLOGY_INCOMING_WEBHOOK_URL`.

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
| `SYNOLOGY_INCOMING_WEBHOOK_URL` | *(wajib diisi)* | Tujuan kirim balasan akhir |
| `SYNOLOGY_VERIFY_SSL` | `true` | Matikan kalau NAS pakai sertifikat self-signed |
| `ADIT_ACK_MESSAGE` | `🤖 sedang mikir…` | Pesan instan sebelum jawaban asli menyusul |
| `ADIT_AGENT_HOST` / `ADIT_AGENT_PORT` | `0.0.0.0` / `9000` | Bind address |

## Struktur

```
adit-agent/
├── app/
│   ├── main.py          # endpoint webhook, ACK + background task
│   ├── adit_client.py    # panggil /v1/chat/completions (non-stream)
│   ├── synology.py        # verifikasi token + kirim incoming webhook
│   └── config.py           # semua konfigurasi via env var
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Keamanan

- Token outgoing webhook diverifikasi dengan `hmac.compare_digest`
  (constant-time, tidak bocor lewat timing attack) — lihat `app/synology.py`.
- Kalau `SYNOLOGY_OUTGOING_TOKEN` belum diisi di env, **semua request
  ditolak** (fail closed), bukan malah mengizinkan semua orang.
- `adit-agent` sendiri tidak menyimpan riwayat chat ke disk — statless per
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
