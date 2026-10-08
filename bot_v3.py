#!/usr/bin/env python3
"""
botbor v3.1 - TokenHarbor Auto-Register
Updated: 2026-09-12
Free models: mimo-v2.5:free, deepseek-v4-flash:free, deepseek-v4.1-flash:free
Tempik + Boterdrop + proxy + fallback email
"""

import requests, re, json, random, string, uuid, urllib.parse, time, sys, os, threading

# ==================== CONFIG ====================

TEMPMAIL_API = "https://mail.dvaai.web.id"
BOTERDROP_URL = "http://127.0.0.1:8000"
TURNSTILE_SITEKEY = "0x4AAAAAADBuC8Knz1EJZx9-"

BASE = "https://tokenharbor.ai"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

ACTION_SIGNUP = "6033fd22f7d7a90f802ba941874ad78ae085351a7d"
ACTION_SIGNIN = "6057a6b9d9874f0d3abf096c307e763454056bbb4f"

FREE_MODELS = [
    "mimo-v2.5:free",
    "deepseek-v4-flash:free",
    "deepseek-v4.1-flash:free",
]

ALL_MODELS = [
    "mimo-v2.5:free", "deepseek-v4-flash:free", "deepseek-v4.1-flash:free",
    "mimo-v2.5", "mimo-v2.5-pro",
    "deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4.1-flash", "deepseek-v3.2",
    "glm-5.3-flash", "glm-5.3", "glm-5.2",
    "qwen3.8-flash", "qwen3.8-27b", "qwen3.8-max", "qwen3.7-max",
    "kimi-k3", "kimi-k2.6",
    "gemini-3.8-flash", "gemini-3.7-flash",
    "claude-sonnet-5", "claude-opus-5", "claude-fable-5.1", "claude-fable-5",
    "claude-sonnet-4.6", "claude-opus-4.8",
    "gpt-6-astra", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.5",
    "grok-4.6", "grok-4.5",
    "th-orchestra",
]

ROUTER = urllib.parse.quote(
    '["",{"children":["login",{"children":["__PAGE__",{},null,null,0]},null,null,0]},null,null,20]'
)

DIR = os.path.dirname(os.path.abspath(__file__))
APIKEY_FILE = os.path.join(DIR, "apikeys.txt")
ACCOUNT_FILE = os.path.join(DIR, "accounts.json")

# PROXY
PROXY_FILE = os.path.join(DIR, "proxy.txt")
_proxy_pool = []
_proxy_idx = 0
_use_proxy = True


# ==================== PROXY ====================

def _load_proxies():
    global _proxy_pool
    _proxy_pool = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "://" in line:
                    _proxy_pool.append({"http": line, "https": line})
    return len(_proxy_pool)


def _get_proxy():
    global _proxy_idx
    if not _use_proxy or not _proxy_pool:
        return {}
    p = _proxy_pool[_proxy_idx % len(_proxy_pool)]
    _proxy_idx += 1
    return p


# ==================== LOAD/SAVE ====================

