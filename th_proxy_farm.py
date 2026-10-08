#!/usr/bin/env python3
"""
TokenHarbor Farm Bot — output API KEY DOANG.

Signup (Next.js server action) -> verify link -> claim -> API key -> test inference.

Output:
  apikeys.txt    -> 1 API key per baris (cuma key, no email/password)
  farm_log.jsonl -> detail per-akun (email/password/status/ip/error) buat record

Pakai:
  python th_proxy_farm.py          # interaktif: ditanya mau berapa akun
  python th_proxy_farm.py 50       # langsung 50 akun
  python th_proxy_farm.py -i       # paksa mode interaktif
"""
import time, random, string, uuid, json, os, sys, re
import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings()

API = "https://tokenharbor.ai"
from pathlib import Path
HERE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT_KEYS = os.path.join(HERE, "apikeys.txt")
OUT_LOG = os.path.join(HERE, "farm_log.jsonl")
FREE_MODEL = "deepseek-v4-flash:free"

# Daftar proxy (Http/Https/Socks).
# Contoh format: "http://user:pass@ip:port" atau "http://ip:port"
PROXIES = [
    "https://brd-customer-hl_af7d432a-zone-center:m1gbtzpn457t@brd.superproxy.io:44445",
    "https://user-W7nj1LLKsgjG6sUt-type-residential-country-SG:LlOdH9jcC5rQ9tIQ@geo.g-w.info:10443"
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
VERIFY_RE = re.compile(r'https://(?:www\.)?tokenharbor\.ai/verify-email\?token=[^\s"\'<>)]+')


# ─────────────────────────── helpers ───────────────────────────

def newpass():
    return "Th" + ''.join(random.choices(string.ascii_letters + string.digits, k=9)) + "!x9"


def format_proxy(raw_proxy, idx):
    if not raw_proxy:
        return None
    return raw_proxy


def rotate_proxy(s, idx):
    """Pilih proxy berikutnya dari daftar PROXIES jika ada."""
    if not PROXIES:
        return None
    raw = PROXIES[idx % len(PROXIES)]
    proxy = format_proxy(raw, idx)
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return proxy


def new_session(proxy=None):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    ad = HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5,
                                       allowed_methods=frozenset(["GET", "POST"])))
    s.mount("https://", ad)
    s.mount("http://", ad)
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
        s.verify = False
    return s


def tm_inbox():
    d = requests.post("https://api.tempmail.lol/v2/inbox/create", timeout=20).json()
    addr, tok = d.get("address") or "", d.get("token") or ""
    if not addr or not tok:
        return None
    return "tll", addr, tok


def mtm_inbox():
    try:
        djson = requests.get("https://api.mail.tm/domains", timeout=20).json()
        mem = djson.get("hydra:member") or []
        dom = mem[0].get("domain") or "" if mem else ""
        if not dom:
            return None
        addr = "t" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@" + dom
        pwd = "Mail" + ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + "!9"
        requests.post("https://api.mail.tm/accounts",
                      json={"address": addr, "password": pwd}, timeout=20)
        r = requests.post("https://api.mail.tm/token",
                          json={"address": addr, "password": pwd}, timeout=20)
        tok = (r.json().get("token") or "") if r else ""
        if not addr or not tok:
            return None
        return "mtm", addr, tok
    except Exception:
        return None


INBOX = {"tll": tm_inbox, "mtm": mtm_inbox}


def get_inbox(kind="tll"):
    for k in ([kind] + [k2 for k2 in INBOX if k2 != kind]):
        try:
            out = INBOX[k]()
            if out:
                return out
        except Exception:
            continue
    return None


