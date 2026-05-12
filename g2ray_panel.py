#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║   G2Ray Ultimate Panel  |  VLESS + XTLS + Reality                 ║
║   شبیه‌سازی ترافیک آپارات برای عبور از فیلترینگ ملی ایران          ║
║   تماماً رایگان روی سرورهای GitHub Actions                         ║
║   توسعه‌یافته توسط جامعه برای عبور امن و پایدار                     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import subprocess, json, sys, os, time, argparse, signal
import uuid as uuid_mod, hashlib, random, socket, platform
import re, tempfile, urllib.request, shutil, threading
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from datetime import datetime

# ════════════════ تنظیمات عمومی ════════════════
DEFAULT_PORT = 443
XRAY_VERSION = "latest"
XRAY_INSTALL_DIR = Path("./xray")
XRAY_BIN = XRAY_INSTALL_DIR / "xray"
CONFIG_PATH = Path("/tmp/g2ray_config.json")
BORE_BIN = Path("/usr/local/bin/bore")
BORE_URL = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"

# لیست سایت‌های ایرانی پرمصرف با پشتیبانی HTTP/2 (پشتیبان‌های هوشمند)
IRANIAN_SITES = [
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

# ════════════ کلاس مدیریت رنگ‌ها و لاگ ════════════
class Colors:
    HEADER = '\033[95m'; BLUE = '\033[94m'; CYAN = '\033[96m'
    GREEN = '\033[92m'; WARNING = '\033[93m'; FAIL = '\033[91m'
    END = '\033[0m'; BOLD = '\033[1m'; UNDERLINE = '\033[4m'

def log(msg: str, level: str = "info"):
    prefix = {"info": f"{Colors.BLUE}[>]{Colors.END}",
              "success": f"{Colors.GREEN}[✓]{Colors.END}",
              "warning": f"{Colors.WARNING}[!]{Colors.END}",
              "error": f"{Colors.FAIL}[✗]{Colors.END}"}
    print(f"{prefix.get(level, '')} {msg}")

def banner():
    print(f"""{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════╗
║         G2RAY REALITY PANEL             ║
║      عبور امن از فیلترینگ ایران          ║
╚══════════════════════════════════════════╝{Colors.END}""")

# ════════════ ابزارهای سیستمی ════════════
def run_cmd(cmd: str, timeout: int = 30, shell: bool = True) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def download_file(url: str, dest: Path):
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        log(f"دانلود ناموفق: {e}", "error")
        return False

# ════════════ نصب Xray-Core ════════════
def install_xray() -> bool:
    log("دریافت آخرین نسخه Xray-Core...", "info")
    try:
        # دریافت دقیق آدرس فایل zip (بدون dgst)
        code, out, err = run_cmd(
            "curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | "
            "grep 'browser_download_url.*linux-64.zip' | grep -v 'dgst' | "
            "cut -d : -f 2,3 | tr -d '\"' | tr -d ' '"
        )
        if code != 0 or not out:
            log("خطا در دریافت لینک Xray", "error"); return False

        url = out.splitlines()[0]  # فقط خط اول (حذف فضای خالی)
        log(f"لینک: {url}", "info")

        XRAY_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = XRAY_INSTALL_DIR / "xray.zip"
        if not download_file(url, zip_path):
            return False

        # استخراج و نصب
        code, _, err = run_cmd(f"unzip -o {zip_path} -d {XRAY_INSTALL_DIR}")
        if code != 0:
            log(f"خطا در استخراج: {err}", "error"); return False

        binary = XRAY_INSTALL_DIR / "xray"
        binary.chmod(0o755)
        log("Xray-Core با موفقیت نصب شد", "success")
        return True
    except Exception as e:
        log(f"خطای بحرانی: {e}", "error"); return False

# ════════════ تولید هویت Reality ════════════
def generate_identity() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        code, uuid_out, _ = run_cmd(f"{XRAY_BIN} uuid")
        if code != 0: raise RuntimeError("UUID failed")
        code, keys_out, _ = run_cmd(f"{XRAY_BIN} x25519")
        if code != 0: raise RuntimeError("Key failed")

        priv = [l.split()[-1] for l in keys_out.splitlines() if "Private" in l][0]
        pub  = [l.split()[-1] for l in keys_out.splitlines() if "Public" in l][0]
        return uuid_out.strip(), pub.strip(), priv.strip()
    except Exception as e:
        log(f"خطای تولید هویت: {e}", "error")
        return None, None, None

# ════════════ ساخت پیکربندی ════════════
def build_config(uuid: str, priv: str, port: int, dest: str, sni: List[str]) -> Dict:
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "reality-in",
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
                    "xver": 0,
                    "serverNames": sni,
                    "privateKey": priv,
                    "shortIds": [""],
                    "minClientVer": "1.8.0"
                }
            }
        }],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"}
        ]
    }

