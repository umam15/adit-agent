# TODO — adit-agent

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

- [ ] **Verifikasi live end-to-end**: jalankan Synology Chat asli → `adit-agent`
  → server adit sungguhan sekali penuh (belum sempat di lingkungan
  pengembangan ini karena keterbatasan sandbox, lihat `README.md`). Terutama
  cek: format form field yang benar-benar dikirim Synology (nama field bisa
  sedikit berbeda antar versi DSM), dan apakah balasan JSON ACK benar-benar
  langsung muncul di UI chat. **Prioritasnya naik** setelah bug `payload` di
  0.3.0 — tanda bahwa asumsi format API pihak ketiga sebaiknya dicek ke
  Synology sungguhan, bukan cuma dokumentasi/simulasi, sebelum dianggap final.
- [ ] **Riwayat percakapan multi-turn**: saat ini tiap pesan dikirim
  single-turn (`messages` cuma berisi 1 pesan user), jadi model tidak
  "ingat" konteks turn sebelumnya di luar alur klarifikasi otomatis (yang
  sudah di-track server-side). Kalau dibutuhkan percakapan yang nyambung,
  perlu state in-memory (atau Redis/SQLite) di `adit-agent` yang menyimpan
  N pesan terakhir per `session_id`, lalu diteruskan sebagai `messages` array
  penuh ke server adit — mirip cara `adit-client` menyimpan `history` per tab.
- [ ] **Robust parsing field Synology**: `SynologyChatListener.parse_request()`
  (`app/channels/synology_chat_listener.py`) saat ini cuma baca
  `payload.get("token"/"text"/"user_id"/"channel_name")` langsung dari form.
  Kalau nanti ketemu variasi payload nyata (nama field beda, token di
  header/query alih-alih body), tambahkan fallback seperti dicontohkan di
  komunitas (`token` dari `body.token` → `?token=` → header).

## Prioritas menengah

- [ ] Rate limiting / anti-spam sendiri di `adit-agent` (independen dari
  rate limit server adit), terutama kalau nanti dipasang di channel besar.
- [ ] Command/slash command sederhana, mis. `/adit reset` untuk membersihkan
  konteks sesi (begitu multi-turn history diimplementasikan).
- [ ] Retry/backoff kalau `send_incoming_webhook()` gagal (saat ini cuma
  di-log, tidak ada retry — jawaban model bisa hilang kalau incoming webhook
  Synology sedang tidak bisa diakses).
- [ ] Metrics/observability dasar (jumlah pesan diproses, latency generate,
  rasio error) — bisa reuse ide dari `docs/TODO-API.md` server adit poin 6.

## Prioritas rendah / nice-to-have

- [ ] Dukungan multi-channel dengan token/incoming-webhook berbeda per
  channel (saat ini satu `SYNOLOGY_INCOMING_WEBHOOK_URL` global di env).
- [ ] Format balasan lebih kaya (lihat dukungan `attachments`/tombol
  interaktif di dokumentasi Synology Chat) untuk pertanyaan klarifikasi —
  mis. tombol quick-reply alih-alih user harus ngetik ulang.
- [ ] **Test otomatis (`pytest` + `TestClient`) disimpan permanen**: saat ini
  verifikasi sudah dilakukan manual lewat script ad-hoc tiap kali ada
  perubahan (termasuk setelah refactor adapter di 0.2.0), belum jadi bagian
  test suite repo (`tests/test_webhook.py`, `tests/channels/test_synology.py`).
  Sekarang strukturnya sudah pluggable (dan sejak 0.4.0, `SynologyChatListener`/
  `SynologyChatBot` bisa dites terpisah -- lihat `CHANGELOG.md` 0.4.0), ini jadi
  lebih penting supaya channel baru bisa dites tanpa harus jalankan manual
  tiap kali.

## Tidak akan dikerjakan (di luar lingkup)

- Streaming token-per-token ke Synology Chat — tidak ada API publik untuk
  edit pesan berkelanjutan di Synology Chat (beda dari Slack), jadi UX ini
  memang tidak relevan untuk platform ini. Lihat rasional di `README.md`.