def poll_verify(kind, token, timeout=180):
    """Poll inbox -> balikin link verifikasi (endpoint WAJIB query-param)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if kind == "tll":
                r = requests.get(f"https://api.tempmail.lol/v2/inbox?token={token}", timeout=15)
                if r.text.strip():
                    d = r.json()
                    for m in (d.get("email") or d.get("emails") or d.get("messages") or []):
                        blob = " ".join(str(m.get(k, "")) for k in ("body", "html", "text", "subject"))
                        mm = VERIFY_RE.search(blob)
                        if mm:
                            return mm.group(0)
            else:
                r = requests.get("https://api.mail.tm/messages",
                                 headers={"Authorization": f"Bearer {token}"}, timeout=15)
                for m in r.json().get("hydra:member", []):
                    r2 = requests.get(f"https://api.mail.tm/messages/{m['id']}",
                                      headers={"Authorization": f"Bearer {token}"}, timeout=15)
                    js = r2.json()
                    blob = str(js.get("text", "")) + " " + str(js.get("html", ""))
                    mm = VERIFY_RE.search(blob)
                    if mm:
                        return mm.group(0)
        except Exception:
            pass
        time.sleep(4)
    return None


def test_key(key, proxy=None, timeout=120):
    try:
        px = {"http": proxy, "https": proxy} if proxy else None
        r = requests.post(f"{API}/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"},
                          json={"model": FREE_MODEL,
                                "messages": [{"role": "user", "content": "hi"}],
                                "max_tokens": 5},
                          proxies=px,
                          verify=False if proxy else True,
                          timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:120]


def save_key(key):
    with open(OUT_KEYS, "a", encoding="utf-8") as f:
        f.write(key + "\n")
    seen, uniq = set(), []
    for ln in open(OUT_KEYS, encoding="utf-8"):
        ln = ln.strip()
        if ln and ln not in seen:
            seen.add(ln)
            uniq.append(ln)
    with open(OUT_KEYS, "w", encoding="utf-8") as f:
        f.write("\n".join(uniq) + "\n")


def log_rec(rec):
    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# ─────────────────────────── signup: precheck + token ───────────────────────────

def signup_err(text):
    for m in re.finditer(r'\d+:\s*\{\s*"error"\s*:\s*"([^"]+)"', text):
        v = m.group(1)
        if v and not v.startswith("$"):
            return v
    m = re.search(r'"error"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else ""


def precheck(s):
    """GET /api/auth/signup-precheck?fp=<uuid> -> (needCaptcha bool, fp str, raw dict)."""
    fp = str(uuid.uuid4())
    try:
        r = s.get(f"{API}/api/auth/signup-precheck?fp={fp}", timeout=25)
        j = r.json() if r.status_code == 200 else {}
        need = bool(j.get("needCaptcha"))
        return need, fp, j
    except Exception:
        # precheck gagal -> asumsikan butuh token (aman) biar gak salah skip
        return True, fp, {}


def get_turnstile_token(timeout=45, headless=True):
    """Ambil token Turnstile lewat Camoufox (kalau tersedia). None = tidak bisa."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except Exception:
        return None
    import asyncio
    READ = ('() => document.querySelector("[name=\\"cf-turnstile-response\\"]")'
            '?.value || ""')
    async def _run():
        async with AsyncCamoufox(headless=headless) as b:
            page = await b.new_page()
            await page.goto(f"{API}/login?mode=signup", wait_until="networkidle",
                            timeout=60000)
            t0 = time.time()
            while time.time() - t0 < timeout - 40:
                v = await page.evaluate(READ)
                if v and len(v) > 20:
                    return v
                await asyncio.sleep(0.5)
            return None
    return asyncio.run(_run())


# ─────────────────────────── core flow ───────────────────────────