# ════════════ تونل‌ها (Bore و لوکال‌هاست ران) ════════════
def start_bore(local_port: int) -> Optional[str]:
    log("راه‌اندازی تونل Bore...", "info")
    if not BORE_BIN.exists():
        code, _, _ = run_cmd(f"curl -sL '{BORE_URL}' | tar xz -C /tmp && sudo mv /tmp/bore {BORE_BIN}")
        if code != 0: return None
    proc = subprocess.Popen(f"{BORE_BIN} local {local_port} --to bore.pub",
                            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(5)
    out = proc.stdout.read().decode() if proc.stdout else ""
    m = re.search(r"listening on\s+(\S+)", out)
    if m:
        return m.group(1).strip()
    return None

def start_ssh_tunnel(local_port: int) -> Optional[str]:
    log("فعال‌سازی تونل پشتیبان SSH (localhost.run)...", "info")
    cmd = f"ssh -o StrictHostKeyChecking=no -R 80:localhost:{local_port} nokey@localhost.run"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(10)
    out = proc.stdout.read().decode() if proc.stdout else ""
    m = re.search(r"https?://([^\s]+)", out)
    if m:
        return m.group(1).replace("https://", "").replace("http://", "")
    return None

def establish_tunnel(port: int) -> Optional[str]:
    tunnel = start_bore(port)
    if not tunnel:
        tunnel = start_ssh_tunnel(port)
    return tunnel

# ════════════ ساخت لینک اتصال ════════════
def make_vless_link(uuid: str, pub_key: str, host: str, port: int, sni: str, name: str = "G2Ray-Iran"):
    return (f"vless://{uuid}@{host}:{port}?encryption=none&security=reality"
            f"&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={pub_key}#{name}")

# ════════════ روال اصلی ════════════
def main():
    banner()
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--backup", action="store_true", help="استفاده از سایت پشتیبان تصادفی")
    parser.add_argument("--sni", help="نام SNI (پیش‌فرض آپارات)")
    args = parser.parse_args()

    # انتخاب سایت هدف
    if args.backup:
        site = random.choice(IRANIAN_SITES)
        dest, sni = site["dest"], site["sni"]
    else:
        dest = "www.aparat.com:443"
        sni = args.sni.split(",") if args.sni else ["www.aparat.com", "aparat.com"]

    # ۱. نصب Xray
    if not install_xray():
        sys.exit(1)

    # ۲. تولید هویت
    uid, pub, priv = generate_identity()
    if not uid:
        sys.exit(1)

    # ۳. ساخت پیکربندی
    config = build_config(uid, priv, args.port, dest, sni)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    log("پیکربندی ساخته شد", "success")

    # ۴. اجرای Xray
    proc = subprocess.Popen([str(XRAY_BIN), "run", "-config", str(CONFIG_PATH)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    if proc.poll() is not None:
        log("Xray اجرا نشد", "error")
        sys.exit(1)
    log("سرویس Xray فعال شد", "success")

    # ۵. تونل
    tunnel = establish_tunnel(args.port)
    if not tunnel:
        log("ایجاد تونل ناموفق - اتصال برقرار نشد", "error")
        sys.exit(1)

    # ۶. چاپ اطلاعات اتصال
    link = make_vless_link(uid, pub, tunnel, args.port, sni[0])
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║     اتصال آماده است!                                        ║
╠═══════════════════════════════════════════════════════════════╣
║ Host: {tunnel:<52}║
║ Port: {args.port:<52}║
║ UUID: {uid:<52}║
║ Public Key: {pub:<48}║
║ SNI : {sni[0]:<52}║
╠═══════════════════════════════════════════════════════════════╣
║ لینک کامل:                                                 ║
║ {link:<60}║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
""")

    # ۷. ماندگاری سرور
    try:
        while proc.poll() is None:
            time.sleep(60)
    except KeyboardInterrupt:
        log("پایان اجرا", "info")

if __name__ == "__main__":
    main()
