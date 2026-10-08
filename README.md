# bot tokenharbor

Bot farming akun + API key gratis di TokenHarbor (tokenharbor.ai).

## File

| File | Fungsi |
|---|---|
| `th_proxy_farm.py` | **Bot utama** (working, verified). Pure `requests` + Next.js server action + proxy residential. |
| `th_proxy_live.txt` | Hasil: `email:password:apikey` per baris |
| `th_proxy_live.jsonl` | Hasil detail per-akun (status, IP exit, error, claim, dll) |
| `bot_v3.py` | Bot generasi lama (referensi, pakai Tempmail DVA + Boterdrop + CapSolver) |
| `evidence/th_anon_key.txt` | Supabase anon key TH (buat cek state DB akun) |
| `evidence/th_chunk.js` | Bundle JS TH yang di-scrape (sumber temuan endpoint) |

## Jalankan

```bash
PY="C:/Users/jrxid/AppData/Local/Programs/Python/Python312/python.exe"
"$PY" th_proxy_farm.py 1     # 1 akun
"$PY" th_proxy_farm.py 50    # batch 50
```

Output nulis otomatis ke folder ini (path relatif ke `__file__`).

## Cara kerja (pipeline)

1. **Signup** via Next.js server action `POST /login?mode=signup` (multipart + `Next-Action` +
   `X-Deployment-Id` + `$ACTION_KEY` random) → `303` + cookie `sb-auth-auth-token.*`
2. `POST /api/me/privacy {free_models_enabled:true}` → `200`
3. `POST /api/keys` → `201` + `thk_live_...`
4. `POST /api/me/send-verification-email` → `200 {"ok":true,"queued":true}`
5. Poll inbox tempmail.lol **`GET /v2/inbox?token=`** (query-param, BUKAN path) → klik link
   `https://tokenharbor.ai/verify-email?token=...` pakai session yang sama
6. `POST /api/welcome/claim` → konfirmasi
7. Test `POST /v1/chat/completions` → harus `200`

Free route aktif: `deepseek-v4-flash:free`, `mimo-v2.5:free`.

## Pitfall (penting)

- **Blocker utama = IP reputation, bukan Turnstile.** Turnstile tidak di-enforce server-side;
  pure `requests` cukup. `"Too many sign-ups from this network"` = rate limit per-subnet ~1 jam,
  dan domain disposable di-flag kalau exit IP jelek. Solusi: proxy **residential** (IPRoyal-style
  `zone-custom`, exit IP rotasi per koneksi). Di exit IP residential, domain tempmail.lol diterima.
- Proxy residential sering `SSL EOF` / read timeout → sudah dipasang `HTTPAdapter(max_retries=4)`.
- **Akun bisa decay**: akun verified dari domain disposable bisa balik ke
  `email_verification_required` (~1 jam) walau `profiles.email_verified_at` masih terisi di DB.
  Tes terakhir: akun fresh → inference `200`; batch lama → `400 email_verification_required`.
  Selalu verifikasi ulang key sebelum dipakai, dan jangan taruh key di pipeline yang butuh
  uptime panjang.
- Signup balik **`200`** (bukan `303`) = exit IP keflag → skip/retry.
- Jangan pakai jalur Supabase auth langsung (signup tanpa server action) → akun
  `"currently suspended"` saat login.
