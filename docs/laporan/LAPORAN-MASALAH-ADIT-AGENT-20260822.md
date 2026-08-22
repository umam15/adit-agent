# Laporan Masalah adit-agent (v0.4.4)

Tanggal: 2026-08-22 · Lingkup: penerapan update v0.4.2 → v0.4.4 di testbench + verifikasi end-to-end (Synology Chat ↔ adit-agent ↔ adit-server v1.11.0-beta)

## Ringkasan eksekutif

Update berhasil diterapkan dan seluruh pipeline tercatat berjalan (webhook 200 → server adit 200 → Synology 200), tetapi verifikasi menemukan **satu masalah kritis**: pengiriman balasan ke URL Bot (`method=chatbot`) **gagal senyap** — HTTP 200 padahal pesan tidak pernah sampai ke siapa pun — karena `reply_to_user` tidak pernah bernilai true melalui jalur mana pun yang disediakan produk. Ditemukan pula masalah UX pada status aktif default dan beberapa catatan operasional.

## Daftar masalah

| ID | Severitas | Ringkas | Status |
|---|---|---|---|
| M1 | Rendah | Nama zip update ≠ folder internal | zip lama sudah dihapus dari `update/` |
| M2 | Sedang | Agent baru tersimpan nonaktif (default `active=false`, UI tanpa kontrol) | workaround PATCH |
| M3 | **Kritis** | URL Bot gagal senyap: tanpa `reply_to_user`/`user_ids`, Synology balas 200 tanpa mengirim apa pun | workaround PATCH + restart |
| M4 | Sedang (potensi) | `user_id` berformat array-string akan gagal `int()` → fallback tanpa `user_ids` lagi | observasi |
| M5 | Info | Restart proses wajib tiap create/update agent | sesuai desain (hot-reload belum ada) |
| M6 | Info | Instance server adit ganda gagal bind port (Errno 10048) | tidak berdampak |
| M7 | Info operasional | `.env` tak dimuat otomatis; `ADIT_AGENT_SECRET_KEY` wajib; dep baru `cryptography>=42` | sudah dipasang |

## Detail

### M1 — Penamaan zip tidak konsisten (rendah)
`adit-agent-v0_4_2-changelog-format-20260817-1005.zip` berisi root folder `adit-agent-v0_4_3/`. Berpotensi membingungkan pelacakan versi saat menerapkan paket dengan alur timpa-file.

### M2 — Agent baru tersimpan nonaktif (sedang)
- Endpoint create mem-default nonaktif: `api_admin.py:113` → `active = bool(body.get("active", False))`.
- UI panel (`app/web/index.html`) **hanya menampilkan** label Aktif/Nonaktif (baris 259–260, metrik 145–146) — **tidak ada kontrol** untuk mengatur status saat create maupun edit.
- Akibat berantai: `load_channels(active_only=True)` (`app/channels/__init__.py`) melewatkan record → `/healthz` tetap `{"channels": []}` bahkan setelah restart.
- Kasus nyata: agent "Azza" (id `45bd1d3ad738`) dibuat lewat panel dengan `active=false`; harus di-PATCH manual `{"active": true}`.

### M3 — URL Bot gagal senyap tanpa `reply_to_user` (kritis)
- Sender memuat flag dengan default False untuk SEMUA platform: `synology_chat_bot.py:57` → `_get_bool(config.get("reply_to_user"), False)`.
- Platform `synology_bot` **tidak** memicu perilaku berbeda apa pun — kedua platform Synology dipetakan ke class yang sama tanpa pembeda (`app/channels/__init__.py`).
- Protokol Synology: payload ke URL Bot **wajib** menyertakan `user_ids`; tanpanya request tetap HTTP 200 tetapi pesan tidak dikirim ke siapa pun.
- UI panel tidak menyediakan field `reply_to_user` sama sekali (tidak ada satu pun kecocokan di `index.html`) — satu-satunya jalan konfigurasi adalah PATCH API manual.
- Perhatian PATCH: `creds` **menimpa seluruh dict lama**, bukan merge per-key (docstring `api_admin.py` PATCH) — salah langkah bisa menghapus token.
- Bukti log (lampiran `adit-agent-9000.log`, 08:00:16–17): `POST /webhook/synology/azza 200` → `POST .../v1/chat/completions 200` → `POST https://...entry.cgi?...method=chatbot... "HTTP/1.1 200 OK"` — namun tidak ada pesan yang muncul.
- Workaround lokal yang diterapkan: PATCH creds lengkap + `reply_to_user=true`, lalu restart proses.

### M4 — Format `user_id` array-string (potensi sedang)
Listener mengambil nilai mentah (`str(payload.get("user_id"))`), sementara Synology kerap mengirim `user_id` sebagai string JSON-array (`[\"8\"]`). Pengirim melakukan `[int(message.user_id)]` → `ValueError` → ter-catch → **mengirim tanpa `user_ids` lagi** (hanya warning log "bukan angka"). Belum terkonfirmasi pada payload nyata — pantau log saat pesan tes berikutnya; jika muncul, perlu normalisasi parsing (terima `"8"`, `8`, dan `[\"8\"]`).

### M5 — Restart wajib setelah create/update agent (info)
`CHANNELS = load_channels()` dievaluasi sekali saat import (`app/channels/__init__.py:90`); API admin sendiri mendokumentasikan ini (`api_admin.py:5–10`) dan menyertakan `"restart_required": true` pada respons — mudah terlewati karena UI tidak menonjolkannya. Hot-reload tercatat TODO prioritas rendah.

### M6 — Konflik port saat start ganda (info)
Log server mencatat percobaan start instance kedua yang gagal bind `127.0.0.1:8000` (`Errno 10048`) lalu shutdown bersih. Terjadi saat debugging; tanpa dampak karena instance pertama tetap melayani.

### M7 — Catatan operasional (info)
- `.env` **tidak** dimuat otomatis (tidak ada python-dotenv) — env harus lewat docker-compose `env_file` atau export manual sebelum menjalankan uvicorn.
- `ADIT_AGENT_SECRET_KEY` wajib; proses fail-closed tanpa itu (by design, baik).
- Dependensi baru v0.4.4: `cryptography>=42` (sudah di-install ke venv testbench).

## Rekomendasi upstream

1. Di `load_channels()`: jika `record.platform == "synology_bot"`, inject `config.setdefault("reply_to_user", True)` — semantik URL Bot menuntut `user_ids`.
2. Panel: tambahkan toggle Aktif/Nonaktif di form create/edit + field `reply_to_user` untuk platform bot, dan sorot banner "restart diperlukan" setelah simpan.
3. Normalisasi parsing `user_id` (M4) di sender/listener.
4. Pertimbangkan default `active=true` saat create, atau minimal peringatan eksplisit bahwa agent baru tidak akan menerima webhook sampai diaktifkan + direstart.

## Lampiran

- `lampiran/adit-agent-9000.log` — log runtime agent (token webhook telah diredaksi)
- `lampiran/adit-server-8000.log` — log server adit (bukti M6)
