# Changelog — adit-agent

## v0.4.2 — rename istilah "channel" -> "Synology Chat" (2026-08-14)

### Diubah
- **Rename murni, tanpa perubahan perilaku**: "channel" bukan istilah yang
  dipakai dokumentasi resmi Synology Chat untuk integrasi ini, dan malah
  bentrok dengan istilah "channel" chat itu sendiri -- membingungkan saat
  mencari referensi di internet. Diganti supaya eksplisit menyebut
  "Synology Chat":
  - `app/channels/synology_channel.py` (`SynologyChannel`) → **rename**
    `app/channels/synology_chat_listener.py` (`SynologyChatListener`).
  - `app/channels/synology_bot.py` (`SynologyBot`) → **rename**
    `app/channels/synology_chat_bot.py` (`SynologyChatBot`).
  - `SynologyAdapter._channel` → `SynologyAdapter._listener` (nama atribut
    internal, tidak ada di API publik).
  - `app/channels/synology.py` (`SynologyAdapter`) dan kontrak
    `ChannelAdapter` (`app/channels/base.py`) **tidak berubah** -- rename
    ini murni di dua file internal yang didelegasikan.

### Diverifikasi
- Compile-check semua modul + regresi penuh via `TestClient` (identik
  v0.4.1): `/healthz`, token salah/benar, ACK, background task, teks
  kosong.
- `SynologyChatBot.send_reply()` diuji ulang sendirian pasca-rename
  (`SYNOLOGY_REPLY_TO_USER=true`) terhadap server HTTP lokal asli --
  payload `user_ids` masih terkirim benar, tidak ada regresi dari rename.

## v0.4.1 — dukungan user_ids untuk Bot Synology (2026-08-14)

### Ditambahkan
- **`SYNOLOGY_REPLY_TO_USER`** (default `false`): kalau
  `SYNOLOGY_INCOMING_WEBHOOK_URL` adalah URL milik sebuah **Bot** Synology
  Chat (`method=chatbot`) alih-alih "Incoming Webhook" polos yang terikat
  channel tetap, payload balasan **wajib** menyertakan `user_ids` (daftar
  penerima) atau balasan bisa tidak sampai ke siapa pun walau request
  sukses (dikonfirmasi lewat KB resmi Synology Chat Integration). Set
  `SYNOLOGY_REPLY_TO_USER=true` supaya `SynologyBot.send_reply()`
  otomatis menyertakan `"user_ids": [<user_id pengirim>]`, diambil dari
  `user_id` yang sudah ditangkap `SynologyChannel` dari payload Outgoing
  Webhook — tidak perlu env var ID tambahan. Default `false` menjaga
  perilaku identik dengan v0.4 (kompatibel dengan setup Incoming Webhook
  polos yang sudah ada).

### Diverifikasi
- **Listener (`SynologyChannel`) tidak perlu dipecah/diubah**: format
  payload Outgoing Webhook masuk sama persis terlepas dari jenis mekanisme
  kirim yang dipakai (Incoming Webhook polos vs Bot `chatbot`) — hanya
  `SynologyBot` (sender) yang perlu bercabang, dan itu digerbangi konfigurasi.
- Kedua mode (`SYNOLOGY_REPLY_TO_USER` unset/`false` vs `true`) diuji
  terhadap server HTTP lokal asli (bukan mock): mode default mengirim
  `{"text": ...}` tanpa `user_ids` (byte-identik dengan v0.4); mode `true`
  mengirim `{"text": ..., "user_ids": [<id>]}` dengan `user_id` dikonversi
  ke integer sesuai contoh resmi Synology (`user_ids: [5]`).
- Regresi penuh via `TestClient` (identik v0.4): `/healthz`, token
  salah/benar, ACK, background task.

## v0.4 — pisah channel/bot Synology (2026-08-14)

### Diubah
- **Refactor `app/channels/synology.py`**: `SynologyAdapter` dulunya satu
  class yang menggabungkan verifikasi Outgoing Webhook (listener) *dan*
  format+kirim Incoming Webhook (sender/bot) -- padahal keduanya integrasi
  Synology Chat yang sama sekali berbeda (beda halaman setting, beda token,
  beda bentuk payload; lihat tabel di `TODO.md` v0.3). Dipecah jadi tiga
  file:
  - `app/channels/synology_channel.py` — `SynologyChannel`: verifikasi
    token (`hmac.compare_digest`, fail-closed) + `parse_request()`.
  - `app/channels/synology_bot.py` — `SynologyBot`: format payload
    `application/x-www-form-urlencoded` + field `payload` (JSON string) +
    `send_reply()`.
  - `app/channels/synology.py` — `SynologyAdapter(ChannelAdapter)`: tinggal
    delegasi ke `self._channel`/`self._bot`, tidak ada logika bisnis lagi
    di sini.

  **Perilaku fungsional tidak berubah** — ini murni pemisahan level file,
  kontrak `ChannelAdapter` yang dipakai `main.py`/`orchestrator.py` sama
  persis dengan v0.3.

### Diverifikasi
- Regresi penuh lewat `TestClient` (identik v0.1–v0.3): `/healthz`
  melaporkan `channels: ["synology"]`; token salah → `200` body kosong;
  token benar → ACK instan + background task terpanggil dengan
  `session_id` benar (`synology:general:u1`); teks kosong → pesan
  pengingat, tidak memanggil `handle_message`.
