#!/usr/bin/env python3
"""
G2Ray Auto-Panel: VLESS Reality Config Generator
نسل جدید پروژه g2ray برای عبور از فیلترینگ با شبیه‌سازی ترافیک آپارات

نحوه اجرا: python3 g2ray_panel.py [--tunnel bore]
"""

import subprocess
import json
import sys
import os
import time
import argparse
import signal
import uuid
import hashlib
import random
import socket
import platform
import re
import tempfile
from typing import Tuple, Optional
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# 0. GLOBALS, DEFAULTS & CONSTANTS
# ══════════════════════════════════════════════════════════════

# --- پیش‌فرض‌های امنیتی پیشنهادی برای ایران ---
DEFAULT_PORT = 443
DEFAULT_DEST = "www.aparat.com:443"           # هدف اصلی شبیه‌سازی
DEFAULT_SERVER_NAMES = ["www.aparat.com", "aparat.com"] # SNI لیست

# وب‌سایت‌های پرطرفدار ایرانی که از HTTP/2 پشتیبانی می‌کنند (بکاپ‌های هوشمند)
backup_iranian_sites = [
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

# --- مسیرهای پیش‌فرض در محیط گیت‌هاب ---
XRAY_BIN = "./xray/xray"
TEMP_DIR = "/tmp/g2ray"

# پارامترهای تونل
BORE_BIN = "/usr/local/bin/bore"
BORE_REMOTE = "bore.pub"

class Colors:
    """رنگ‌های ترمینال برای نمایش بهتر اطلاعات."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# ══════════════════════════════════════════════════════════════
# 1. UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════

def print_banner() -> None:
    """نمایش بنر اصلی G2Ray."""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║        ██████╗ ██████╗ ██████╗  █████╗ ██╗   ██╗                 ║
║       ██╔════╝      ██║██╔══██╗██╔══██╗╚██╗ ██╔╝                 ║
║       ██║  ███╗ █████╔╝██████╔╝███████║ ╚████╔╝                  ║
║       ██║   ██║██╔══██╗██╔══██╗██╔══██║  ╚██╔╝                   ║
║       ╚██████╔╝██║  ██║██║  ██║██║  ██║   ██║                    ║
║        ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝                    ║
║                                                                   ║
║   VLESS + XTLS + REALITY - Anti-Censorship Panel                  ║
║   شبیه‌سازی ترافیک آپارات برای عبور از فیلترینگ                    ║
║   Powered by GitHub Actions - کاملاً رایگان و بدون تحریم           ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
{Colors.END}"""
    print(banner)


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}[✓] {msg}{Colors.END}")

def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}[>] {msg}{Colors.END}")

def log_warning(msg: str) -> None:
    print(f"{Colors.WARNING}[!] هشدار: {msg}{Colors.END}")

def log_error(msg: str) -> None:
    print(f"{Colors.FAIL}[✗] خطا: {msg}{Colors.END}", file=sys.stderr)

def log_critical(msg: str) -> int:
    """نمایش خطای بحرانی و خروج با کد 1."""
    print(f"{Colors.FAIL}[✗] بحرانی: {msg}{Colors.END}", file=sys.stderr)
    return 1

