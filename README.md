# MultiPost v1.2 Hybrid — 1 Video, Posting ke 5 Platform

> **v1.2 — browser ringan:** mode Browser/Cookie sekarang memakai **Microsoft Edge bawaan Windows 11** (tanpa unduh Chromium ±170 MB). Fallback otomatis: Chrome, lalu Chromium bawaan Playwright. Paksa pilihan lewat env `MULTIPOST_BROWSER=edge|chrome|chromium`.

Software desktop Windows: upload **1 video + 1 caption**, terbit ke **Instagram, Threads, Facebook, TikTok, YouTube** sekaligus.

Dibangun hybrid sesuai sifat tiap platform:

| Platform | Mode utama | Mode cadangan | Catatan |
|---|---|---|---|
| Instagram | API (Meta Graph) | Browser (eksperimental) | API butuh URL publik video + akun Business/Creator |
| Threads | API (Threads) | Browser (eksperimental) | API butuh URL publik video, teks maks 500 karakter (auto-potong + peringatan) |
| Facebook | API (Page, upload file lokal) | Browser (profil personal) | Profil personal via API hanya bisa teks |
| TikTok | **Browser** (TikTok Studio) | Cookie `sessionid` | API resmi tanpa audit = private-only |
| YouTube | **Browser** (YouTube Studio) | Cookie (tidak disarankan) | API tanpa audit = video dipaksa private |

## Cara pakai (Windows 11)

### Opsi A — langsung dari source (disarankan untuk pemakaian pertama)
1. Ekstrak ZIP ini ke `C:\BOT\MultiPost\`
2. Klik 2x `run.bat` (install dependency + Chromium otomatis, lalu UI terbuka).

### Opsi B — jadi .exe
1. Klik 2x `build.bat` → hasil `dist\MultiPost.exe`.
2. Jalankan exe-nya. Folder `data\` dibuat di sebelah exe — **jangan dipisah dari exe** (di situlah akun & sesi login tersimpan).

### Alur posting
1. Tab **Akun**: tambah akun per platform, pilih mode, login/token sesuai `PANDUAN-AKUN.md`.
2. Tab **Posting**: pilih video → tulis caption → (judul YouTube & URL publik bila pakai API Meta) → centang akun → **POSTING SEKARANG** → cek ringkasan → OK.
3. Status tiap platform muncul di Log & tab **Jadwal & Riwayat**. Penjadwalan: centang "Jadwalkan pada" — software harus tetap terbuka agar job jalan pada waktunya.

## Keamanan
- Token/cookie terenkripsi **Windows DPAPI** (hanya user Windows kamu yang bisa membukanya), sesi browser tersimpan lokal. Tidak ada data yang dikirim ke server mana pun selain platform tujuannya sendiri.
- 1x konfirmasi sebelum publish menampilkan versi persis yang akan terbit. Tidak ada auto-retry: hasil tidak jelas = dilaporkan, bukan diulang (anti dobel posting).

## Batasan v1 (jujur)
- Belum dites dengan akun asli pemilik — selector TikTok Studio/YouTube Studio/Meta web bisa perlu penyesuaian setelah uji pertama (kegagalan selalu terscreenshot di `data\logs\`).
- Mode Browser Meta (IG/Threads web) masih eksperimental; jalur andalannya API.
- Jadwal hanya jalan saat aplikasi terbuka (belum ada Windows Service).

## Struktur
```
app.py                 entry point (UI / --cli)
multipost/
  captions.py          adaptasi caption per platform + batas karakter
  crypto_store.py      enkripsi DPAPI (Windows) / Fernet (dev)
  store.py             akun, job terjadwal, riwayat (folder data\)
  engine.py            orkestrasi publish sekuensial per platform
  publishers/
    meta_api.py        IG / Threads / FB Page via Graph API
    tiktok_browser.py  TikTok Studio via profil browser persisten
    youtube_browser.py YouTube Studio via profil browser persisten
    meta_browser.py    fallback web Meta (eksperimental)
  ui.py                antarmuka PySide6
tests/                 unit test core (caption, store, engine dry-run)
```

## Tes (pengembang)
```
python -m pytest tests/ -q
python app.py --cli dry-run --caption "Tes"   # butuh minimal 1 akun tersimpan
```