def farm(idx, proxy, verbose=True):
    rec = {"index": idx, "status": "failed", "email": "", "password": "", "api_key": "",
           "error": "", "claim": "", "ip": "", "proxy": proxy or "direct", "inference": ""}
    s = new_session(proxy)

    try:
        try:
            rec["ip"] = s.get("https://api.ipify.org", timeout=25).text.strip()
        except Exception as e:
            rec["error"] = "proxy_dead: " + str(e)[:60]
            if verbose: print(f"  [{idx}] proxy mati, skip", flush=True)
            return rec
        if verbose: print(f"  [{idx}] exit IP: {rec['ip']}", flush=True)

        inbox = get_inbox("tll")
        if not inbox:
            rec["error"] = "inbox_unavailable"
            if verbose: print(f"  [{idx}] semua provider inbox gagal, skip", flush=True)
            return rec
        kind, email, mtok = inbox
        pwd = newpass()
        rec["email"], rec["password"] = email, pwd
        if verbose: print(f"  [{idx}] email: {email}", flush=True)

        # 1) halaman signup -> action id + deploy id dinamis
        r = None
        for attempt in range(6):
            try:
                r = s.get(f"{API}/login?mode=signup", timeout=45)
                if r.status_code < 500:
                    break
                if attempt == 5:
                    break
                proxy = rotate_proxy(s, idx)
                if verbose: print(f"  [{idx}] exit {r.status_code}, ganti IP ({attempt+1}/5)...", flush=True)
                time.sleep(2)
            except requests.RequestException as e:
                if attempt == 5:
                    rec["error"] = "proxy_bad_exit: " + str(e)[:80]
                    if verbose: print(f"  [{idx}] proxy bermasalah setelah 6x, skip", flush=True)
                    return rec
                proxy = rotate_proxy(s, idx)
                if verbose: print(f"  [{idx}] koneksi gagal, ganti IP ({attempt+1}/5)...", flush=True)
        if r is None or r.status_code >= 500:
            rec["error"] = "proxy_unreachable"
            if verbose: print(f"  [{idx}] proxy terus 5xx setelah 6x ganti IP, skip", flush=True)
            return rec
        dep = re.search(r'dpl_([A-Za-z0-9]+)', r.text)
        deploy_id = f"dpl_{dep.group(1)}" if dep else ""
        act = re.search(r'"id":"([a-f0-9]{40,50})"', r.text) or re.search(r'[a-f0-9]{40,50}', r.text)
        action_id = act.group(1) if act and act.groups() else (act.group(0) if act else "")
        time.sleep(2)

        # 2) signup via server action — precheck dulu, token kalau perlu
        need, fp, pj = precheck(s)
        if verbose:
            print(f"  [{idx}] precheck needCaptcha={need}" + (f" ({pj.get('error','')})" if not need and pj.get('error') else ""), flush=True)

        def build_and_post(token=None):
            nb = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]
            fields = ["1_$ACTION_REF_1", "", "1_$ACTION_1:0", json.dumps({"id": action_id, "bound": "$@1"}),
                      "1_$ACTION_1:1", '["$undefined"]', "1_$ACTION_KEY", uuid.uuid4().hex,
                      "1_device_fingerprint", fp, "1_timezone", "Asia/Jakarta",
                      "1_next", "", "1_email", email, "1_password", pwd, "0", '["$undefined","$K1"]']
            if token:
                fields += ["1_cf-turnstile-response", token,
                           "cf-turnstile-response", token]
            parts = []
            for i in range(0, len(fields), 2):
                parts += [f"--{nb}", f'Content-Disposition: form-data; name="{fields[i]}"', "", fields[i + 1]]
            body = "\r\n".join(parts) + f"\r\n--{nb}--\r\n"
            return s.post(f"{API}/login?mode=signup",
                          headers={"Content-Type": f"multipart/form-data; boundary={nb}",
                                   "Next-Action": action_id, "X-Deployment-Id": deploy_id,
                                   "Accept": "text/x-component", "Origin": API,
                                   "Referer": f"{API}/login?mode=signup"},
                          data=body.encode(), timeout=45, allow_redirects=False)

        r = build_and_post()
        for attempt in range(6):
            if r.status_code not in (502, 503, 504):
                break
            if attempt == 5:
                rec["error"] = "proxy_502_after_retry"
                if verbose: print(f"  [{idx}] proxy terus 502 setelah 6x ganti IP, skip", flush=True)
                return rec
            proxy = rotate_proxy(s, idx)
            if verbose: print(f"  [{idx}] exit {r.status_code}, ganti IP ({attempt+1}/5)...", flush=True)
            time.sleep(2)
            try:
                r = build_and_post()
            except requests.RequestException as e:
                if verbose: print(f"  [{idx}] POST gagal ({type(e).__name__}), coba IP lain...", flush=True)

        low = r.text.lower()
        reason = signup_err(r.text)
        # kalau precheck bilang butuh captcha, atau pertama kali jawab needCaptcha -> ambil token & kirim ulang sekali
        if (need or "needcaptcha" in (reason or "").lower() or
                "human check" in (reason or "").lower()):
            if r.status_code == 303:
                pass  # sudah sukses walau precheck bilang butuh — beres
            else:
                tok = get_turnstile_token()
                if tok:
                    if verbose: print(f"  [{idx}] token captcha ({len(tok)} chars), kirim ulang...", flush=True)
                    r = build_and_post(token=tok)
                    reason = signup_err(r.text)
                    low = r.text.lower()
                elif verbose:
                    print(f"  [{idx}] butuh token captcha tapi Camoufox/venv tidak tersedia — skip", flush=True)
        if "many sign-ups" in low or "take a breath" in low:
            rec["error"] = "NETWORK_RATE_LIMIT"; print(f"  [{idx}] rate limit IP", flush=True); return rec
        if "team has been alerted" in low or "couldn't create" in low:
            rec["error"] = "DOMAIN_REJECTED_OR_IP_BAD"; print(f"  [{idx}] domain/IP ditolak: {reason[:100]}", flush=True); return rec
        lowv = (reason or "").lower()
        if r.status_code != 303:
            if "needcaptcha" in lowv or "human check" in lowv or "captcha" in lowv:
                rec["error"] = f"NEED_CAPTCHA ({r.status_code})"
                print(f"  [{idx}] butuh token captcha (IP AMAN, {r.status_code}) {reason[:100]}", flush=True); return rec
            rec["error"] = f"signup_{r.status_code}_other"
            print(f"  [{idx}] respons {r.status_code}: {reason or '(kosong)'[:120]}", flush=True); return rec
        if verbose: print(f"  [{idx}] signup OK (303)", flush=True)

        # 3) enable free models + bikin key
        s.post(f"{API}/api/me/privacy", json={"free_models_enabled": True},
               headers={"Content-Type": "application/json", "Origin": API}, timeout=30)
        r = s.post(f"{API}/api/keys", json={"label": f"farm-{idx}"},
                   headers={"Content-Type": "application/json", "Origin": API,
                            "Referer": f"{API}/dashboard"}, timeout=30)
        try:
            rec["api_key"] = r.json().get("plaintext", "")
        except Exception:
            rec["api_key"] = ""
        if not rec["api_key"]:
            rec["error"] = f"key_{r.status_code}"
            print(f"  [{idx}] gagal bikin key ({r.status_code})", flush=True); return rec
        if verbose: print(f"  [{idx}] key dibuat", flush=True)

        # 4) verifikasi email (klik link) + retry kalau API masih nolak
        for attempt in (1, 2):
            s.post(f"{API}/api/me/send-verification-email", data="",
                   headers={"Content-Type": "application/json", "Origin": API,
                            "Referer": f"{API}/dashboard"}, timeout=30)
            link = poll_verify(kind, mtok, 120 if attempt == 1 else 90)
            if link:
                try:
                    s.get(link, timeout=30, allow_redirects=True)
                except Exception:
                    pass
                if verbose: print(f"  [{idx}] verify link diklik", flush=True)
            code, body = test_key(rec["api_key"], proxy=proxy)
            rec["inference"] = f"{code} {body[:120]}"
            if code == 200:
                break
            if "email_verification_required" in body and attempt == 1:
                if verbose: print(f"  [{idx}] masih diminta verify, retry sekali", flush=True)
                time.sleep(5)
                continue
            if attempt == 1:
                if verbose: print(f"  [{idx}] menunggu 8s, coba inference lagi...", flush=True)
                time.sleep(8)
                code, body = test_key(rec["api_key"], proxy=proxy)
                rec["inference"] = f"{code} {body[:120]}"
                if code == 200:
                    break
            break

        s.post(f"{API}/api/welcome/claim", data="",
               headers={"Content-Type": "application/json", "Origin": API,
                        "Referer": f"{API}/dashboard"}, timeout=30)

        if code == 200:
            rec["status"] = "success"
            save_key(rec["api_key"])
            if verbose: print(f"  [{idx}] ✔ LIVE", flush=True)
        else:
            rec["error"] = f"inference_{code}"
            if verbose: print(f"  [{idx}] ✘ inference {code}", flush=True)
    except Exception as e:
        rec["error"] = str(e)[:170]
        if verbose: print(f"  [{idx}] EXC {rec['error'][:110]}", flush=True)
    return rec