def load_accounts():
    if os.path.exists(ACCOUNT_FILE):
        try:
            with open(ACCOUNT_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def save_accounts(data):
    with open(ACCOUNT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_keys():
    if os.path.exists(APIKEY_FILE):
        with open(APIKEY_FILE) as f:
            return [l.strip() for l in f if l.strip()]
    return []


def save_key(key):
    with open(APIKEY_FILE, "a") as f:
        f.write(f"{key}\n")


# ==================== HELPERS ====================

def rand_pwd():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + '!Aa1'


def solve_turnstile():
    """Solve Turnstile via Boterdrop-Solver"""
    try:
        r = requests.get(f"{BOTERDROP_URL}/turnstile",
            params={"url": f"{BASE}/login", "sitekey": TURNSTILE_SITEKEY},
            timeout=30)
        if r.status_code != 202:
            return None
        task_id = r.json().get("task_id")
        if not task_id:
            return None
        for _ in range(60):
            time.sleep(3)
            r2 = requests.get(f"{BOTERDROP_URL}/result", params={"id": task_id}, timeout=15)
            data = r2.json()
            if data.get("status") == "success":
                return data.get("value", "")
            elif data.get("status") in ("error", None):
                return None
    except Exception as e:
        print(f"    Boterdrop error: {e}")
    return None


# ==================== EMAIL PROVIDERS ====================

def create_email_tempik():
    try:
        r = requests.get(f"{TEMPMAIL_API}/api/session", timeout=10)
        session_id = r.json().get("sessionId", "")
        if not session_id:
            return None, None, None
        r2 = requests.post(f"{TEMPMAIL_API}/api/inboxes",
            json={}, headers={"x-session-id": session_id}, timeout=10)
        inbox = r2.json().get("address", "")
        if inbox:
            return inbox, session_id, "tempik"
    except:
        pass
    return None, None, None


def create_email_tempmail():
    try:
        r = requests.post("https://api.tempmail.lol/v2/inbox/create", timeout=10)
        data = r.json()
        if "address" in data:
            return data["address"], data["token"], "tempmail"
    except:
        pass
    return None, None, None


def create_email_mailtm():
    import secrets
    try:
        r = requests.get("https://api.mail.tm/domains", timeout=10)
        domains = [m["domain"] for m in r.json().get("hydra:member", []) if m.get("isActive", True)]
        if not domains:
            return None, None, None
        email = f"{secrets.token_hex(6)}@{domains[0]}"
        pwd = rand_pwd()
        requests.post("https://api.mail.tm/accounts",
            json={"address": email, "password": pwd}, timeout=10)
        t = requests.post("https://api.mail.tm/token",
            json={"address": email, "password": pwd}, timeout=10)
        if t.status_code == 200:
            return email, t.json().get("token"), "mailtm"
    except:
        pass
    return None, None, None


def create_email():
    """Create email: tempmail.lol -> tempik -> mail.tm"""
    for provider_fn in [create_email_tempmail, create_email_tempik, create_email_mailtm]:
        email, token, provider = provider_fn()
        if email:
            return email, token, provider
    return None, None, None


# ==================== EMAIL MESSAGES ====================

def get_messages_tempik(session_id, email):
    try:
        r = requests.get(f"{TEMPMAIL_API}/api/inboxes/{email}/messages",
            headers={"x-session-id": session_id}, timeout=10)
        if r.status_code == 200:
            return r.json() if isinstance(r.json(), list) else []
    except:
        pass
    return []


def get_messages_tempmail(token):
    try:
        r = requests.get(f"https://api.tempmail.lol/v2/inbox?token={token}", timeout=10)
        return r.json().get("emails", [])
    except:
        pass
    return []


def get_messages_mailtm(token):
    try:
        r = requests.get("https://api.mail.tm/messages",
            headers={"Authorization": f"Bearer {token}"}, timeout=10)
        result = []
        for m in r.json().get("hydra:member", []):
            full = requests.get(f"https://api.mail.tm/messages/{m['id']}",
                headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
            html = full.get("html", "")
            text = full.get("text", "")
            body = html[0] if isinstance(html, list) and html else text
            result.append({"body": body})
        return result
    except:
        pass
    return []


def get_messages(mail_token, email, provider):
    if provider == "tempik":
        return get_messages_tempik(mail_token, email)
    elif provider == "tempmail":
        return get_messages_tempmail(mail_token)
    elif provider == "mailtm":
        return get_messages_mailtm(mail_token)
    return []


# ==================== SIGNUP ====================

def make_signup_body(email, pwd, turnstile_token="", device_fp=None):
    if device_fp is None:
        device_fp = str(uuid.uuid4())
    bd = "----WebKitFormBoundary" + ''.join(
        random.choices(string.ascii_uppercase + string.digits, k=16)
    )
    def af(n, v=""):
        return f'--{bd}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}'
    parts = [
        af("1_$ACTION_REF_1"),
        af("1_$ACTION_1:0", json.dumps({"id": ACTION_SIGNUP, "bound": "$@1"})),
        af("1_$ACTION_1:1", '["$undefined"]'),
        af("1_$ACTION_KEY"),
        af("1_device_fingerprint", device_fp),
        af("1_timezone", "Asia/Jakarta"),
        af("1_next", ""),
        af("1_email", email),
        af("1_password", pwd),
        af("1_invite_code", ""),
    ]
    if turnstile_token:
        parts.append(af("1_cf-turnstile-response", turnstile_token))
    parts.append(af("0", '["$undefined","$K1"]'))
    body = "\r\n".join(parts) + f"\r\n--{bd}--\r\n"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={bd}",
        "Accept": "text/x-component",
        "Next-Action": ACTION_SIGNUP,
        "Next-Router-State-Tree": ROUTER,
        "Origin": BASE,
        "Referer": f"{BASE}/login",
    }
    return body, headers


def make_login_body(email, pwd):
    bd = "----WebKitFormBoundary" + ''.join(
        random.choices(string.ascii_uppercase + string.digits, k=16)
    )
    def af(n, v=""):
        return f'--{bd}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}'
    parts = [
        af("1_$ACTION_REF_1"),
        af("1_$ACTION_1:0", json.dumps({"id": ACTION_SIGNIN, "bound": "$@1"})),
        af("1_$ACTION_1:1", '["$undefined"]'),
        af("1_$ACTION_KEY"),
        af("1_device_fingerprint", str(uuid.uuid4())),
        af("1_timezone", "Asia/Jakarta"),
        af("1_next", "/dashboard"),
        af("1_email", email),
        af("1_password", pwd),
        af("0", '["$undefined","$K1"]'),
    ]
    body = "\r\n".join(parts) + f"\r\n--{bd}--\r\n"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={bd}",
        "Accept": "text/x-component",
        "Next-Action": ACTION_SIGNIN,
        "Next-Router-State-Tree": ROUTER,
        "Origin": BASE, "Referer": f"{BASE}/login",
    }
    return body, headers


# ==================== EMAIL VERIFY ====================

def verify_email(email, mail_token, provider, max_wait=120):
    import quopri
    start = time.time()
    while time.time() - start < max_wait:
        try:
            msgs = get_messages(mail_token, email, provider)
            for em in msgs:
                body = em.get("body", "") or em.get("text", "") or ""
                try:
                    body = quopri.decodestring(body.encode('utf-8', errors='replace')).decode('utf-8', errors='replace')
                except:
                    pass
                links = re.findall(r'(https://tokenharbor\.ai/verify-email\?[^\s"<>]+)', str(body))
                if links:
                    requests.get(links[0], timeout=15, allow_redirects=True)
                    return True
        except:
            pass
        time.sleep(8)
    return False


def verify_email_bg(email, mail_token, provider):
    t = threading.Thread(target=verify_email, args=(email, mail_token, provider), daemon=True)
    t.start()


def wait_for_verification(key, max_wait=120):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = requests.post(f"{BASE}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "mimo-v2.5:free", "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 3}, timeout=15)
            if r.status_code == 200:
                return True
            if "Verify your email" not in r.text:
                return True
        except:
            pass
        time.sleep(5)
    return False