def run_command(cmd: str, shell: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
    """اجرای دستور سیستم با مدیریت خطا و Timeout."""
    try:
        proc = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


# ══════════════════════════════════════════════════════════════
# 2. CORE CONFIGURATION
# ══════════════════════════════════════════════════════════════

def download_xray_core(xray_path: str = XRAY_BIN) -> bool:
    """دانلود و نصب آخرین نسخه Xray-Core از مخزن رسمی XTLS."""
    log_info("در حال دانلود Xray-Core...")
    try:
        # دریافت لینک آخرین نسخه
        fetch_cmd = 'curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep "browser_download_url.*linux-64.zip" | cut -d : -f 2,3 | tr -d \\"'
        code, out, err = run_command(fetch_cmd, timeout=15)
        if code != 0 or not out.strip():
            return log_critical("خطا در دریافت لینک Xray-Core")

        download_url = out.strip()
        log_info(f"لینک دریافت شد: {download_url}")

        # آماده‌سازی دایرکتوری
        os.makedirs(os.path.dirname(xray_path), exist_ok=True)

        # دانلود و استخراج
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "xray.zip")
            code, _, _ = run_command(f"curl -sL '{download_url}' -o {zip_path}", timeout=60)
            if code != 0:
                return log_critical("خطا در دانلود فایل")

            code, _, _ = run_command(f"unzip -o {zip_path} -d {tmpdir}", timeout=15)
            if code != 0:
                return log_critical("خطا در استخراج فایل")

            # انتقال فایل اجرایی
            run_command(f"install -m 755 {tmpdir}/xray {xray_path}")

        # بررسی
        if os.path.isfile(xray_path) and os.access(xray_path, os.X_OK):
            log_success(f"Xray-Core با موفقیت نصب شد: {xray_path}")
            return True
        else:
            return log_critical("فایل Xray-Core یافت نشد یا دسترسی اجرایی ندارد")
    except Exception as e:
        return log_critical(f"خطای پیش‌بینی نشده: {e}")


def generate_reality_identity(xray_path: str = XRAY_BIN) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """تولید هویت امن Reality (UUID، کلید عمومی و خصوصی)."""
    try:
        # تولید UUID
        code, uid, err = run_command(f"{xray_path} uuid")
        if code != 0: raise RuntimeError(f"UUID خطا: {err}")

        # تولید کلیدها
        code, keys, err = run_command(f"{xray_path} x25519")
        if code != 0: raise RuntimeError(f"x25519 خطا: {err}")

        # استخراج
        priv = [line.split()[-1] for line in keys.splitlines() if "Private" in line][0]
        pub = [line.split()[-1] for line in keys.splitlines() if "Public" in line][0]
        return uid.strip(), pub.strip(), priv.strip()
    except Exception as e:
        log_error(f"خطا در تولید کلیدها: {e}")
        return None, None, None


def generate_reality_config(
    uuid: str, private_key: str,
    port: int = DEFAULT_PORT,
    dest: str = DEFAULT_DEST,
    server_names: list = DEFAULT_SERVER_NAMES,
    short_id: str = ""
) -> dict:
    """ساخت دیکشنری پیکربندی Reality Xray."""
    config = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": [
            {
                "tag": "reality-in",
                "listen": "0.0.0.0",
                "port": port,
                "protocol": "vless",
                "settings": {
                    "clients": [
                        {
                            "id": uuid,
                            "flow": "xtls-rprx-vision"
                        }
                    ],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": dest,
                        "xver": 0,
                        "serverNames": server_names,
                        "privateKey": private_key,
                        "shortIds": [short_id],
                        "minClientVer": "1.8.0",
                        "maxClientVer": "",
                        "maxTimeDiff": 60   # <-- FIXED: از 0 به 60 ثانیه تغییر کرد
                    }
                }
            }
        ],
        "outbounds": [
            {
                "tag": "direct",
                "protocol": "freedom",
                "settings": {}
            },
            {
                "tag": "block",
                "protocol": "blackhole",
                "settings": {}
            }
        ]
    }
    return config