def run_batch(n, start=1, proxies=None, workers=1):
    ok = 0
    proxies = proxies if proxies else []
    jobs = list(range(start, start + n))

    def do(i):
        raw_proxy = proxies[(i - 1) % len(proxies)] if proxies else None
        proxy = format_proxy(raw_proxy, i)
        rec = farm(i, proxy)
        log_rec(rec)
        return rec

    if workers > 1:
        import concurrent.futures as futures
        with futures.ThreadPoolExecutor(max_workers=workers) as ex:
            for rec in ex.map(do, jobs):
                if rec["status"] == "success":
                    ok += 1
        return ok

    for i in jobs:
        rec = do(i)
        if rec["status"] == "success":
            ok += 1
        if i < start + n - 1:
            time.sleep(random.uniform(8, 15))
    return ok


def ask_count():
    while True:
        try:
            raw = input("Mau farm berapa akun? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if raw in ("q", "quit", "exit"):
            return 0
        if not raw:
            raw = "1"
        try:
            n = int(raw)
        except ValueError:
            print("  Angka ya, contoh: 10")
            continue
        if n < 1:
            print("  Minimal 1.")
            continue
        return n


def main():
    import argparse
    ap = argparse.ArgumentParser(description="TokenHarbor Farm Bot")
    ap.add_argument("count", nargs="?", type=int, default=None,
                    help="jumlah akun (tanpa ini = mode interaktif)")
    ap.add_argument("-i", "--interactive", action="store_true",
                    help="paksa mode interaktif")
    ap.add_argument("--proxy", metavar="SPEC",
                    help="pakai proxy, contoh: --proxy 'http://user:pass@host:port'")
    ap.add_argument("--direct", action="store_true",
                    help="paksa direct connection (tanpa proxy, abaikan PROXIES)")
    ap.add_argument("--gacha", action="store_true",
                    help="gacha proxy acak dari proxies_good.txt (ala dahl-farm); "
                         "auto-run filter_proxies.py kalau pool kosong")
    ap.add_argument("--all", action="store_true",
                    help="(gacha) pakai SEMUA proxy hasil scrape di proxies_all.txt, "
                         "bukan cuma yang lolos filter -- reroll lebih banyak diperlukan")
    ap.add_argument("--gacha-file", default="",
                    help="(gacha) file pool proxy kustom untuk gacha")
    ap.add_argument("--reroll", type=int, default=20,
                    help="maks reroll gacha per akun (default: 20)")
    ap.add_argument("-w", "--workers", type=int, default=1,
                    help="jumlah worker paralel (default: 1)")
    args = ap.parse_args()

    # ── mode gacha ──
    if args.gacha:
        return run_gacha(args)

    # pilih sumber proxy: --proxy > PROXIES di file > direct
    if args.proxy:
        proxies = [args.proxy]
        mode = "proxy"
    elif args.direct:
        proxies = []
        mode = "direct"
    elif PROXIES:
        proxies = list(PROXIES)
        mode = "proxy"
    else:
        proxies = []
        mode = "direct"

    interactive = args.interactive or args.count is None
    n = args.count if args.count else 0

    if not interactive:
        print(f"TokenHarbor Farm | {n} akun ({mode.upper()})" +
              (f" x{args.workers} workers" if args.workers > 1 else ""))
        ok = run_batch(n, proxies=proxies)
        print(f"\n=== {ok}/{n} live -> {OUT_KEYS} ===")
        return

    print(f"TokenHarbor Farm Bot ({mode.upper()}) — ketik 'q' buat keluar")
    total_ok = 0
    idx = 1
    while True:
        n = ask_count()
        if n == 0:
            break
        ok = run_batch(n, start=idx, proxies=proxies, workers=args.workers)
        idx += n
        total_ok += ok
        print(f"\n  batch ini: {ok}/{n} live | total: {total_ok} key -> {OUT_KEYS}\n")
    print(f"\n=== selesai: {total_ok} key live -> {OUT_KEYS} ===")


# ─────────────────────────── gacha mode ───────────────────────────

GACHA_FILE = HERE / "proxies_good.txt"
ALL_FILE = HERE / "proxies_all.txt"


def load_pool_lines(path):
    p = Path(path)
    if p.exists():
        return [l.strip() for l in p.read_text(
            encoding="utf-8", errors="ignore").splitlines()
            if l.strip() and not l.startswith("#")]
    return []


def load_good_proxies():
    return load_pool_lines(GACHA_FILE)


def run_gacha(args):
    import subprocess
    good, pool_label = [], ""

    if args.gacha_file:
        good = load_pool_lines(args.gacha_file)
        pool_label = f"kustom: {args.gacha_file}"
    elif args.all:
        if not ALL_FILE.exists() or ALL_FILE.stat().st_size == 0:
            print("proxies_all.txt kosong -> scrape proxy publik dulu...\n")
            subprocess.run([sys.executable, str(HERE / "filter_proxies.py"),
                            "0", "--scrape-only"], check=False)
        good = load_pool_lines(ALL_FILE)
        pool_label = f"SEMUA proxy ({ALL_FILE.name})"
    else:
        good = load_good_proxies()
        pool_label = GACHA_FILE.name
        if not good:
            need = max(20, (args.count or 5) * 3)
            print(f"proxies_good.txt kosong -> jalankan filter_proxies.py (target {need})...\n")
            subprocess.run([sys.executable, str(HERE / "filter_proxies.py"), str(need)])
            good = load_good_proxies()

    if not good:
        print("Tidak ada proxy. Farm dibatalkan.")
        return 1

    n = args.count or 1
    interactive = args.interactive or args.count is None
    if interactive:
        n = ask_count()
        if n == 0:
            return 0

    reroll = args.reroll
    if args.all and args.reroll == 20:
        reroll = 40
    print(f"\n== GACHA PROXY FARM: {n} akun | pool: {len(good)} proxy ({pool_label}) | reroll: {reroll} ==")
    ok = 0
    for i in range(1, n + 1):
        success = False
        for roll in range(reroll):
            gacha_p = random.choice(good)
            masked = re.sub(r"://([^:@]+):[^@]+@", r"://\1:***@", gacha_p)
            if roll == 0:
                print(f"\n[{i:02d}] Gacha -> {masked}", flush=True)
            else:
                print(f"[{i:02d}] Reroll ({roll+1}/{reroll}) -> {masked}", flush=True)
            try:
                rec = farm(i, gacha_p, verbose=False)
            except Exception as e:
                print(f"  gagal: {type(e).__name__}: {str(e)[:80]}", flush=True)
                continue
            err = (rec.get("error") or "").lower()
            if rec["status"] == "success":
                print(f"  [{i:02d}] ✔ KEY: {rec['api_key'][:26]}...", flush=True)
                ok += 1
                success = True
                break
            if ("rate" in err or "502" in err or "503" in err or
                    "proxy" in err or "429" in err or "flagged" in err or
                    "domain" in err):
                print(f"  [{i:02d}] {rec['error'][:70]} -> gacha proxy lain...", flush=True)
                continue
            print(f"  [{i:02d}] {rec['error'][:70]} -> gacha proxy lain...", flush=True)
        if not success:
            print(f"[{i:02d}] GAGAL setelah {reroll}x reroll.", flush=True)
        if i < n:
            time.sleep(random.uniform(4, 8))
    print(f"\n=== {ok}/{n} live -> {OUT_KEYS} ===")
    return 0


if __name__ == "__main__":
    main()