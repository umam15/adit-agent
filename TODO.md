# TODO — adit-agent

## Prioritas tinggi

- [ ] **Verifikasi live end-to-end**: jalankan Synology Chat asli → `adit-agent`
  → server adit sungguhan sekali penuh (belum sempat di lingkungan
  pengembangan ini karena keterbatasan sandbox, lihat `README.md`). Terutama
  cek: format form field yang benar-benar dikirim Synology (nama field bisa
  sedikit berbeda antar versi DSM), dan apakah balasan JSON ACK benar-benar
  langsung muncul di UI chat.
- [ ] **Riwayat percakapan multi-turn**: saat ini tiap pesan dikirim
  single-turn (`messages` cuma berisi 1 pesan user), jadi model tidak
  "ingat" konteks turn sebelumnya di luar alur klarifikasi otomatis (yang
  sudah di-track server-side). Kalau dibutuhkan percakapan yang nyambung,
  perlu state in-memory (atau Redis/SQLite) di `adit-agent` yang menyimpan
  N pesan terakhir per `session_id`, lalu diteruskan sebagai `messages` array
  penuh ke server adit — mirip cara `adit-client` menyimpan `history` per tab.
- [ ] **Robust parsing field Synology**: `main.py` saat ini cuma baca
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
- [ ] Test otomatis (`pytest` + `TestClient`) disimpan permanen di
  `tests/test_webhook.py` — saat ini verifikasi sudah dilakukan manual
  lewat script ad-hoc, belum jadi bagian test suite repo.

## Tidak akan dikerjakan (di luar lingkup)

- Streaming token-per-token ke Synology Chat — tidak ada API publik untuk
  edit pesan berkelanjutan di Synology Chat (beda dari Slack), jadi UX ini
  memang tidak relevan untuk platform ini. Lihat rasional di `README.md`.
