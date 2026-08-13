# Changelog — adit-agent

## v0.1 — rilis awal (2026-08-13)

Repo baru, terpisah dari `adit-client`: jembatan antara Synology Chat dan
server `adit` (`/v1/chat/completions`).

### Ditambahkan
- `app/main.py` — endpoint `POST /webhook/synology` (outgoing webhook
  Synology Chat): verifikasi token, balas ACK instan (`{"text": "..."}`),
  proses jawaban di background task supaya tidak menahan respons webhook
  (Synology Chat butuh respons cepat, generate model di CPU bisa lama).
  `GET /healthz` untuk monitoring.
- `app/synology.py` — `verify_token()` (constant-time compare, fail closed
  kalau token belum dikonfigurasi), `send_incoming_webhook()` (kirim
  balasan akhir sebagai pesan baru lewat Incoming Webhook URL).
- `app/adit_client.py` — `ask_adit()`: panggil `/v1/chat/completions` server
  adit selalu **non-streaming** (rasional: Synology Chat tidak punya API
  edit-pesan-berkelanjutan, jadi streaming token-per-token tidak ada
  gunanya di sini), terjemahkan status error (400/401/429/503) jadi pesan
  ramah berbahasa Indonesia, tandai balasan `clarification_pending` dengan
  emoji ❓.
- `app/config.py` — semua konfigurasi lewat env var, lihat `.env.example`.
- `session_id` dibentuk dari `synology:<channel_name>:<user_id>`, selaras
  dengan alur klarifikasi otomatis server adit yang di-track per
  `session_id` (jawaban atas klarifikasi otomatis diproses lewat mekanisme
  server yang sudah ada, tidak perlu logika tambahan di agent).
- `Dockerfile` + `docker-compose.yml` — jalankan `adit-agent` + server adit
  bersamaan, server adit tidak perlu diekspos ke internet, cukup
  `adit-agent` yang publik-facing untuk menerima webhook.
- `README.md`, `TODO.md` — dokumentasi setup Synology Chat (Outgoing +
  Incoming Webhook), tabel konfigurasi, rasional desain, batasan yang
  diketahui.

### Diverifikasi
- Seluruh logika `app/main.py` lewat `TestClient` (mock `ask_adit` &
  `send_incoming_webhook`): token salah → ditolak (`200` dengan body kosong,
  tidak membocorkan detail kegagalan auth ke chat); token benar → ACK instan
  + background task terpanggil dengan `session_id` yang benar
  (`synology:general:u1`); teks kosong → pesan pengingat, tidak memanggil
  model; `/healthz` → `200`.
- `send_incoming_webhook()` diverifikasi benar-benar mengirim HTTP POST
  nyata ke server penerima terpisah (bukan mock) — payload `{"text": ...}`
  diterima dan dicocokkan.
- Bentuk request `/v1/chat/completions` yang dikirim `ask_adit()`
  (field `model`, `messages`, `max_tokens`, `temperature`, `top_k`,
  `session_id`, `stream: false`) sama persis dengan yang sudah berkali-kali
  diverifikasi bekerja terhadap server adit v0.6 & v1.0-beta1 sepanjang
  pengembangan `adit-client`.

### Belum diverifikasi
- Live end-to-end penuh (Synology Chat asli → adit-agent → server adit
  sungguhan, tiga proses hidup bersamaan) — terkendala keterbatasan sandbox
  untuk proses latar belakang jangka panjang di lingkungan pengembangan ini.
  Lihat `TODO.md` poin pertama.
