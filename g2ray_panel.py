#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G2Ray Reality Panel – VLESS + XTLS + Reality
شبیه‌سازی ترافیک آپارات و سایت‌های ایرانی – اجرا روی گیت‌هاب
"""

import subprocess, json, sys, os, time, argparse, random, re, tempfile, urllib.request
from pathlib import Path
from typing import Tuple, Optional, Dict, List

# ════════════ تنظیمات ════════════
LOCAL_PORT = 10000                           # پورت غیرممتاز
XRAY_DIR = Path("./xray")
XRAY_BIN = XRAY_DIR / "xray"
CONFIG_PATH = Path("/tmp/g2ray.json")
BORE_BIN = Path("/usr/local/bin/bore")
BORE_URL = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"

# سایت‌های ایرانی با HTTP/2
IR_SITES = [
    {"dest": "www.aparat.com:443", "sni": ["www.aparat.com", "aparat.com"]},
    {"dest": "www.digikala.com:443", "sni": ["www.digikala.com", "digikala.com"]},
    {"dest": "www.ninisite.com:443", "sni": ["www.ninisite.com", "ninisite.com"]},
    {"dest": "www.namnak.com:443", "sni": ["www.namnak.com", "namnak.com"]},
    {"dest": "www.varzesh3.com:443", "sni": ["www.varzesh3.com", "varzesh3.com"]},
    {"dest": "www.beytoote.com:443", "sni": ["www.beytoote.com", "beytoote.com"]},
    {"dest": "www.torob.com:443", "sni": ["www.torob.com", "torob.com"]},
    {"dest": "www.filimo.com:443", "sni": ["www.filimo.com", "filimo.com"]},
    {"dest": "www.sheypoor.com:443", "sni": ["www.sheypoor.com", "sheypoor.com"]},
    {"dest": "yooz.ir:443", "sni": ["yooz.ir", "yooz.ir"]},
    {"dest": "www.isna.ir:443", "sni": ["www.isna.ir", "isna.ir"]},
    {"dest": "www.iribnews.ir:443", "sni": ["www.iribnews.ir", "iribnews.ir"]},
]

# ════════════ ابزارهای لاگ ════════════
class C:
    HEADER = '\033[95m'; BLUE = '\033[94m'; GREEN = '\033[92m'
    WARNING = '\033[93m'; FAIL = '\033[91m'; END = '\033[0m'; BOLD = '\033[1m'

def log(msg, level="info"):
    p = {"info": f"{C.BLUE}[>]{C.END}",
         "success": f"{C.GREEN}[✓]{C.END}",
         "error": f"{C.FAIL}[✗]{C.END}"}
    print(f"{p.get(level,'')} {msg}")

def banner():
    print(f"{C.BOLD}╔══════════════════════════════╗\n║   G2Ray Reality Panel v2  ║\n╚══════════════════════════════╝{C.END}")

# ════════════ توابع کمکی ════════════
def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def download(url, dest):
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        log(f"دانلود خطا: {e}", "error")
        return False

# ════════════ نصب Xray ════════════
def install_xray():
    log("دریافت Xray-core...")
    code, out, _ = run("curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep 'browser_download_url.*linux-64.zip' | grep -v dgst | cut -d : -f 2,3 | tr -d '\"'")
    if code != 0 or not out:
        log("خطا در دریافت لینک Xray", "error"); return False
    url = out.splitlines()[0].strip()
    XRAY_DIR.mkdir(exist_ok=True)
    zip_path = XRAY_DIR / "xray.zip"
    if not download(url, zip_path): return False
    code, _, err = run(f"unzip -o {zip_path} -d {XRAY_DIR}")
    if code != 0:
        log(f"خطای unzip: {err}", "error"); return False
    (XRAY_DIR/"xray").chmod(0o755)
    log("Xray نصب شد", "success")
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

# ════════════ تونل Bore ════════════
def start_bore(port):
    if not BORE_BIN.exists():
        code, _, _ = run(f"curl -sL '{BORE_URL}' | tar xz -C /tmp && sudo mv /tmp/bore {BORE_BIN}")
        if code: return None
    proc = subprocess.Popen(f"{BORE_BIN} local {port} --to bore.pub", shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(5)
    out = proc.stdout.read(256).decode(errors='ignore')
    m = re.search(r"listening on (\S+:\d+)", out)
    return m.group(1) if m else None

# ════════════ تونل SSH (پشتیبان) ════════════
def start_ssh_tunnel(port):
    cmd = f"ssh -o StrictHostKeyChecking=no -R 80:localhost:{port} nokey@localhost.run"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(10)
    out = proc.stdout.read(512).decode(errors='ignore')
    m = re.search(r"https?://(\S+)", out)
    return m.group(1).replace("https://","").replace("http://","") if m else None

# ════════════ ایجاد لینک VLESS ════════════
def make_link(uuid, pub, host_port, sni):
    # host_port مثل bore.pub:12345
    return f"vless://{uuid}@{host_port}?encryption=none&security=reality&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={pub}#G2Ray-Iran"

# ════════════ برنامه اصلی ════════════
def main():
    banner()
    parser = argparse.ArgumentParser()
    parser.add_argument("--sni", help="SNI (پیش‌فرض: آپارات)")
    parser.add_argument("--backup", action="store_true", help="استفاده از سایت تصادفی ایرانی")
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
        log("تولید هویت ناموفق", "error"); sys.exit(1)

    cfg = build_config(uid, priv, LOCAL_PORT, dest, sni)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    log("پیکربندی Reality ساخته شد", "success")

    # اجرای Xray با بررسی خطا
    log("اجرای Xray...")
    proc = subprocess.Popen([str(XRAY_BIN), "run", "-config", str(CONFIG_PATH)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2)
    if proc.poll() is not None:
        _, err = proc.communicate()
        log(f"Xray اجرا نشد: {err.strip()}", "error")
        # با این وجود لینک را نمایش می‌دهیم ولی بدون تونل نمی‌توان استفاده کرد
        link = make_link(uid, pub, "TUNNEL_NOT_READY", sni[0])
        print(f"\n⚠️  تونل در دسترس نیست، اما مشخصات کانفیگ:\n{link}\n")
        sys.exit(1)

    log("ایجاد تونل...")
    tunnel = start_bore(LOCAL_PORT)
    if not tunnel:
        tunnel = start_ssh_tunnel(LOCAL_PORT)
    if not tunnel:
        log("تونل برقرار نشد!", "error")
    else:
        log(f"تونل فعال: {tunnel}", "success")

    # نمایش نهایی
    host_port = tunnel if tunnel else "NEED_TUNNEL"
    link = make_link(uid, pub, host_port, sni[0])
    print(f"""
{C.BOLD}═══════════════════════════════════════
 ✅ کانفیگ آماده
────────────────────────────────────
 {C.GREEN}UUID:{C.END}       {uid}
 {C.GREEN}Public Key:{C.END} {pub}
 {C.GREEN}SNI:{C.END}        {sni[0]}
 {C.GREEN}Endpoint:{C.END}   {host_port}
────────────────────────────────────
 {C.BOLD}لینک اتصال:{C.END}
 {link}
═══════════════════════════════════════
""")
    # زنده نگه‌داشتن
    try:
        while proc.poll() is None:
            time.sleep(60)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