- **Baru dimungkinkan oleh pemisahan ini**: `SynologyBot.send_reply()`
  diuji **sendirian** terhadap server HTTP lokal buatan sendiri (bukan
  mock) tanpa menyentuh sisi listener sama sekali — dikonfirmasi
  `Content-Type: application/x-www-form-urlencoded` dengan field `payload`
  berisi JSON string yang benar, persis format yang sempat salah di v0.3.
  Sebaliknya, `SynologyChannel.parse_request()` juga diuji sendirian
  (token benar → `IncomingMessage` dengan `session_id` benar; token salah →
  `AuthError`) tanpa menyentuh `SynologyBot` sama sekali. Ini persis
  skenario testing yang, kalau ada dari awal, kemungkinan besar membuat bug
  format payload v0.3 ketahuan lebih cepat.

## v0.3 — perbaikan format Incoming Webhook (2026-08-13)

### Diperbaiki
- **[BUG, prioritas tinggi]** `send_reply()` di `app/channels/synology.py`
  mengirim balasan dengan `Content-Type: application/json` (body JSON
  mentah) ke Incoming Webhook Synology — **format yang salah**. Dampaknya:
  balasan model **tidak pernah benar-benar muncul** di channel Synology
  Chat, meskipun tidak selalu terlihat sebagai error jelas di log.

  Format yang benar (dikonfirmasi lewat KB resmi Synology + beberapa sumber
  independen yang konsisten): `Content-Type:
  application/x-www-form-urlencoded` dengan satu field bernama **`payload`**
  yang isinya *string* JSON, bukan body JSON langsung.

  ```python
  # sebelum (salah)
  await client.post(url, json={"text": text})

  # sesudah (benar)
  form_data = {"payload": json.dumps({"text": text}, ensure_ascii=False)}
  await client.post(url, data=form_data)
  ```

### Diverifikasi
- Byte yang benar-benar dikirim di kabel dicek langsung lewat server
  penerima buatan sendiri (bukan cuma percaya dokumentasi/asumsi):
  `Content-Type: application/x-www-form-urlencoded`, body
  `payload=%7B%22text%22...%7D`, di-parse ulang jadi
  `{'text': 'halo dari test'}` — cocok persis format yang didokumentasikan.
- Regresi penuh lewat `TestClient` (sama seperti v0.2): `/healthz`, token
  salah/benar, ACK, background task, teks kosong — semua masih identik,
  bugfix ini tidak mengubah perilaku bagian lain.

## v0.2 — arsitektur adapter per channel (2026-08-13)

Refactor supaya `adit-agent` siap ditambah integrasi lain (Telegram, Slack,
dst) di masa depan tanpa mengubah kode inti.

### Ditambahkan
- `app/channels/base.py` — kontrak `ChannelAdapter` (ABC): `parse_request()`
  (wajib raise `AuthError` kalau verifikasi gagal), `send_reply()`, plus
  method opsional `ack_response()`/`reject_response()`/`empty_text_response()`
  dengan default masuk akal. `IncomingMessage` dataclass sebagai bentuk pesan
  yang sudah dinormalisasi lintas channel.
- `app/channels/__init__.py` — registry `CHANNELS: list[ChannelAdapter]`,
  satu-satunya tempat channel baru perlu didaftarkan.
- `app/orchestrator.py` — `handle_message()`: logika generik "terima pesan
  -> panggil adit -> kirim balasan lewat adapter", dipisah dari `main.py`
  supaya bisa dites/dipakai ulang lepas dari detail HTTP routing.
- `app/main.py` — `_make_webhook_handler()` generik + loop registrasi route
  otomatis dari `CHANNELS` (pakai `webhook_path` tiap adapter). `/healthz`
  sekarang menampilkan daftar channel aktif.
- `README.md` — bagian baru "Menambah channel baru" dengan contoh stub
  `TelegramAdapter` lengkap sebagai pola referensi.

### Diubah
- `app/synology.py` (lama, fungsi lepas) dipindah & dibungkus jadi
  `app/channels/synology.py` (`SynologyAdapter`, class). Perilaku fungsional
  **tidak berubah** — verifikasi token, format ACK, pengiriman incoming
  webhook, semuanya identik dengan v0.1, cuma dibungkus ulang jadi metode
  `ChannelAdapter`.
- `app/config.py` ditrim jadi cuma setting inti lintas channel
  (`ADIT_BASE_URL`, dst). Setting spesifik Synology
  (`SYNOLOGY_OUTGOING_TOKEN`, `SYNOLOGY_INCOMING_WEBHOOK_URL`,
  `SYNOLOGY_VERIFY_SSL`) sekarang dibaca sendiri di dalam
  `app/channels/synology.py` supaya tiap channel self-contained. Nama env
  var **tidak berubah**, `.env.example` tetap sama.

### Diverifikasi
- Compile-check semua modul (`app/*.py`, `app/channels/*.py`).
- Route `/webhook/synology` terkonfirmasi terdaftar otomatis dari `CHANNELS`
  (bukan hardcoded di `main.py` lagi) lewat inspeksi `app.routes`.
- Regresi fungsional penuh lewat `TestClient` dengan `ask_adit`/
  `SynologyAdapter.send_reply` di-mock: `/healthz` melaporkan
  `channels: ["synology"]`; token salah → `200` body kosong (sama seperti
  v0.1); token benar → ACK instan + background task terpanggil dengan
  `session_id` yang benar; teks kosong → pesan pengingat. Semua hasil identik
  dengan perilaku v0.1 sebelum refactor.

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
