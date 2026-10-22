# Panduan Akun MultiPost — Cookie & API

Semua kredensial disimpan **lokal di PC kamu** (`data\accounts.json`, terenkripsi Windows DPAPI + sesi browser di `data\profiles\`). Jangan kirim token/cookie ke siapa pun lewat chat.

## Mode Browser (paling gampang — TikTok, YouTube, semua platform)

1. Tab **Akun** → pilih platform, mode `browser`, isi label → **Simpan Akun**.
2. Pilih akun di tabel → **Login Browser**. Jendela Chromium terbuka: login sendiri (password/OTP/CAPTCHA kamu yang pegang), lalu tutup jendelanya.
3. Sesi tersimpan di `data\profiles\<akun>\`. Selama tidak logout & cookie belum kedaluwarsa, tidak perlu login ulang.

Ini pada dasarnya "cookie", tapi disimpan sebagai profil browser utuh — jauh lebih awet daripada copy-paste 1 cookie.

## Mode Cookie (paste manual — lanjutan)

### Cara A — 1 cookie (cukup untuk TikTok)
1. Login ke tiktok.com di Chrome biasa.
2. Tekan **F12** → tab **Application** → kiri: Storage → Cookies → `https://www.tiktok.com`.
3. Cari baris Name = `sessionid` → klik 2x kolom **Value** → salin isinya (teks panjang).
4. Di MultiPost tab Akun: platform TikTok, mode `cookie`, tempel ke kolom Token/Cookie, Nama cookie biarkan `sessionid` → **Simpan Akun**. Tersimpan terenkripsi DPAPI di `data\accounts.json` — bukan teks polos.

### Cara B — export JSON (wajib untuk Facebook, bisa untuk IG)
Facebook tidak cukup 1 cookie (perlu `c_user` + `xs` sekaligus), jadi pakai cara ini:
1. Install ekstensi **Cookie-Editor** di Chrome (dari Chrome Web Store resmi).
2. Login ke facebook.com / instagram.com → klik ikon Cookie-Editor → **Export → Export as JSON** (seluruh cookie tersalin).
3. Di MultiPost: mode `cookie`, tempel **seluruh JSON** ke kolom Token/Cookie → **Simpan Akun**. Software membaca semua cookie dari JSON itu saat publish.

YouTube: cookie-nya banyak & ketat — untuk YouTube **pakai mode Browser saja**.

Risiko: cookie mentah lebih cepat mati & lebih gampang memicu checkpoint. Kalau gagal terus, pindah ke mode Browser. **JANGAN PERNAH kirim cookie/token ke chat mana pun (termasuk ke GONZO)** — cookie = kata sandi, orang yang memegangnya bisa masuk akunmu tanpa OTP. Kalau cookie terlanjur tersebar: ganti password + logout semua sesi di platformnya, cookie lama langsung mati.

## Mode API — Meta (Instagram / Threads / Facebook Page)

Syarat keras dari Meta:
- Instagram harus akun **Business/Creator**. Threads memakai akun yang sama.
- Facebook yang bisa API hanyalah **Page** (bukan profil personal).

Langkah:
1. Buat app di https://developers.facebook.com → tipe Business.
2. Tambahkan produk: Instagram Graph API / Threads API / Facebook Login.
3. Minta permission: `instagram_content_publish`, `threads_content_publish`, `pages_manage_posts`, `pages_show_list`, `pages_read_engagement`. Untuk akun sendiri dalam mode Development, token bisa dibuat dari Graph API Explorer; untuk pemakaian luas perlu App Review + verifikasi bisnis.
4. Ambil **User Access Token** (tukar ke long-lived ±60 hari) → tempel di kolom Token/Cookie akun.
5. Isi **ID platform**: IG User ID (id akun IG bisnis), Threads User ID, atau Page ID — sesuai platform akunnya.
6. PENTING IG/Threads: API Meta **tidak menerima upload file lokal** — video harus bisa diakses dari URL publik. Isi kolom *URL publik video* di tab Posting (mis. link file dari hosting kamu). Facebook Page tidak punya batasan ini (file lokal langsung diupload software).
7. YouTube API tidak dipakai di v1: upload dari project Google yang belum diaudit dipaksa **private** oleh Google — karena itu YouTube lewat mode Browser (Studio) supaya publik.

## Kenapa TikTok tidak pakai API resmi?

API resmi TikTok untuk client yang belum diaudit hanya boleh posting **private (SELF_ONLY)**, maks 5 user/24 jam, dan audit TikTok menolak aplikasi utilitas untuk akun sendiri. Mode Browser memposting publik persis seperti manual.

## Risiko otomasi (wajib dibaca)

- Jalur browser/cookie = otomasi UI web. Ada risiko **limit, checkpoint, sampai ban akun kalau spam**. Jaga ritme manusiawi: 1–3 posting/hari/akun, jangan 5 akun posting di detik yang sama berulang-ulang.
- Kalau platform mengubah tampilan web, selector bisa rusak → publish gagal + ada screenshot di `data\logs\`. Itu disengaja: gagal terlihat, bukan gagal diam-diam.
- Jangan pernah publish ulang hasil yang statusnya tidak jelas — cek profil dulu. MultiPost tidak pernah auto-retry.