# ==================== REGISTER ====================

def register_one():
    print("  [1/8] Generate temp email...", end=" ", flush=True)
    email, mail_token, provider = create_email()
    if not email:
        print("GAGAL")
        return None, "temp email failed"
    pwd = rand_pwd()
    print(f"OK -> {email} ({provider})")

    device_fp = str(uuid.uuid4())

    print("  [2/8] Check captcha...", end=" ", flush=True)
    need_captcha = False
    try:
        r = requests.get(f"{BASE}/api/auth/signup-precheck?fp={device_fp}",
            proxies=_get_proxy(), timeout=10)
        need_captcha = r.json().get("needCaptcha", False)
    except:
        pass
    print("required" if need_captcha else "skip")

    print("  [3/8] Solve Turnstile...", end=" ", flush=True)
    turnstile_token = solve_turnstile()
    print("OK" if turnstile_token else "WARN")

    print("  [4/8] Inject load...", end=" ", flush=True)
    proxy = _get_proxy()
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    try:
        s.get(f"{BASE}/login", proxies=proxy, timeout=20)
    except:
        pass
    print("OK")
    time.sleep(5)

    print("  [5/8] Inject Salt...", end=" ", flush=True)
    body, headers = make_signup_body(email, pwd, turnstile_token, device_fp)
    r = s.post(f"{BASE}/login", data=body, headers=headers, proxies=proxy, timeout=25)

    if "signedIn" not in r.text:
        errors = re.findall(r'"error":"([^"]+)"', r.text)
        real_errors = [e for e in errors if e not in ('$f', '$undefined')]
        err = real_errors[0] if real_errors else f"HTTP {r.status_code}"
        print(f"GAGAL - {err[:60]}")
        return None, err[:100]
    print("OK")

    uid = re.findall(r'"userId":\s*"([^"]+)"', r.text)

    print("  [6/8] Hapus auto keys...", end=" ", flush=True)
    try:
        r2 = s.get(f"{BASE}/api/keys", headers={"Accept": "application/json"},
                    proxies=proxy, timeout=15)
        for k in r2.json().get("keys", []):
            try:
                s.delete(f"{BASE}/api/keys/{k['id']}", proxies=proxy, timeout=10)
            except:
                pass
    except:
        pass
    print("OK")

    print("  [7/8] Accept free consent...", end=" ", flush=True)
    try:
        login_body, login_headers = make_login_body(email, pwd)
        s.post(f"{BASE}/login", data=login_body, headers=login_headers, proxies=proxy, timeout=25)
        rc = s.post(f"{BASE}/api/me/privacy",
            json={"free_models_enabled": True},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            proxies=proxy, timeout=10)
        if rc.status_code == 200 and rc.json().get("free_models_enabled"):
            print("OK")
        else:
            print(f"WARN {rc.status_code}")
    except:
        print("SKIP")

    print("  [8/8] Buat API key...", end=" ", flush=True)
    r3 = s.post(f"{BASE}/api/keys", json={"label": f"botbor-{random.randint(100, 999)}"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                proxies=proxy, timeout=15)

    if r3.status_code != 201:
        print(f"GAGAL - HTTP {r3.status_code}")
        return None, f"key create failed {r3.status_code}"

    key = r3.json().get("plaintext")
    if not key:
        print("GAGAL - no plaintext")
        return None, "no plaintext"
    print("OK")

    verify_email_bg(email, mail_token, provider)

    return {
        "email": email, "password": pwd,
        "userId": uid[0] if uid else "",
        "api_key": key, "email_token": mail_token,
        "provider": provider, "verified": True,
    }, None


# ==================== RE-VERIFY OLD KEY ====================

def reverify_key(account):
    """Re-trigger email verification for an existing unverified key"""
    email = account.get("email", "")
    mail_token = account.get("email_token", "")
    provider = account.get("provider", "")
    key = account.get("api_key", "")

    if not all([email, mail_token, provider, key]):
        return False

    print(f"  Re-verifying: {email}...", end=" ", flush=True)
    result = verify_email(email, mail_token, provider, max_wait=90)
    if result:
        print("OK")
        verified = wait_for_verification(key, max_wait=60)
        return verified
    print("FAILED (no verify link)")
    return False


# ==================== TEST ====================

def test_key(key):
    try:
        r = requests.get(f"{BASE}/v1/models",
            headers={"Authorization": f"Bearer {key}"}, timeout=15)
        if r.status_code == 200:
            models = r.json().get("data", [])
            free = [m.get("id", "") for m in models if "free" in m.get("id", "")]
            return True, f"{len(models)} models, free: {', '.join(free) if free else 'none'}"
        elif r.status_code == 403:
            err = r.json().get("error", {}).get("message", "")[:60]
            if "Verify your email" in err:
                return False, "email not verified"
            return False, f"403: {err}"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_key_models(key, models=None):
    """Test key against free models. Returns dict of model->status."""
    if models is None:
        models = FREE_MODELS
    results = {}
    for model in models:
        try:
            r = requests.post(f"{BASE}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 5}, timeout=20)
            if r.status_code == 200:
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                results[model] = f"OK -> {content[:30]}"
            else:
                err = r.json().get("error", {}).get("message", "")[:40]
                results[model] = f"FAIL: {err}"
        except Exception as e:
            results[model] = f"ERR: {str(e)[:30]}"
    return results


def pick_valid_key(verbose=True):
    """Ambil key pertama yang valid (verified). Return (key, info) atau (None, None)."""
    keys = load_keys()
    for k in keys:
        valid, info = test_key(k)
        if valid:
            if verbose:
                print(f"  Using key: {k[:35]}... -> {info}")
            return k, info
        elif verbose:
            print(f"  Skip {k[:30]}... -> {info}")
    return None, None


def scan_all_models(key):
    """Scan all available models on the platform"""
    results = {}
    for model in ALL_MODELS:
        try:
            r = requests.post(f"{BASE}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 5}, timeout=20)
            if r.status_code == 200:
                results[model] = "FREE"
            elif r.status_code == 402 or "insufficient" in r.text.lower() or "credit" in r.text.lower():
                results[model] = "PAID (need deposit)"
            else:
                err = r.json().get("error", {}).get("message", "")[:40] if "json" in r.headers.get("content-type", "") else r.text[:40]
                results[model] = f"ERR: {r.status_code}"
        except Exception as e:
            results[model] = f"ERR: {str(e)[:30]}"
    return results


# ==================== BATCH ====================

def run_batch(n):
    success = 0
    for i in range(n):
        print(f"\n  === Akun {i+1}/{n} ===")
        for attempt in range(5):
            if attempt > 0:
                print(f"  Retry {attempt+1}/5...")
                time.sleep(random.randint(5, 10))
            try:
                account, err = register_one()
                if account:
                    accounts = load_accounts()
                    accounts.append(account)
                    save_accounts(accounts)
                    save_key(account["api_key"])
                    success += 1
                    print(f"\n  >> SUKSES: {account['email']}")
                    print(f"     Key: {account['api_key'][:40]}...")
                    print(f"     Waiting for verification...")
                    verified = wait_for_verification(account["api_key"])
                    if verified:
                        print(f"     Verified! Testing free models...")
                        models = test_key_models(account["api_key"])
                        for m, s in models.items():
                            print(f"       {m}: {s}")
                    else:
                        print(f"     WARNING: not verified after 2 min")
                    break
                else:
                    print(f"  Gagal: {err[:40]}")
            except Exception as e:
                print(f"  Error: {str(e)[:40]}")
        if i < n - 1:
            wait = random.randint(15, 30)
            print(f"  Tunggu {wait}s...")
            time.sleep(wait)
    print(f"\n  === Selesai: {success}/{n} akun berhasil ===")
    return success


# ==================== EXPORT ====================

def export_keys():
    """Export all keys to JSON for 9Router injection"""
    accounts = load_accounts()
    keys = load_keys()
    export = []
    for a in accounts:
        export.append({
            "email": a.get("email", ""),
            "api_key": a.get("api_key", ""),
            "models": FREE_MODELS,
        })
    # Add any extra keys from apikeys.txt not in accounts
    account_keys = {a.get("api_key") for a in accounts}
    for k in keys:
        if k not in account_keys:
            export.append({"email": "", "api_key": k, "models": FREE_MODELS})

    out = os.path.join(DIR, "export.json")
    with open(out, "w") as f:
        json.dump(export, f, indent=2)
    print(f"  Exported {len(export)} keys to {out}")
    return export


# ==================== MENU ====================

def show_menu():
    print("""
botbor v3.1 - TokenHarbor Auto-Register
----------------------------------------
Free: mimo-v2.5:free | deepseek-v4-flash:free | deepseek-v4.1-flash:free
[1] Buat 1 akun
[2] Buat batch (N akun)
[3] Test semua API key
[4] List akun & key
[5] Test 1 key (input)
[6] Scan all models (free vs paid)
[7] Re-verify unverified accounts
[8] Export keys (JSON)
[9] Refresh models list (scrape from API)
[0] Exit
""")


# ==================== MAIN ====================

if __name__ == "__main__":
    # CLI mode
    if len(sys.argv) > 1:
        if "--proxy" in sys.argv:
            _use_proxy = True
            n = _load_proxies()
            print(f"  Loaded {n} proxies")
        elif "--direct" in sys.argv:
            _use_proxy = False

        cmd = sys.argv[1]

        if cmd == "1":
            a, err = register_one()
            if a:
                accounts = load_accounts()
                accounts.append(a)
                save_accounts(accounts)
                save_key(a["api_key"])
                print(f"\n  SUKSES: {a['email']}")
                print(f"  Key: {a['api_key'][:40]}...")
                print(f"\n  Waiting for email verification...")
                verified = wait_for_verification(a["api_key"])
                if verified:
                    print("  Verified! Testing free models...")
                    models = test_key_models(a["api_key"])
                    for m, s in models.items():
                        print(f"    {m}: {s}")
                else:
                    print("  WARNING: email not verified after 2 min")
            else:
                print(f"\n  GAGAL: {err}")

        elif cmd == "batch":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            print(f"Batch {n} akun...")
            ok = run_batch(n)
            print(f"\n  Done: {ok}/{n}")

        elif cmd == "test":
            keys = load_keys()
            print(f"Testing {len(keys)} keys...")
            ok = 0
            for k in keys:
                valid, info = test_key(k)
                mark = "OK" if valid else "FAIL"
                print(f"  [{mark}] {k[:35]}... -> {info}")
                if valid:
                    ok += 1
                    models = test_key_models(k)
                    for m, s in models.items():
                        print(f"       {m}: {s}")
            print(f"\n  {ok}/{len(keys)} valid")

        elif cmd == "list":
            accts = load_accounts()
            keys = load_keys()
            print(f"\nAccounts: {len(accts)} | Keys: {len(keys)}")
            for i, a in enumerate(accts):
                v = "V" if a.get("verified") else "?"
                print(f"  [{v}] {a['email']} | {a.get('api_key','?')[:35]}...")

        elif cmd == "scan":
            keys = load_keys()
            if keys:
                print(f"Scanning all models with key: {keys[0][:30]}...")
                results = scan_all_models(keys[0])
                free = [m for m, s in results.items() if s == "FREE"]
                paid = [m for m, s in results.items() if "PAID" in s]
                print(f"\n  FREE ({len(free)}): {', '.join(free)}")
                print(f"  PAID ({len(paid)}): {', '.join(paid)}")

        elif cmd == "export":
            export_keys()

        elif cmd == "reverify":
            accounts = load_accounts()
            keys = load_keys()
            # Match accounts to keys
            for a in accounts:
                if a.get("api_key") in keys:
                    valid, info = test_key(a["api_key"])
                    if not valid and "email not verified" in info:
                        reverify_key(a)

        else:
            print(f"Usage: {sys.argv[0]} [1|batch N|test|list|scan|export|reverify]")

    else:
        # Interactive menu
        proxy_choice = input("  Use proxy? (y/n): ").strip().lower()
        if proxy_choice == "y":
            _use_proxy = True
            n = _load_proxies()
            print(f"  Loaded {n} proxies")
        else:
            _use_proxy = False
            print("  Running direct mode")

        while True:
            show_menu()
            choice = input("Pilih: ").strip()

            if choice == "1":
                a, err = register_one()
                if a:
                    accounts = load_accounts()
                    accounts.append(a)
                    save_accounts(accounts)
                    save_key(a["api_key"])
                    print(f"\n  SUKSES: {a['email']}")
                    print(f"  Key: {a['api_key'][:40]}...")
                    print(f"\n  Waiting for email verification...")
                    verified = wait_for_verification(a["api_key"])
                    if verified:
                        print("  Verified! Testing free models...")
                        models = test_key_models(a["api_key"])
                        for m, s in models.items():
                            print(f"    {m}: {s}")
                    else:
                        print("  WARNING: email not verified after 2 min")
                else:
                    print(f"\n  GAGAL: {err}")

            elif choice == "2":
                n = input("Jumlah: ").strip()
                if n.isdigit() and int(n) > 0:
                    print(f"\nBatch {int(n)} akun...")
                    ok = run_batch(int(n))
                    print(f"\n  Done: {ok}/{int(n)}")
                else:
                    print("  Invalid")

            elif choice == "3":
                keys = load_keys()
                print(f"Testing {len(keys)} keys...")
                ok = 0
                for k in keys:
                    valid, info = test_key(k)
                    mark = "OK" if valid else "FAIL"
                    print(f"  [{mark}] {k[:35]}... -> {info}")
                    if valid:
                        ok += 1
                        models = test_key_models(k)
                        for m, s in models.items():
                            print(f"       {m}: {s}")
                print(f"\n  {ok}/{len(keys)} valid")

            elif choice == "4":
                accts = load_accounts()
                keys = load_keys()
                print(f"\nAccounts: {len(accts)} | Keys: {len(keys)}")
                for i, a in enumerate(accts):
                    v = "V" if a.get("verified") else "?"
                    print(f"  [{v}] {a['email']} | {a.get('api_key','?')[:35]}...")

            elif choice == "5":
                key = input("Key: ").strip()
                if key:
                    valid, info = test_key(key)
                    mark = "OK" if valid else "FAIL"
                    print(f"  [{mark}] {info}")
                    if valid:
                        models = test_key_models(key)
                        for m, s in models.items():
                            print(f"  {m}: {s}")

            elif choice == "6":
                keys = load_keys()
                if keys:
                    print(f"Scanning all models with key: {keys[0][:30]}...")
                    results = scan_all_models(keys[0])
                    free = [m for m, s in results.items() if s == "FREE"]
                    paid = [m for m, s in results.items() if "PAID" in s]
                    err = [m for m, s in results.items() if s.startswith("ERR")]
                    print(f"\n  FREE ({len(free)}):")
                    for m in free:
                        print(f"    + {m}")
                    print(f"\n  PAID ({len(paid)}):")
                    for m in paid:
                        print(f"    $ {m}")
                    if err:
                        print(f"\n  ERRORS ({len(err)}):")
                        for m in err:
                            print(f"    ! {m}: {results[m]}")
                else:
                    print("  No keys found")

            elif choice == "7":
                accounts = load_accounts()
                keys = load_keys()
                unverified = []
                for a in accounts:
                    if a.get("api_key") in keys:
                        valid, info = test_key(a["api_key"])
                        if not valid and "email not verified" in info:
                            unverified.append(a)
                if unverified:
                    print(f"  {len(unverified)} unverified accounts found")
                    for a in unverified:
                        reverify_key(a)
                else:
                    print("  All accounts verified or no keys available")

            elif choice == "8":
                export_keys()

            elif choice == "9":
                keys = load_keys()
                if keys:
                    valid, info = test_key(keys[0])
                    if valid:
                        r = requests.get(f"{BASE}/v1/models",
                            headers={"Authorization": f"Bearer {keys[0]}"}, timeout=15)
                        if r.status_code == 200:
                            models = [m["id"] for m in r.json().get("data", [])]
                            print(f"  {len(models)} models available:")
                            for m in sorted(models):
                                tag = " [FREE]" if "free" in m else ""
                                print(f"    {m}{tag}")
                            print(f"\n  Copy FREE_MODELS list from above to update config")
                    else:
                        print("  Key not valid, cannot fetch models")
                else:
                    print("  No keys found")

            elif choice == "0":
                print("Bye!")
                break

            else:
                print("Invalid")
