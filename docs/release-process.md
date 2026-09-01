# Proses rilis (otomatis lewat CHANGELOG.md)

Sejak 0.5.0, rilis `adit-agent` (tag, release notes, image Docker) dibuat
otomatis oleh CI setiap `CHANGELOG.md` mendapat heading versi baru (`##
[x.y.z]`) dan di-push ke branch `main`. Tidak perlu langkah manual apa pun
di luar itu, di GitHub maupun Gitea (workflow berjalan paralel di
keduanya, dipilih otomatis oleh masing-masing platform).

## Alur

1. Tambah entri baru di `CHANGELOG.md` dengan heading `## [x.y.z] -
   YYYY-MM-DD`, sinkronkan angka versi yang sama di `app/__init__.py`
   (`__version__` — satu-satunya sumber versi lain di repo ini).
2. Push ke `main`.
3. CI (`release.yml`) mem-parsing versi & catatan rilis langsung dari
   section `CHANGELOG.md` yang baru, lalu:
   - Membuat tag `vx.y.z` + Release (GitHub Release / Gitea Release) berisi
     catatan tersebut apa adanya.
   - Build & push image Docker ke Docker Hub (`endsho/adit-agent`) dengan
     tag `x.y.z`, `x.y` (kalau versi stabil, bukan pre-release), dan
     `latest`.
   - Versi dengan akhiran pre-release (mis. `1.0.0-beta`) otomatis ditandai
     sebagai *prerelease*, bukan rilis stabil.
   - Kalau tag `vx.y.z` sudah pernah dibuat sebelumnya (mis. push ulang),
     langkah pembuatan release & image dilewati — dianggap sudah pernah
     rilis, tidak dobel.

Push ke `main` yang **tidak** menyentuh `CHANGELOG.md` (mis. perbaikan
kecil di antara dua rilis) tetap membangun & mem-push image Docker lewat
`docker-publish.yml`, tapi cuma dengan tag `:latest` — tidak membuat
Release maupun tag versi baru.

## Backfill

`backfill-releases.yml` dijalankan manual (workflow_dispatch) sekali saja
kalau perlu membuat Release yang tertinggal untuk versi-versi lama di
`CHANGELOG.md` yang belum punya Release (mis. setelah mengaktifkan
otomasi ini pertama kali di repo yang sudah punya banyak riwayat versi).

## Secret yang dibutuhkan

- GitHub: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` (repo secrets). `GITHUB_TOKEN`
  bawaan Actions dipakai untuk membuat Release, tidak perlu diisi manual.
- Gitea: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, dan `GITEA_TOKEN`
  (personal/repo access token dengan izin tulis Release) — Gitea Actions
  tidak menyediakan token Release bawaan seperti GitHub.

Image publik memakai akun Docker Hub `endsho`, lisensi MIT (lihat
`LICENSE`).
