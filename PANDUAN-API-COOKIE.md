# Panduan Ambil API & Cookie — Semua Platform MultiPost

Aturan emas: token & cookie = kata sandi. Ambil dari browsermu sendiri, tempel HANYA ke MultiPost (tab Akun — tersimpan terenkripsi DPAPI di PC-mu). **Jangan kirim ke chat mana pun.**

Dua cara umum mengambil cookie (berlaku semua platform):
- **F12**: login di Edge/Chrome → F12 → tab **Application** → **Cookies** → pilih domain → salin kolom **Value** dari cookie yang dicari.
- **Cookie-Editor** (ekstensi Chrome Web Store): login → klik ikon Cookie-Editor → **Export → Export as JSON** → tempel utuh ke MultiPost (mode `cookie`). Ini cara paling aman untuk platform yang butuh banyak cookie.

---

## 1. TikTok
- **Cookie (dipakai MultiPost)**: login `tiktok.com` → F12 → Application → Cookies → `www.tiktok.com` → cari **`sessionid`** → salin Value. MultiPost: Platform TikTok, Mode `cookie`, Nama cookie `sessionid`.
- **API**: ada (Content Posting API di developers.tiktok.com), TAPI client belum audit hanya bisa posting **private** — karena itu MultiPost tidak memakai API TikTok. Pakai cookie/browser.

## 2. Instagram
- **Cookie**: login `instagram.com` → pakai **Cookie-Editor Export JSON** (IG butuh `sessionid` + `csrftoken` + `ds_user_id` sekaligus). Cara F12: domain `.instagram.com`, cookie `sessionid`.
- **API (Meta Graph)** — syarat: akun IG **Business/Creator** dan terhubung ke Facebook Page.
  1. `developers.facebook.com` → My Apps → **Create App** → tipe Business.
  2. Di dashboard app: tambahkan produk **Instagram Graph API**.
  3. Buka **Tools → Graph API Explorer** → pilih app kamu → **Generate Access Token**, centang izin: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` → login & setujui.
  4. Token awal berlaku 1 jam → perpanjang: `developers.facebook.com/tools/debug/accesstoken` → **Extend Access Token** (±60 hari). Tempel token ini ke MultiPost.
  5. **IG User ID**: di Graph API Explorer jalankan `me/accounts` → catat Page yang terhubung → jalankan `{page-id}?fields=instagram_business_account` → angka `id` di hasilnya = IG User ID. Isi di kolom "ID platform" MultiPost.
  6. Ingat: mode API IG butuh **URL publik video** (API Meta tidak menerima file lokal).

## 3. Threads
- **Cookie**: login `threads.net` → Cookie-Editor Export JSON. Paling praktis sebenarnya **mode Browser**.
- **API**: masih di app Meta yang sama.
  1. Dashboard app → **Add Product → Threads API** → Set up.
  2. Di pengaturan Threads API: tambahkan akun Threads kamu sebagai **Threads Tester**, lalu terima undangannya di aplikasi Threads (Profil → Pengaturan → Akun → undangan/tester — terima dari notifikasi/Settings).
  3. Ambil token dari **Threads API Explorer** (di halaman produk Threads) dengan izin `threads_basic` + `threads_content_publish`.
  4. **Threads User ID**: jalankan query `me` di explorer itu → field `id`. Isi ke MultiPost + tempel tokennya.
  5. Sama seperti IG: mode API butuh URL publik video.

## 4. Facebook
- **Cookie**: WAJIB **JSON penuh** via Cookie-Editor di `facebook.com` (perlu `c_user` + `xs` + lainnya — 1 cookie tidak akan jalan).
- **API** — hanya untuk **Page** (profil personal tidak bisa):
  1. Pakai app & Graph API Explorer yang sama, izin tambahan: `pages_manage_posts`.
  2. Jalankan `me/accounts` → hasilnya daftar Page kamu, masing-masing dengan **`access_token` (Page Token)** dan **`id` (Page ID)**.
  3. MultiPost: tempel **Page Token**-nya (bukan user token), isi Page ID di kolom ID platform.
  4. Keuntungan FB: mode API bisa **upload file lokal langsung**, tidak butuh URL publik.

## 5. YouTube
- **Cookie**: TIDAK disarankan — cookie Google banyak & ketat, sesi impor sering ditolak/checkpoint. Pakai **mode Browser** (login sekali di jendela Edge MultiPost).
- **API**: ada (YouTube Data API v3 di console.cloud.google.com, OAuth client_secret.json), TAPI project yang belum diaudit Google hasil uploadnya **dipaksa private** — karena itu MultiPost tidak memakai API YouTube.

---

## Kalau gagal / kedaluwarsa
- Cookie mati kalau: logout, ganti password, atau platform meminta verifikasi ulang → ulangi langkah ambil cookie di atas.
- Token Meta mati tiap ±60 hari → ulangi Generate + Extend, tempel ulang di MultiPost (akun yang sama, jangan tambah akun baru).
- Publish gagal "belum login" pada mode cookie/browser → klik **Login Browser** di tab Akun untuk akun itu, login ulang, tutup jendela.
