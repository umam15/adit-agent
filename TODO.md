# TODO — adit-agent

> Item baru di bawah bertanda **(2026-08-22)** berasal dari
> [`docs/laporan/LAPORAN-MASALAH-ADIT-AGENT-20260822.md`](docs/laporan/LAPORAN-MASALAH-ADIT-AGENT-20260822.md)
> (pengujian penerapan 0.4.2 → 0.4.4 + verifikasi end-to-end Synology Chat
> asli). Baca laporan itu untuk log mentah & konteks lengkap tiap temuan.

## Selesai di 0.6.1

- [x] **`depends_on` di `docker-compose.yml` dihapus** — lihat
  `CHANGELOG.md` 0.6.1. Tidak sesuai standar (service `adit` tidak punya
  image publik, dan `depends_on` cuma nunggu kontainer dibuat, bukan
  server siap) -- koneksi antar service sudah cukup lewat nama service
  langsung.

## Selesai di 0.6.0

- [x] **Tema panel admin diseragamkan dengan `adit-admin`** — lihat
  `CHANGELOG.md` 0.6.0. `app/web/index.html` sekarang pakai token warna &
  tipografi yang sama dengan dashboard `adit-admin`.
- [x] **Panel admin lepas dari CDN eksternal** — font ikon tabler-icons
  diganti SVG inline, panel bisa dibuka tanpa koneksi internet.
- [x] **`VERSION` sebagai satu-satunya sumber nomor versi** — sebelumnya
  hardcode string di `app/__init__.py`.

## Selesai di 0.4.6

- [x] **Versi aplikasi bisa dicek dari luar** — `__version__` di
  `app/__init__.py`, tampil di metadata FastAPI dan `GET /healthz`.
- [x] **`.gitignore` & `.dockerignore`** — sebelumnya tidak ada.
- [x] **Redaksi nama personal di laporan** — `Azza` → `TestBot` di
  `docs/laporan/LAPORAN-MASALAH-ADIT-AGENT-20260822.md` & log lampiran.
- [x] **(2026-08-22) Penamaan zip rilis tidak konsisten (M1)** — dicek
  ulang: paket rilis sejak 0.4.5 sudah konsisten (nama file & folder root
  sama-sama `adit-agent-v0_4_x`). Tetap jaga konsistensi ini di rilis
  berikutnya.

## Selesai di 0.4.5

- [x] **[KRITIS] `synology_bot` gagal senyap tanpa `reply_to_user`** — lihat
  `CHANGELOG.md` 0.4.5. `reply_to_user` sekarang di-hardcode `true` di kode
  (`_FORCE_REPLY_TO_USER`, `app/channels/synology.py`) begitu
  `platform == "synology_bot"`, berlaku juga di endpoint tes koneksi
  (sebelumnya tidak, lihat catatan `build_adapter()` di CHANGELOG).
- [x] **Normalisasi `user_id`** — `_normalize_user_id()` baru
  (`app/channels/synology_chat_bot.py`) menerima bentuk angka, string
  angka, maupun string JSON-array satu elemen.
- [x] **Toggle Aktif di modal "Tambah agent"** — `app/web/index.html`.
- [x] **Webhook dispatch dinamis** — satu route generik
  (`webhook_dispatch`, `app/main.py`) lookup agent dari database per
  request. Create/update/delete/toggle agent lewat panel admin sekarang
  langsung live, TIDAK perlu restart proses. `/healthz` juga query
  database fresh tiap dipanggil. Lihat `docs/architecture.md`.
- [x] `app/channels/build_adapter()` — satu fungsi bersama pembangun
  adapter, dipakai `load_channels()`, `webhook_dispatch`, dan endpoint tes
  koneksi (sebelumnya tiga tempat beda-beda caranya).

## Selesai di 0.4.4

- [x] **Panel admin (`/admin`) + kredensial channel murni dari UI**: lihat
  `CHANGELOG.md` 0.4.4 untuk detail lengkap. Ini menyelesaikan sebagian
  besar item "Panel kontrol multi-agent" yang sebelumnya direncanakan di
  bagian bawah file ini (sudah dipindah ke bagian "Selesai" ini):
  - [x] `app/store.py` — penyimpanan agent terenkripsi (Fernet)
  - [x] Refactor adapter Synology terima `config` per-instance
  - [x] `app/channels/__init__.py` — `load_channels()` murni dari database
  - [x] `app/api_admin.py` — CRUD `/api/agents` + tes koneksi
  - [x] Panel admin (`app/web/index.html`) tersambung ke API asli
  - [x] Env var kredensial channel (`SYNOLOGY_*`) dihapus total — env var
    sekarang murni admin/server
