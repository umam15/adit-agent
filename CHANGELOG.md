# Changelog

Semua perubahan penting pada proyek `adit-agent` didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
dan proyek ini mengikuti [Semantic Versioning](https://semver.org/lang/id/).
Selama masih `0.x.y`, API/konfigurasi bisa berubah tanpa pemberitahuan di
setiap rilis minor.

## [Unreleased]

## [0.4.5] - 2026-08-22

Rilis ini merespons `docs/laporan/LAPORAN-MASALAH-ADIT-AGENT-20260822.md`
(pengujian penerapan 0.4.4, termasuk verifikasi end-to-end ke Synology Chat
sungguhan) dan diskusi desain arsitektur lanjutan.

### Fixed — KRITIS
- **`synology_bot` gagal senyap tanpa `reply_to_user`** (laporan M3): payload
  ke URL Bot Synology (`method=chatbot`) wajib menyertakan `user_ids`, tapi
  sebelumnya tidak ada jalur apa pun yang membuat `reply_to_user` bernilai
  `true` secara otomatis untuk platform ini -- request tetap sukses (HTTP
  200) tapi pesan tidak sampai ke siapa pun. `reply_to_user` sekarang
  **di-hardcode `true`** di `SynologyAdapter.__init__` (`app/channels/synology.py`,
  `_FORCE_REPLY_TO_USER`) begitu `platform == "synology_bot"` -- override,
  bukan default, jadi tetap benar walau ada baris lama di database yang
  eksplisit menyimpan `false`. Berlaku juga untuk endpoint "Tes koneksi"
  (`app/api_admin.py` sebelumnya tidak meneruskan `platform` sama sekali ke
  adapter tes -- ikut diperbaiki, lihat "Changed" di bawah).
- **Normalisasi `user_id`** (laporan M4, potensi): Synology Chat pada
  beberapa kondisi mengirim `user_id` sebagai string JSON-array (`'["8"]'`)
  alih-alih angka polos. `int(message.user_id)` langsung sebelumnya gagal
  senyap untuk kasus ini (`ValueError` tertangkap, fallback tanpa
  `user_ids` -- gejala identik bug di atas). `_normalize_user_id()` baru
  (`app/channels/synology_chat_bot.py`) menerima `8`, `"8"`, `'["8"]'`,
  `["8"]`, `[8]`.
- **Toggle Aktif tidak ada di alur "Tambah agent"** (laporan M2): endpoint
  `POST /api/agents` default `active=false` tapi modal "Tambah agent"
  (`app/web/index.html`) sebelumnya tidak punya kontrol untuk mengubahnya
  saat create -- ditambahkan toggle "Aktifkan begitu disimpan" di modal.

### Added
- **Webhook dispatch dinamis** -- mengganti kebutuhan restart proses untuk
  operasi agent, bukan cuma memberi tombol untuk itu. `app/main.py` sekarang
  cuma punya SATU route (`webhook_dispatch`, pola
  `POST /webhook/{platform}/{slug}`) yang lookup agent dari database per
  request (`store.get_agent_by_webhook_path()`, baru), bukan route statis
  per adapter yang didaftarkan sekali saat startup. Konsekuensi:
  create/update/delete/toggle agent lewat panel `/admin` **langsung live**,
  tanpa restart sama sekali. `/healthz` juga query database fresh tiap
  dipanggil (bukan baca list statis).
- `app/channels/build_adapter()` -- fungsi bersama untuk membangun satu
  instance adapter dari `AgentRecord`, dipakai `load_channels()`,
  `webhook_dispatch` (`app/main.py`), dan endpoint tes koneksi
  (`app/api_admin.py`) -- sebelumnya tiga tempat ini punya logika
  instansiasi adapter yang sedikit berbeda-beda (jadi sumber bug
  `reply_to_user` di atas tidak konsisten diperbaiki di endpoint tes).

### Changed
- Field `"restart_required"` di respons `POST`/`PATCH /api/agents/*`
  dihapus -- sudah tidak relevan sejak webhook dispatch dinamis. Banner
  restart di panel admin juga dihapus.
- `SynologyAdapter.__init__` terima parameter baru `platform` (default
  `"synology_chat"`, backward-compatible).
- `app/channels/__init__.py`: `_PLATFORM_ADAPTERS`/loop instansiasi adapter
  dipindah ke `build_adapter()` (lihat "Added").

### Docs
- `docs/architecture.md`, `docs/channels/synology-chat.md`, `README.md`:
  hapus semua instruksi "restart setelah tambah/ubah agent" yang sudah
  tidak berlaku.
- Laporan pengujian disalin ke `docs/laporan/` (data sensitif -- domain NAS
  asli, token webhook yang tidak sengaja tidak ter-redaksi, nama pengguna --
  sudah dihapus/diganti placeholder sebelum disalin).

### Dipertimbangkan, sengaja TIDAK dikerjakan
Lihat `TODO.md` bagian "Tidak akan dikerjakan" untuk desain yang
dipertimbangkan tapi sengaja tidak diambil di rilis ini (edit admin token
dari UI, halaman "Pengaturan" generik) beserta alasannya -- ringkasnya:
kredensial admin sebaiknya tetap di layer infra (env var), terpisah dari
sistem yang dia lindungi; setting yang butuh restart (host/port) sebaiknya
tidak dibuat UI-editable karena menciptakan ekspektasi salah.

## [0.4.4] - 2026-08-22

### Added
- **Panel admin di `/admin`** (`app/web/index.html`, disajikan langsung
  oleh adit-agent lewat `StaticFiles`): tambah/lihat/ubah/hapus agent chat
  dari browser, termasuk kredensial (token, URL webhook), toggle
  aktif/nonaktif, dan tombol "Tes koneksi" yang mengirim pesan uji
  sungguhan sebelum agent diaktifkan.
- `app/api_admin.py`: router `GET/POST/PATCH/DELETE /api/agents` +
  `POST /api/agents/{id}/test`, dipakai panel admin di atas. Bisa dikunci
  dengan `ADIT_AGENT_ADMIN_TOKEN` (opsional, bearer token).
- `app/store.py`: penyimpanan agent (SQLite) dengan kredensial terenkripsi
  (Fernet, key dari `ADIT_AGENT_SECRET_KEY`) — menggantikan `.env` sebagai
  tempat mengisi kredensial per-channel.
- **Multi-instance per platform**: sekarang bisa memasang lebih dari satu
  Synology Chat/Bot/Telegram sekaligus, masing-masing dengan kredensial
  dan `webhook_path` sendiri (`SynologyAdapter`/`SynologyChatListener`/
  `SynologyChatBot` menerima `config` dict per-instance, `channel_id`
  dipakai sebagai prefix `session_id` supaya riwayat percakapan dua
  instance tidak numpuk).
- `test_connection()` (opsional per adapter, `app/channels/base.py`) —
  dipakai tombol "Tes koneksi", terpisah dari `send_reply()` supaya tidak
  mengubah perilaku pengiriman pesan normal.
- CORS opsional (`ADIT_AGENT_UI_ORIGINS`) untuk kasus panel admin di-hosting
  terpisah dari adit-agent sendiri.
- Dokumentasi teknis dipindah ke `docs/architecture.md` dan
  `docs/channels/synology-chat.md`, README utama ditulis ulang untuk
  pengguna non-teknis (fokus: cara pakai panel admin).

### Changed — BREAKING
- **Kredensial channel (Synology Chat/Bot) TIDAK LAGI dibaca dari env
  var.** `SYNOLOGY_OUTGOING_TOKEN`, `SYNOLOGY_INCOMING_WEBHOOK_URL`,
  `SYNOLOGY_REPLY_TO_USER`, `SYNOLOGY_VERIFY_SSL` semuanya dihapus dari
  `.env.example` — isi ulang lewat panel `/admin` setelah upgrade. Env var
  di adit-agent sekarang khusus setting admin/server (`ADIT_BASE_URL`,
  `ADIT_AGENT_SECRET_KEY`, dst).
- `ADIT_AGENT_SECRET_KEY` sekarang **wajib** diisi — adit-agent tidak akan
  start tanpanya (`app/channels/__init__.py` sengaja membiarkan
  `SecretKeyMissing` menjalar ke atas, bukan fallback diam-diam), supaya
  kegagalan konfigurasinya eksplisit sejak awal, bukan berupa "channel
  tidak jalan" yang membingungkan belakangan.
- `app/channels/__init__.py`: `CHANNELS` sekarang murni dari agent aktif di
  database (diisi lewat panel admin), bukan list hardcode. Kalau belum ada
  agent, `CHANNELS` kosong dan adit-agent tetap start normal — `/admin`
  tetap bisa dibuka untuk menambah agent pertama.

### Migrasi dari 0.4.3
1. `pip install -r requirements.txt` (`cryptography` baru ditambahkan).
2. Generate `ADIT_AGENT_SECRET_KEY` (lihat `.env.example`), isi sebagai env
   var permanen.
3. Jalankan adit-agent, buka `/admin`, tambah ulang agent Synology Chat
   kamu dengan token/URL yang sama seperti di `.env` lama.
4. Hapus `SYNOLOGY_*` dari `.env` (sudah tidak dipakai).
5. Restart adit-agent supaya webhook agent yang baru ditambah aktif.

## [0.4.2] - 2026-08-14

### Changed
- Rename istilah "channel" → "Synology Chat" di sisi listener (murni
  rename, tanpa perubahan perilaku): "channel" bukan istilah yang dipakai
  dokumentasi resmi Synology Chat untuk integrasi ini, dan malah bentrok
  dengan istilah "channel" chat itu sendiri — membingungkan saat mencari
  referensi di internet.
  - `app/channels/synology_channel.py` (`SynologyChannel`) → `app/channels/synology_chat_listener.py` (`SynologyChatListener`)
  - `app/channels/synology_bot.py` (`SynologyBot`) → `app/channels/synology_chat_bot.py` (`SynologyChatBot`)
  - `SynologyAdapter._channel` → `SynologyAdapter._listener` (atribut internal, bukan API publik)
  - `app/channels/synology.py` (`SynologyAdapter`) dan kontrak `ChannelAdapter` (`app/channels/base.py`) **tidak berubah**.
  - Diverifikasi: compile-check semua modul + regresi penuh via `TestClient`
    (identik 0.4.1: `/healthz`, token salah/benar, ACK, background task,
    teks kosong); `SynologyChatBot.send_reply()` diuji ulang sendirian
    pasca-rename (`SYNOLOGY_REPLY_TO_USER=true`) ke server HTTP lokal asli
    — payload `user_ids` tetap terkirim benar.

## [0.4.1] - 2026-08-14

### Added
- Env var `SYNOLOGY_REPLY_TO_USER` (default `false`): kalau
  `SYNOLOGY_INCOMING_WEBHOOK_URL` adalah URL milik sebuah **Bot** Synology
  Chat (`method=chatbot`) alih-alih "Incoming Webhook" polos yang terikat
  channel tetap, payload balasan **wajib** menyertakan `user_ids` (daftar
  penerima) atau balasan bisa tidak sampai ke siapa pun walau request
  sukses (dikonfirmasi lewat KB resmi Synology Chat Integration). Set
  `true` supaya `SynologyBot.send_reply()` otomatis menyertakan
  `"user_ids": [<user_id pengirim>]`, diambil dari `user_id` yang sudah
  ditangkap `SynologyChannel` dari payload Outgoing Webhook — tidak perlu
  env var ID tambahan. Default `false` menjaga perilaku identik dengan
  0.4.0 (kompatibel dengan setup Incoming Webhook polos yang sudah ada).
  - Diverifikasi: kedua mode diuji ke server HTTP lokal asli (bukan mock)
    — default mengirim `{"text": ...}` tanpa `user_ids` (byte-identik
    dengan 0.4.0); `true` mengirim `{"text": ..., "user_ids": [<id>]}`
    dengan `user_id` dikonversi ke integer sesuai contoh resmi Synology
    (`user_ids: [5]`). Listener (`SynologyChannel`) tidak perlu ikut
    diubah — formatnya sama untuk kedua mode kirim. Regresi penuh via
    `TestClient` (identik 0.4.0) tetap hijau.

## [0.4.0] - 2026-08-14

### Changed
- Refactor `app/channels/synology.py`: `SynologyAdapter` dulunya satu
  class yang menggabungkan verifikasi Outgoing Webhook (listener) *dan*
  format+kirim Incoming Webhook (sender/bot) — padahal keduanya integrasi
  Synology Chat yang sama sekali berbeda (beda halaman setting, beda
  token, beda bentuk payload). Dipecah jadi tiga file:
  - `app/channels/synology_channel.py` — `SynologyChannel`: verifikasi
    token (`hmac.compare_digest`, fail-closed) + `parse_request()`.
  - `app/channels/synology_bot.py` — `SynologyBot`: format payload
    `application/x-www-form-urlencoded` + field `payload` (JSON string) +
    `send_reply()`.
  - `app/channels/synology.py` — `SynologyAdapter(ChannelAdapter)`:
    tinggal delegasi ke `self._channel`/`self._bot`, tidak ada logika
    bisnis lagi di sini.

  Perilaku fungsional tidak berubah — ini murni pemisahan level file,
  kontrak `ChannelAdapter` yang dipakai `main.py`/`orchestrator.py` sama
  persis dengan 0.3.0.
  - Diverifikasi: regresi penuh lewat `TestClient` (identik 0.1.0–0.3.0):
    `/healthz` melaporkan `channels: ["synology"]`; token salah → `200`
    body kosong; token benar → ACK instan + background task terpanggil
    dengan `session_id` benar (`synology:general:u1`); teks kosong →
    pesan pengingat, tidak memanggil `handle_message`. Baru dimungkinkan
    oleh pemisahan ini: `SynologyBot.send_reply()` diuji **sendirian**
    terhadap server HTTP lokal buatan sendiri (bukan mock) tanpa
    menyentuh sisi listener sama sekali — dikonfirmasi
    `Content-Type: application/x-www-form-urlencoded` dengan field
    `payload` berisi JSON string yang benar, persis format yang sempat
    salah di 0.3.0. Sebaliknya, `SynologyChannel.parse_request()` juga
    diuji sendirian (token benar → `IncomingMessage` dengan `session_id`
    benar; token salah → `AuthError`) tanpa menyentuh `SynologyBot` sama
    sekali.

## [0.3.0] - 2026-08-13

### Fixed
- **[Bug, prioritas tinggi]** `send_reply()` di `app/channels/synology.py`
  mengirim balasan dengan `Content-Type: application/json` (body JSON
  mentah) ke Incoming Webhook Synology — format yang salah. Dampaknya:
  balasan model **tidak pernah benar-benar muncul** di channel Synology
  Chat, meskipun tidak selalu terlihat sebagai error jelas di log.

  Format yang benar (dikonfirmasi lewat KB resmi Synology + beberapa
  sumber independen yang konsisten): `Content-Type:
  application/x-www-form-urlencoded` dengan satu field bernama `payload`
  yang isinya *string* JSON, bukan body JSON langsung.

  ```python
  # sebelum (salah)
  await client.post(url, json={"text": text})

  # sesudah (benar)
  form_data = {"payload": json.dumps({"text": text}, ensure_ascii=False)}
  await client.post(url, data=form_data)
  ```
  - Diverifikasi: byte yang benar-benar dikirim di kabel dicek langsung
    lewat server penerima buatan sendiri (bukan cuma percaya
    dokumentasi/asumsi): `Content-Type: application/x-www-form-urlencoded`,
    body `payload=%7B%22text%22...%7D`, di-parse ulang jadi
    `{'text': 'halo dari test'}` — cocok persis format yang
    didokumentasikan. Regresi penuh lewat `TestClient` (sama seperti
    0.2.0): `/healthz`, token salah/benar, ACK, background task, teks
    kosong — semua masih identik, bugfix ini tidak mengubah perilaku
    bagian lain.

## [0.2.0] - 2026-08-13

Refactor supaya `adit-agent` siap ditambah integrasi lain (Telegram,
Slack, dst) di masa depan tanpa mengubah kode inti.

### Added
- `app/channels/base.py` — kontrak `ChannelAdapter` (ABC):
  `parse_request()` (wajib raise `AuthError` kalau verifikasi gagal),
  `send_reply()`, plus method opsional
  `ack_response()`/`reject_response()`/`empty_text_response()` dengan
  default masuk akal. `IncomingMessage` dataclass sebagai bentuk pesan
  yang sudah dinormalisasi lintas channel.
- `app/channels/__init__.py` — registry `CHANNELS: list[ChannelAdapter]`,
  satu-satunya tempat channel baru perlu didaftarkan.
- `app/orchestrator.py` — `handle_message()`: logika generik "terima
  pesan -> panggil adit -> kirim balasan lewat adapter", dipisah dari
  `main.py` supaya bisa dites/dipakai ulang lepas dari detail HTTP
  routing.
- `app/main.py` — `_make_webhook_handler()` generik + loop registrasi
  route otomatis dari `CHANNELS` (pakai `webhook_path` tiap adapter).
  `/healthz` sekarang menampilkan daftar channel aktif.
- `README.md` — bagian baru "Menambah channel baru" dengan contoh stub
  `TelegramAdapter` lengkap sebagai pola referensi.

### Changed
- `app/synology.py` (lama, fungsi lepas) dipindah & dibungkus jadi
  `app/channels/synology.py` (`SynologyAdapter`, class). Perilaku
  fungsional **tidak berubah** — verifikasi token, format ACK, pengiriman
  incoming webhook, semuanya identik dengan 0.1.0, cuma dibungkus ulang
  jadi metode `ChannelAdapter`.
- `app/config.py` ditrim jadi cuma setting inti lintas channel
  (`ADIT_BASE_URL`, dst). Setting spesifik Synology
  (`SYNOLOGY_OUTGOING_TOKEN`, `SYNOLOGY_INCOMING_WEBHOOK_URL`,
  `SYNOLOGY_VERIFY_SSL`) sekarang dibaca sendiri di dalam
  `app/channels/synology.py` supaya tiap channel self-contained. Nama env
  var **tidak berubah**, `.env.example` tetap sama.
  - Diverifikasi: compile-check semua modul (`app/*.py`,
    `app/channels/*.py`); route `/webhook/synology` terkonfirmasi
    terdaftar otomatis dari `CHANNELS` (bukan hardcoded di `main.py`
    lagi) lewat inspeksi `app.routes`; regresi fungsional penuh lewat
    `TestClient` dengan `ask_adit`/`SynologyAdapter.send_reply` di-mock —
    semua hasil identik dengan perilaku 0.1.0 sebelum refactor.

## [0.1.0] - 2026-08-13

Rilis awal, repo baru terpisah dari `adit-client`: jembatan antara
Synology Chat dan server `adit` (`/v1/chat/completions`).

### Added
- `app/main.py` — endpoint `POST /webhook/synology` (outgoing webhook
  Synology Chat): verifikasi token, balas ACK instan (`{"text": "..."}`),
  proses jawaban di background task supaya tidak menahan respons webhook
  (Synology Chat butuh respons cepat, generate model di CPU bisa lama).
  `GET /healthz` untuk monitoring.
- `app/synology.py` — `verify_token()` (constant-time compare, fail
  closed kalau token belum dikonfigurasi), `send_incoming_webhook()`
  (kirim balasan akhir sebagai pesan baru lewat Incoming Webhook URL).
- `app/adit_client.py` — `ask_adit()`: panggil `/v1/chat/completions`
  server adit selalu **non-streaming** (rasional: Synology Chat tidak
  punya API edit-pesan-berkelanjutan, jadi streaming token-per-token
  tidak ada gunanya di sini), terjemahkan status error (400/401/429/503)
  jadi pesan ramah berbahasa Indonesia, tandai balasan
  `clarification_pending` dengan emoji ❓.
- `app/config.py` — semua konfigurasi lewat env var, lihat `.env.example`.
- `session_id` dibentuk dari `synology:<channel_name>:<user_id>`, selaras
  dengan alur klarifikasi otomatis server adit yang di-track per
  `session_id`.
- `Dockerfile` + `docker-compose.yml` — jalankan `adit-agent` + server
  adit bersamaan, server adit tidak perlu diekspos ke internet, cukup
  `adit-agent` yang publik-facing untuk menerima webhook.
- `README.md`, `TODO.md` — dokumentasi setup Synology Chat (Outgoing +
  Incoming Webhook), tabel konfigurasi, rasional desain, batasan yang
  diketahui.

Diverifikasi: seluruh logika `app/main.py` lewat `TestClient` (mock
`ask_adit` & `send_incoming_webhook`) — token salah → ditolak (`200`
dengan body kosong, tidak membocorkan detail kegagalan auth ke chat);
token benar → ACK instan + background task terpanggil dengan `session_id`
yang benar (`synology:general:u1`); teks kosong → pesan pengingat, tidak
memanggil model; `/healthz` → `200`. `send_incoming_webhook()`
diverifikasi mengirim HTTP POST nyata ke server penerima terpisah (bukan
mock) — payload `{"text": ...}` diterima dan dicocokkan. Bentuk request
`/v1/chat/completions` sama persis dengan yang sudah berkali-kali
diverifikasi bekerja terhadap server adit v0.6 & v1.0-beta1 sepanjang
pengembangan `adit-client`.

*Belum diverifikasi: live end-to-end penuh (Synology Chat asli →
adit-agent → server adit sungguhan, tiga proses hidup bersamaan) —
terkendala keterbatasan sandbox untuk proses latar belakang jangka
panjang di lingkungan pengembangan ini.*