def save_config(config: dict, path: str = "/tmp/g2ray_config.json") -> bool:
    """ذخیره فیزیکی فایل پیکربندی."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        log_success(f"پیکربندی در {path} ذخیره شد")
        return True
    except Exception as e:
        return log_critical(f"خطا در ذخیره پیکربندی: {e}")


# ══════════════════════════════════════════════════════════════
# 3. TUNNEL MANAGEMENT
# ══════════════════════════════════════════════════════════════

def start_bore_tunnel(local_port: int = DEFAULT_PORT) -> Optional[str]:
    """ایجاد تونل TCP با استفاده از Bore (کاملاً رایگان و بدون نیاز به توکن)."""
    log_info("راه‌اندازی تونل امن با Bore...")
    try:
        # نصب Bore
        bore_url = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"
        code, _, _ = run_command(f"curl -sL '{bore_url}' | tar xz -C /tmp && sudo mv /tmp/bore {BORE_BIN}", timeout=20)
        if code != 0 or not os.path.isfile(BORE_BIN):
            log_error("خطا در نصب Bore")
            return None

        # راه‌اندازی تونل
        log_info(f"باز کردن تونل روی پورت {local_port}...")
        cmd = f"{BORE_BIN} local {local_port} --to {BORE_REMOTE} > /tmp/bore.log 2>&1 &"
        code, _, _ = run_command(cmd)
        if code != 0:
            log_error("خطا در اجرای تونل")
            return None

        # انتظار با حلقه برای استخراج آدرس
        remote_addr = None
        for _ in range(30):   # حداکثر ۳۰ ثانیه صبر
            time.sleep(1)
            if os.path.isfile("/tmp/bore.log"):
                with open("/tmp/bore.log", "r") as f:
                    log_content = f.read()
                match = re.search(r'listening on\s+([^\s]+)', log_content)
                if match:
                    remote_addr = match.group(1)
                    break

        if remote_addr:
            log_success(f"تونل Bore فعال شد: {remote_addr}")
            return remote_addr

        log_error("خطا در استخراج آدرس تونل پس از ۳۰ ثانیه")
        return None
    except Exception as e:
        log_error(f"استثنا در تونل: {e}")
        return None


def start_ssh_tunnel(local_port: int = DEFAULT_PORT) -> Optional[str]:
    """ایجاد تونل SSH جایگزین (با localhost.run) در صورت عدم موفقیت Bore."""
    log_info("تلاش برای تونل پشتیبان SSH (localhost.run)...")
    try:
        cmd = f"ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:{local_port} nokey@localhost.run > /tmp/ssh_tunnel.log 2>&1 &"
        code, _, _ = run_command(cmd)
        if code != 0:
            return None

        # حلقه انتظار مشابه Bore
        for _ in range(20):
            time.sleep(1)
            if os.path.isfile("/tmp/ssh_tunnel.log"):
                with open("/tmp/ssh_tunnel.log", "r") as f:
                    content = f.read()
                match = re.search(r'(https?://[^\s]+)', content)
                if match:
                    url = match.group(1).replace('https://', '').replace('http://', '')
                    log_success(f"تونل SSH فعال شد: {url}")
                    return url
        return None
    except Exception as e:
        log_error(f"استثنا SSH: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# 4. CLIENT LINK GENERATION
# ══════════════════════════════════════════════════════════════

def generate_vless_links(
    uuid: str, public_key: str, tunnel_host: str, port: int = 443,
    sni: str = "www.aparat.com"
) -> Tuple[str, str]:
    """تولید لینک‌های استاندارد VLESS Reality."""
    # لینک اصلی
    base = f"vless://{uuid}@{tunnel_host}:{port}?encryption=none&security=reality&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={public_key}"

    full_link = base + "#G2Ray-Aparat-Auto"

    # لینک دوم (فاقد فرگمنت)
    raw_link = base

    return full_link, raw_link


def print_connection_summary(config_data: dict) -> None:
    """نمایش نهایی و جذاب اطلاعات اتصال در خروجی."""
    uuid = config_data.get("uuid", "")
    pub = config_data.get("public_key", "")
    tunnel = config_data.get("tunnel", "")
    port = config_data.get("port", 443)
    sni = config_data.get("sni", "www.aparat.com")

    full, _ = generate_vless_links(uuid, pub, tunnel, port, sni)

    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║                    اطلاعات اتصال G2Ray Reality                    ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   {Colors.GREEN}UUID:{Colors.END}        {uuid}
║   {Colors.GREEN}Public Key:{Colors.END}   {pub}
║   {Colors.GREEN}SNI (Goal):{Colors.END}   {sni}
║   {Colors.GREEN}Port:{Colors.END}        {port}
║   {Colors.GREEN}Flow:{Colors.END}        xtls-rprx-vision
║   {Colors.GREEN}Network:{Colors.END}     tcp
║   {Colors.GREEN}Security:{Colors.END}    reality
║   {Colors.GREEN}Fingerprint:{Colors.END} chrome
║   {Colors.GREEN}Tunnel Host:{Colors.END} {tunnel}
║                                                                   ║
║   لینک کامل اتصال:                                               ║
║   {full}
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
{Colors.END}""")