- [x] **Auth panel admin diverifikasi nyata**: laporan pengujian
  2026-08-22 (`LAPORAN-MASALAH-ADIT-AGENT.md` M7 + lampiran log) mengonfirmasi
  alur `ADIT_AGENT_ADMIN_TOKEN` jalan sungguhan di `app/web/index.html` —
  `401 Unauthorized` sebelum token diisi, `200 OK` setelahnya. Create/tes
  koneksi/update/delete via panel juga tercatat sukses di log. **Kritis
  ditemukan dari pengujian yang sama** — lihat "Prioritas tinggi" di bawah.

## Selesai di 0.4.2

- [x] **Rename istilah "channel" -> "Synology Chat"**: `SynologyChannel` →
  `SynologyChatListener`, `SynologyBot` → `SynologyChatBot` (rename murni,
  tanpa perubahan perilaku). Lihat `CHANGELOG.md` 0.4.2.

## Selesai di 0.4.1

- [x] **`user_ids` untuk Bot Synology (`method=chatbot`)**: `SynologyChatBot`
  sekarang mendukung `SYNOLOGY_REPLY_TO_USER` (default `false`, backward
  compatible) untuk menyertakan `user_ids` di payload saat
  `SYNOLOGY_INCOMING_WEBHOOK_URL` adalah URL Bot, bukan Incoming Webhook
  polos. Lihat `CHANGELOG.md` 0.4.1. Listener (`SynologyChatListener`) tidak
  perlu ikut dipecah — formatnya sama untuk kedua mode kirim.

## Selesai di 0.4.0

- [x] **Pisah "channel" (listener) dan "bot" (sender) Synology jadi dua
  concern eksplisit**: `SynologyAdapter` sekarang cuma delegasi tipis ke
  `SynologyChatListener` (`app/channels/synology_chat_listener.py`, verifikasi token +
  `parse_request()`) dan `SynologyChatBot` (`app/channels/synology_chat_bot.py`,
  format payload + `send_reply()`). Kontrak `ChannelAdapter` yang dipakai
  `main.py`/`orchestrator.py` tidak berubah. Lihat `CHANGELOG.md` 0.4.0 untuk
  detail verifikasi.

## Selesai di 0.3.0

- [x] **Bugfix format Incoming Webhook**: lihat `CHANGELOG.md` 0.3.0 —
  `send_reply()` sekarang kirim `application/x-www-form-urlencoded` dengan
  field `payload` (string JSON), bukan `application/json` mentah.

## Selesai di 0.2.0

- [x] **Arsitektur adapter per channel**: refactor `app/synology.py` jadi
  `app/channels/synology.py` yang mengimplementasikan `ChannelAdapter`
  (`app/channels/base.py`). Logika inti (`app/orchestrator.py`, `main.py`)
  sekarang generik lintas channel — nambah channel baru tinggal satu file +
  satu baris di `app/channels/__init__.py`, tidak perlu ubah kode lain.
  Lihat panduan & contoh stub Telegram di `README.md`.
- [x] `/healthz` sekarang menampilkan daftar channel aktif (`{"channels":
  [...]}`), berguna buat verifikasi cepat channel mana saja yang terpasang.

## Prioritas tinggi

