#!/usr/bin/env python3
"""
G2Ray Reality Panel – Stable Anti‑Censorship on GitHub
نسخه بدون هنگ – با تونل‌های غیرهمگام و fallback خودکار
"""

import subprocess, json, sys, os, time, argparse, random, re, tempfile, shutil
from pathlib import Path
from typing import Tuple, Optional, Dict, List

# ════════════ تنظیمات ════════════
LOCAL_PORT = 10000
XRAY_DIR = Path("./xray")
XRAY_BIN = XRAY_DIR / "xray"
CONFIG_PATH = Path("/tmp/g2ray.json")
BORE_BIN = Path("/usr/local/bin/bore")
BORE_URL = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"

IR_SITES = [
    {"dest": "www.aparat.com:443", "sni": ["www.aparat.com", "aparat.com"]},
    {"dest": "www.digikala.com:443", "sni": ["www.digikala.com", "digikala.com"]},
    {"dest": "www.varzesh3.com:443", "sni": ["www.varzesh3.com", "varzesh3.com"]},
    {"dest": "www.ninisite.com:443", "sni": ["www.ninisite.com", "ninisite.com"]},
    {"dest": "www.namnak.com:443", "sni": ["www.namnak.com", "namnak.com"]},
    {"dest": "www.beytoote.com:443", "sni": ["www.beytoote.com", "beytoote.com"]},
    {"dest": "www.torob.com:443", "sni": ["www.torob.com", "torob.com"]},
    {"dest": "www.filimo.com:443", "sni": ["www.filimo.com", "filimo.com"]},
    {"dest": "yooz.ir:443", "sni": ["yooz.ir", "yooz.ir"]},
]

# ════════════ رنگ و لاگ ════════════
class C:
    H = '\033[95m'; B = '\033[94m'; G = '\033[92m'; Y = '\033[93m'
    R = '\033[91m'; E = '\033[0m'; BD = '\033[1m'

def log(msg, lvl="info"):
    p = {"info": f"{C.B}[>]{C.E}", "ok": f"{C.G}[✓]{C.E}", "err": f"{C.R}[✗]{C.E}"}
    print(f"{p.get(lvl,'')} {msg}")

def banner():
    print(f"{C.BD}╔══════════════════════════════╗\n║   G2Ray Reality Panel v3  ║\n╚══════════════════════════════╝{C.E}")

# ════════════ دستورات سیستمی ════════════
def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

# ════════════ نصب Xray ════════════
def install_xray():
    log("دریافت Xray-core...")
    code, out, _ = run("curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep 'browser_download_url.*linux-64.zip' | grep -v dgst | cut -d : -f 2,3 | tr -d '\"'")
    if code != 0 or not out:
        log("خطا در دریافت لینک Xray", "err"); return False
    url = out.splitlines()[0].strip()
    XRAY_DIR.mkdir(exist_ok=True)
    zip_path = XRAY_DIR / "xray.zip"
    try:
        import urllib.request; urllib.request.urlretrieve(url, zip_path)
    except Exception as e:
        log(f"دانلود Xray خطا: {e}", "err"); return False
    code, _, err = run(f"unzip -o {zip_path} -d {XRAY_DIR}")
    if code != 0:
        log(f"خطای unzip: {err}", "err"); return False
    (XRAY_DIR/"xray").chmod(0o755)
    log("Xray نصب شد", "ok")
    return True

# ════════════ تولید هویت ════════════
def gen_identity():
    code, uid, _ = run(f"{XRAY_BIN} uuid")
    if code: return None,None,None
    code, keys, _ = run(f"{XRAY_BIN} x25519")
    if code: return None,None,None
    priv = [l.split()[-1] for l in keys.splitlines() if "Private" in l][0]
    pub  = [l.split()[-1] for l in keys.splitlines() if "Public" in l][0]
    return uid.strip(), pub.strip(), priv.strip()

# ════════════ ساخت کانفیگ ════════════
def build_config(uuid, priv, port, dest, sni):
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "listen": "0.0.0.0",
            "port": port,
            "protocol": "vless",
            "settings": {
                "clients": [{"id": uuid, "flow": "xtls-rprx-vision"}],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "show": False,
                    "dest": dest,
                    "serverNames": sni,
                    "privateKey": priv,
                    "shortIds": [""]
                }
            }
        }],
        "outbounds": [{"protocol": "freedom"}]
    }