# ══════════════════════════════════════════════════════════════
# 5. MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main() -> int:
    """تابع اصلی مدیریت تمام فرآیندها."""
    print_banner()

    # پارس آرگومان‌ها
    parser = argparse.ArgumentParser(description="G2Ray Reality Panel")
    parser.add_argument("--tunnel", choices=["bore", "ssh", "auto"], default="auto", help="نوع تونل")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="هدف شبیه‌سازی")
    parser.add_argument("--sni", nargs='+', default=None, help="SNI لیست")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="پورت لوکال")
    parser.add_argument("--backup-site", action="store_true", help="استفاده از سایت پشتیبان")
    args = parser.parse_args()

    # انتخاب سایت هدف
    dest = args.dest
    sni_list = args.sni if args.sni else DEFAULT_SERVER_NAMES
    if args.backup_site:
        chosen = random.choice(backup_iranian_sites)
        dest = chosen["dest"]
        sni_list = chosen["sni"]
        log_info(f"سایت پشتیبان انتخاب شد: {sni_list[0]}")

    # 1. دانلود Xray-Core
    if not download_xray_core():
        return 1

    # 2. تولید هویت
    log_info("تولید هویت امنیتی...")
    uid, pub, priv = generate_reality_identity()
    if not all([uid, pub, priv]):
        return log_critical("تولید هویت ناموفق")
    log_success(f"UUID: {uid}")

    # 3. ساخت و ذخیره پیکربندی
    log_info("ساخت پیکربندی Reality...")
    config = generate_reality_config(uid, priv.strip(), port=args.port, dest=dest, server_names=sni_list)
    if not save_config(config):
        return 1

    # 4. اجرای Xray-Core
    log_info("راه‌اندازی سرویس Xray...")
    xray_cmd = f"{XRAY_BIN} run -config /tmp/g2ray_config.json > /tmp/xray.log 2>&1 &"
    code, _, _ = run_command(xray_cmd)
    if code != 0:
        return log_critical("اجرای Xray ناموفق")
    time.sleep(2)
    log_success("سرویس Xray فعال شد")

    # 5. راه‌اندازی تونل
    tunnel_host: Optional[str] = None
    if args.tunnel in ("auto", "bore"):
        tunnel_host = start_bore_tunnel(args.port)
    if not tunnel_host and args.tunnel in ("auto", "ssh"):
        tunnel_host = start_ssh_tunnel(args.port)

    if not tunnel_host:
        return log_critical("خطا در برقراری تونل. ارتباط میسر نشد")

    # 6. جمع‌بندی اطلاعات
    connection_data = {
        "uuid": uid,
        "public_key": pub,
        "private_key": priv,
        "port": args.port,
        "tunnel": str(tunnel_host),
        "sni": str(sni_list[0]),
        "link": ""
    }

    # 7. نمایش و ذخیره‌سازی نهایی
    print_connection_summary(connection_data)

    log_info("سرور آماده دریافت اتصال است. (برای خروج Ctrl+C را بزنید)")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log_info("پنل متوقف شد")

    return 0


if __name__ == "__main__":
    sys.exit(main())