- [ ] **Pesan ACK bisa custom**: saat ini `ADIT_ACK_MESSAGE` satu nilai
  global lewat env var (`app/config.py`, dipakai `SynologyAdapter.ack_response()`).
  Field "Pesan ACK" per-agent di form tambah/edit (kolom `ack_message`
  nullable di tabel `agents`, `app/store.py` — `NULL` berarti pakai
  default global), dengan default global itu sendiri ikut jadi salah satu
  "runtime setting" yang bisa diedit dari panel (lihat item "Runtime
  settings" di bawah, bukan halaman "Pengaturan" umum).

- [ ] **Runtime settings di panel admin — bukan halaman "Pengaturan"
  umum, dan bukan tempat mengedit token admin**: pisahkan berdasarkan
  sifatnya, bukan digabung rata:
  - **Tetap env var, TIDAK dibuat bisa diedit dari UI**: `ADIT_AGENT_HOST`,
    `ADIT_AGENT_PORT`, `ADIT_AGENT_SECRET_KEY`, `ADIT_AGENT_DB_PATH`,
    `ADIT_AGENT_ADMIN_TOKEN`. Semua ini dibaca sekali saat proses
    bootstrap (bind socket, buka koneksi database, kunci enkripsi) —
    mengubahnya secara inheren butuh restart, jadi UI-editable untuk
    field ini cuma menciptakan ekspektasi salah ("kok saya ganti kok
    belum berubah"). Ini juga keputusan keamanan sadar untuk
    `ADIT_AGENT_ADMIN_TOKEN` khususnya: kredensial akses ke panel yang
    mengelola kredensial lain sebaiknya hidup di layer infrastruktur,
    bukan di sistem yang dia sendiri lindungi — kalau database bocor,
    token admin tidak ikut bocor. **Turunkan "edit admin token dari UI"
    ke tidak dikerjakan sama sekali** kecuali panel ini nanti benar-benar
    dipakai lebih dari satu admin (baru itu sepadan dengan kompleksitas
    login+hash+session).
  - **Aman dipindah ke DB + diedit dari UI, berlaku langsung tanpa
    restart** (dipakai ulang tiap request, tidak mengikat resource apa
    pun saat start): `ADIT_BASE_URL`, `ADIT_API_KEY`, `ADIT_MAX_TOKENS`,
    `ADIT_TEMPERATURE`, `ADIT_TOP_K`, `ADIT_REQUEST_TIMEOUT`, pesan ACK
    global (lihat item di atas). Simpan di tabel key-value baru
    (`app/store.py`, field sensitif seperti `ADIT_API_KEY` tetap
    dienkripsi sama seperti kredensial channel), endpoint
    `GET/PATCH /api/settings`. `app/config.py` perlu pola yang sama
    seperti `load_channels()`: baca dari DB dulu, fallback ke env
    var/default kalau belum diisi lewat UI.
  - Bagian ini bisa jadi satu panel kecil (mis. drawer terpisah "Server"
    di sebelah daftar agent), bukan halaman terpisah besar — cakupannya
    memang cuma segelintir field.

## Prioritas tinggi (temuan lain, non-kritis)

- [ ] **Verifikasi live end-to-end**: jalankan Synology Chat asli → `adit-agent`
  → server adit sungguhan sekali penuh (belum sempat di lingkungan
  pengembangan ini karena keterbatasan sandbox, lihat `docs/architecture.md`).
  Terutama cek: format form field yang benar-benar dikirim Synology (nama
  field bisa sedikit berbeda antar versi DSM), dan apakah balasan JSON ACK
  benar-benar langsung muncul di UI chat. **Prioritasnya naik** setelah bug
  `payload` di 0.3.0 — tanda bahwa asumsi format API pihak ketiga sebaiknya
  dicek ke Synology sungguhan, bukan cuma dokumentasi/simulasi, sebelum
  dianggap final.
- [ ] **Riwayat percakapan multi-turn**: saat ini tiap pesan dikirim
  single-turn (`messages` cuma berisi 1 pesan user), jadi model tidak
  "ingat" konteks turn sebelumnya di luar alur klarifikasi otomatis (yang
  sudah di-track server-side). Kalau dibutuhkan percakapan yang nyambung,
  perlu state in-memory (atau Redis/SQLite) di `adit-agent` yang menyimpan
  N pesan terakhir per `session_id`, lalu diteruskan sebagai `messages` array
  penuh ke server adit — mirip cara `adit-client` menyimpan `history` per tab.
  Sebaiknya jadi toggle per-agent (lewat panel admin), bukan flag global.
- [ ] **Robust parsing field Synology**: `SynologyChatListener.parse_request()`
  (`app/channels/synology_chat_listener.py`) saat ini cuma baca
  `payload.get("token"/"text"/"user_id"/"channel_name")` langsung dari form.
  Kalau nanti ketemu variasi payload nyata (nama field beda, token di
  header/query alih-alih body), tambahkan fallback seperti dicontohkan di
  komunitas (`token` dari `body.token` → `?token=` → header).

## Prioritas menengah

- [ ] **`TelegramAdapter` sungguhan** (`app/channels/telegram.py`) — bukti
  nyata bahwa pola adapter + multi-instance di 0.4.4 memang generik lintas
  platform. Lihat contoh stub & langkah pendaftaran di `docs/architecture.md`.
- [ ] Rotasi token dari panel admin (generate ulang tanpa hapus-buat-ulang
  agent).
- [ ] Rate limiting / anti-spam sendiri di `adit-agent` (independen dari
  rate limit server adit), terutama kalau nanti dipasang di channel besar.
- [ ] Command/slash command sederhana, mis. `/adit reset` untuk membersihkan
  konteks sesi (begitu multi-turn history diimplementasikan).
- [ ] Retry/backoff kalau `send_reply()` gagal (saat ini cuma di-log, tidak
  ada retry — jawaban model bisa hilang kalau incoming webhook Synology
  sedang tidak bisa diakses). Begitu ada, tampilkan badge "pesan tertunda"
  di kartu agent terkait pada panel admin.
- [ ] Metrics/observability dasar (jumlah pesan diproses, latency generate,
  rasio error) — bisa reuse ide dari `docs/TODO-API.md` server adit poin 6.

## Prioritas rendah / nice-to-have

- [ ] **(2026-08-22) `.env` tidak dimuat otomatis (M7)**: adit-agent tidak
  memakai `python-dotenv`, jadi `.env` di root repo TIDAK otomatis terbaca
  saat `uvicorn app.main:app` dijalankan langsung — env var harus di-export
  manual atau lewat `env_file` di `docker-compose.yml`. Ini sebenarnya
  perilaku yang disengaja (env var eksplisit lebih predictable), tapi
  `README.md`/`.env.example` perlu menyebutkan ini secara eksplisit supaya
  tidak dikira bug ("`cp .env.example .env` lalu isi" bisa terkesan otomatis
  kebaca) — atau pertimbangkan tambah `python-dotenv` kalau UX "cukup isi
  `.env`" lebih diutamakan daripada eksplisitnya env var.
- [ ] Audit log perubahan kredensial di panel admin (siapa ubah apa, kapan)
  — baru relevan kalau panel ini dipakai lebih dari satu orang.
- [ ] Format balasan lebih kaya (lihat dukungan `attachments`/tombol
  interaktif di dokumentasi Synology Chat) untuk pertanyaan klarifikasi —
  mis. tombol quick-reply alih-alih user harus ngetik ulang.
- [ ] **Test otomatis (`pytest` + `TestClient`) disimpan permanen**: saat ini
  verifikasi sudah dilakukan manual lewat script ad-hoc tiap kali ada
  perubahan, belum jadi bagian test suite repo (`tests/test_webhook.py`,
  `tests/channels/test_synology.py`, `tests/test_store.py`,
  `tests/test_api_admin.py`). Sekarang strukturnya sudah pluggable (dan
  sejak 0.4.0, `SynologyChatListener`/`SynologyChatBot` bisa dites terpisah),
  ini jadi lebih penting supaya channel baru bisa dites tanpa harus jalankan
  manual tiap kali. Dua kasus dari 0.4.5 yang PALING wajib masuk duluan
  (sudah divalidasi manual/isolated saat implementasi, tapi belum permanen
  sebagai test suite -- lihat batasan verifikasi di `CHANGELOG.md` 0.4.4/0.4.5
  soal sandbox tanpa `fastapi`):
  - Buat agent `synology_bot` lewat `store.create_agent()`, bangun lewat
    `build_adapter()`, assert `adapter._bot.reply_to_user is True` walau
    `creds` yang disimpan eksplisit `False` -- regresi utama bug kritis M3.
  - Buat agent lewat API, langsung `TestClient.post()` ke webhook
    path-nya TANPA memanggil ulang apa pun di antaranya (simulasi "tanpa
    restart proses") -- assert diterima (bukan 404). Bukti langsung
    webhook dispatch dinamis benar.

## Tidak akan dikerjakan (di luar lingkup)

- Streaming token-per-token ke Synology Chat — tidak ada API publik untuk
  edit pesan berkelanjutan di Synology Chat (beda dari Slack), jadi UX ini
  memang tidak relevan untuk platform ini. Lihat rasional di
  `docs/architecture.md`.
- **(2026-08-22) Edit `ADIT_AGENT_ADMIN_TOKEN` dari UI panel admin** —
  dipertimbangkan, sengaja tidak dikerjakan untuk instance single-admin.
  Kredensial akses ke panel yang mengelola kredensial channel lain
  sebaiknya tetap hidup di layer infrastruktur (env var), terpisah dari
  sistem yang dia sendiri lindungi — kalau database `app/store.py` bocor,
  token admin tidak ikut bocor bersamanya. Rotasi tetap lewat edit `.env`
  + restart. Buka lagi item ini kalau panel benar-benar perlu dipakai
  lebih dari satu admin (baru itu sepadan dengan kompleksitas
  login+hash+session yang jadi prasyaratnya).
- **Halaman "Pengaturan" generik yang menggabung semua setting jadi satu**
  — diganti desain yang memisahkan setting infra (tetap env var) dari
  runtime setting (boleh diedit dari UI), lihat item "Runtime settings"
  di Prioritas tinggi. Menggabung semuanya jadi satu halaman menciptakan
  ekspektasi salah bahwa semua field di situ langsung berlaku, padahal
  sebagian (host/port) secara inheren butuh restart.