# ════════════ تونل Bore (با تایم‌اوت واقعی) ════════════
def start_bore(port, timeout=15):
    log("تلاش برای تونل Bore...")
    if not BORE_BIN.exists():
        code, _, _ = run(f"curl -sL '{BORE_URL}' | tar xz -C /tmp && sudo mv /tmp/bore {BORE_BIN}")
        if code != 0: return None
    log_file = "/tmp/bore_out.txt"
    cmd = f"{BORE_BIN} local {port} --to bore.pub > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True)
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
            with open(log_file, "r") as f:
                content = f.read()
            m = re.search(r"listening on (\S+:\d+)", content)
            if m:
                return m.group(1)
        time.sleep(1)
    proc.kill()
    return None

# ════════════ تونل SSH (localhost.run) ════════════
def start_ssh(port, timeout=20):
    log("تلاش برای تونل SSH (localhost.run)...")
    log_file = "/tmp/ssh_out.txt"
    cmd = f"ssh -o StrictHostKeyChecking=no -R 80:localhost:{port} nokey@localhost.run > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True)
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                content = f.read()
            m = re.search(r"https?://(\S+)", content)
            if m:
                url = m.group(1)
                # حذف پروتکل و اسلش‌های اضافی
                host = url.replace("https://","").replace("http://","").rstrip("/")
                return host
        time.sleep(1)
    proc.kill()
    return None

# ════════════ لینک VLESS ════════════
def make_link(uuid, pub, host_port, sni):
    return f"vless://{uuid}@{host_port}?encryption=none&security=reality&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={pub}#G2Ray-Iran"

# ════════════ بدنه اصلی ════════════
def main():
    banner()
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", action="store_true", help="استفاده از سایت تصادفی ایرانی")
    parser.add_argument("--sni", help="SNI دستی (اختیاری)")
    args = parser.parse_args()

    if args.backup:
        site = random.choice(IR_SITES)
        dest, sni = site["dest"], site["sni"]
    else:
        dest = "www.aparat.com:443"
        sni = args.sni.split(",") if args.sni else ["www.aparat.com", "aparat.com"]

    if not install_xray():
        sys.exit(1)

    uid, pub, priv = gen_identity()
    if not uid:
        log("خطای تولید هویت", "err"); sys.exit(1)

    cfg = build_config(uid, priv, LOCAL_PORT, dest, sni)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    log("پیکربندی Reality ساخته شد", "ok")

    # اجرای Xray
    xray_proc = subprocess.Popen(
        [str(XRAY_BIN), "run", "-config", str(CONFIG_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    if xray_proc.poll() is not None:
        log("Xray اجرا نشد", "err"); sys.exit(1)
    log("سرویس Xray فعال", "ok")

    # تلاش برای تونل
    tunnel = None
    for method in [start_bore, start_ssh]:
        tunnel = method(LOCAL_PORT)
        if tunnel:
            break

    if not tunnel:
        log("هیچ تونلی برقرار نشد! شاید سرورهای رایگان در دسترس نباشند.", "err")
        host_port = "YOUR_TUNNEL_ADDRESS:PORT"
    else:
        host_port = tunnel
        log(f"تونل: {tunnel}", "ok")

    # نمایش نهایی
    link = make_link(uid, pub, host_port, sni[0])
    print(f"""
{C.BD}═══════════════════════════════════════
 ✅ کانفیگ آماده
────────────────────────────────────
 {C.G}UUID:{C.E}       {uid}
 {C.G}Public Key:{C.E} {pub}
 {C.G}SNI:{C.E}        {sni[0]}
 {C.G}Endpoint:{C.E}   {host_port}
────────────────────────────────────
 {C.BD}لینک اتصال:{C.E}
 {link}

 ⚠️  اگر Endpoint مقدار YOUR_TUNNEL_ADDRESS:PORT بود،
 باید Workflow را دوباره اجرا کنید یا از VPN برای دسترسی به تونل استفاده کنید.
═══════════════════════════════════════
""")
    # زنده نگهداشتن سرور
    try:
        while xray_proc.poll() is None:
            time.sleep(30)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
