# Synology Chat & Synology Bot

Panduan ini untuk mengisi **panel admin** (`/admin`) saat menambah agent
bertipe Synology Chat atau Synology Bot. Semua kredensial di bawah diisi
lewat UI — tidak ada file `.env` yang perlu disentuh untuk ini.

## Field yang diminta panel, dan dari mana asalnya

### 1. Token outgoing webhook

Synology Chat → **Profile → Integration → Bot → Buat Outgoing Webhook**.

- Isi kolom URL di Synology dengan alamat webhook masuk yang ditampilkan
  panel admin setelah agent dibuat (bentuknya `https://<host-kamu>/webhook/synology/<nama-agent>`).
- Salin token yang digenerate Synology, tempel ke field **"Token outgoing
  webhook"** di panel.

Ini arah **Synology → adit-agent**: setiap ada pesan baru, Synology yang
memanggil alamat webhook di atas.

### 2. URL incoming webhook / URL Bot

Ini arah sebaliknya, **adit-agent → Synology**, dan ada dua pilihan
platform di panel karena Synology punya dua jenis integrasi berbeda untuk
ini:

**Pilih "Synology Chat"** kalau balasan cukup muncul di satu channel tetap
(paling sederhana): **Profile → Integration → Incoming Webhook → Buat
webhook baru**, salin URL lengkapnya (sudah termasuk `?token=...`) ke
field **"URL incoming webhook"**.

**Pilih "Synology Bot"** kalau kamu ingin balasan bisa dikirim langsung ke
pengirim pesan (DM), bukan ke channel tetap — ini pakai `Bot` yang sama
dengan langkah token outgoing di atas (**Profile → Integration → Bot**),
method Synology-nya disebut `chatbot`. Salin URL webhook milik Bot
tersebut ke field **"URL webhook Bot"**.

> Kenapa dua platform terpisah di panel padahal sama-sama "Synology Chat"?
> Karena bentuk payload yang dikirim adit-agent ke Synology **berbeda**
> untuk dua kasus ini — kalau salah pilih, request bisa sukses (HTTP 200)
> tapi pesannya tidak pernah sampai ke siapa pun. Memisahkan pilihannya di
> panel mencegah campur-aduk dua konfigurasi ini secara tidak sengaja.

### 3. Pesan ACK (opsional)

Begitu pesan masuk, adit-agent langsung membalas satu pesan instan
("sedang mikir…" secara default) sebelum jawaban asli dari server adit
selesai diproses — supaya pengirim tahu pesannya sudah diterima, bukan
diam saja. Field **"Pesan ACK"** di panel membiarkan kamu ganti teks itu
khusus untuk agent ini. **Kosongkan** kalau mau tetap pakai pesan default.

## Sertifikat self-signed

Kalau NAS kamu memakai sertifikat self-signed (bukan dari Let's Encrypt
atau CA publik), pesan mungkin gagal terkirim karena verifikasi SSL. Panel
admin punya opsi "matikan verifikasi SSL" untuk kasus ini — hanya aktifkan
kalau kamu memang tahu NAS-nya memakai sertifikat self-signed dan berada
di jaringan yang kamu percaya.

## Setelah diisi

1. Simpan agent di panel (boleh biarkan nonaktif dulu kalau belum yakin
   kredensialnya benar — ada toggle "Aktifkan begitu disimpan" saat
   menambah agent, atau nyalakan toggle **Aktif** kapan pun lewat panel
   detail).
2. Klik **"Tes koneksi"** — adit-agent akan mengirim satu pesan uji lewat
   URL incoming webhook/Bot yang baru diisi. Kalau berhasil, cek channel
   atau DM Synology Chat terkait untuk konfirmasi pesan uji benar-benar
   muncul.
3. Nyalakan toggle **Aktif** (kalau belum), simpan. **Langsung berlaku
   saat itu juga — tidak perlu restart proses adit-agent sama sekali**
   untuk mengaktifkan/menonaktifkan/mengubah agent.

## Detail teknis lebih dalam

Kalau kamu berencana menambah channel baru selain Synology (mis. Telegram)
atau ingin paham arsitektur adapter di baliknya, lihat
[`docs/architecture.md`](../architecture.md). Riwayat perubahan/bug spesifik
integrasi Synology ada di `CHANGELOG.md` di root repo.
