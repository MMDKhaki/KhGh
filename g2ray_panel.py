#!/usr/bin/env python3
"""
G2Ray Reality Panel – Ultimate Stable Version
VLESS + XTLS + Reality | عبور از فیلترینگ با شبیه‌سازی آپارات
همهٔ توابع دارای تایم‌اوت مستقل، تلاش مجدد و fallback هستند.
"""

import subprocess, json, sys, os, time, argparse, random, re, shutil, signal
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# ════════════════ CONFIGURATION ════════════════
LOCAL_PORT          = 10000
XRAY_DIR            = Path("./xray")
XRAY_BIN            = XRAY_DIR / "xray"
CONFIG_PATH         = Path("/tmp/g2ray_config.json")
BORE_BIN            = Path("/usr/local/bin/bore")
BORE_URL            = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"
DOWNLOAD_TIMEOUT    = 120           # ثانیه
TUNNEL_TIMEOUT      = 20            # ثانیه برای هر تونل
MONITOR_INTERVAL    = 300           # گزارش وضعیت هر ۵ دقیقه

# سایت‌های ایرانی دارای HTTP/2 (ترافیک عادی)
IRANIAN_SITES = [
    {"dest": "www.aparat.com:443",     "sni": ["www.aparat.com", "aparat.com"]},
    {"dest": "www.digikala.com:443",   "sni": ["www.digikala.com", "digikala.com"]},
    {"dest": "www.varzesh3.com:443",   "sni": ["www.varzesh3.com", "varzesh3.com"]},
    {"dest": "www.ninisite.com:443",   "sni": ["www.ninisite.com", "ninisite.com"]},
    {"dest": "www.namnak.com:443",     "sni": ["www.namnak.com", "namnak.com"]},
    {"dest": "www.beytoote.com:443",   "sni": ["www.beytoote.com", "beytoote.com"]},
    {"dest": "www.torob.com:443",      "sni": ["www.torob.com", "torob.com"]},
    {"dest": "www.filimo.com:443",     "sni": ["www.filimo.com", "filimo.com"]},
    {"dest": "yooz.ir:443",            "sni": ["yooz.ir", "yooz.ir"]},
]

# ════════════════ LOGGING & COLORS ════════════════
class C:
    HEADER = '\033[95m'; BLUE = '\033[94m'; GREEN = '\033[92m'
    YELLOW = '\033[93m'; RED = '\033[91m'; END = '\033[0m'; BOLD = '\033[1m'

def log(msg: str, level: str = "info") -> None:
    prefixes = {
        "info": f"{C.BLUE}[>]{C.END}",
        "success": f"{C.GREEN}[✓]{C.END}",
        "warn": f"{C.YELLOW}[!]{C.END}",
        "error": f"{C.RED}[✗]{C.END}",
        "heartbeat": f"{C.HEADER}[♥]{C.END}"
    }
    print(f"{prefixes.get(level, '[ ]')} {msg}")

def banner():
    print(f"""
{C.BOLD}{C.CYAN}
╔══════════════════════════════════════════════════╗
║       G2Ray Reality Panel – Ultimate Stable      ║
║    VLESS + XTLS + Reality  |  شبیه‌ساز آپارات     ║
╚══════════════════════════════════════════════════╝
{C.END}
""")

# ════════════════ SYSTEM UTILS ════════════════
def run_cmd(cmd: str, timeout: int = 30, shell: bool = True) -> Tuple[int, str, str]:
    """اجرای یک فرمان با timeout و ثبت خروجی"""
    try:
        proc = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def download_with_curl(url: str, dest: Path, timeout: int = DOWNLOAD_TIMEOUT) -> bool:
    """دانلود فایل با curl و تایم‌اوت مشخص (بدون hang)"""
    log(f"دانلود {dest.name} از {url[:50]}...", "info")
    code, _, err = run_cmd(
        f"curl -sL --max-time {timeout} '{url}' -o {dest}",
        timeout=timeout + 10
    )
    if code != 0:
        log(f"خطای دانلود: {err}", "error")
        return False
    if dest.stat().st_size == 0:
        log("فایل دانلود شده خالی است", "error")
        return False
    log("دانلود موفق", "success")
    return True

# ════════════════ XRAY CORE INSTALLATION ════════════════
def install_xray() -> bool:
    """نصب آخرین نسخه Xray-core با دانلود مطمئن"""
    log("دریافت آخرین لینک Xray-core...", "info")
    code, out, _ = run_cmd(
        "curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | "
        "grep 'browser_download_url.*linux-64.zip' | grep -v 'dgst' | "
        "cut -d : -f 2,3 | tr -d '\"' | tr -d ' '"
    )
    if code != 0 or not out:
        log("خطا در دریافت لینک Xray", "error")
        return False
    url = out.splitlines()[0].strip()
    XRAY_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = XRAY_DIR / "xray.zip"
    if not download_with_curl(url, zip_path):
        return False

    log("استخراج فایل Xray...", "info")
    code, _, err = run_cmd(f"unzip -o {zip_path} -d {XRAY_DIR}")
    if code != 0:
        log(f"خطای unzip: {err}", "error")
        return False

    binary = XRAY_DIR / "xray"
    if not binary.exists():
        log("فایل اجرایی xray پیدا نشد", "error")
        return False
    binary.chmod(0o755)
    log("Xray-core با موفقیت نصب شد", "success")
    return True

# ════════════════ REALITY IDENTITY ════════════════
def generate_identity() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """ساخت UUID و کلیدهای امنیتی Reality"""
    code, uuid_out, err = run_cmd(f"{XRAY_BIN} uuid")
    if code != 0:
        log(f"خطای UUID: {err}", "error")
        return None, None, None
    code, keys_out, err = run_cmd(f"{XRAY_BIN} x25519")
    if code != 0:
        log(f"خطای x25519: {err}", "error")
        return None, None, None

    priv = [l.split()[-1] for l in keys_out.splitlines() if "Private" in l]
    pub  = [l.split()[-1] for l in keys_out.splitlines() if "Public" in l]
    if not priv or not pub:
        log("کلیدهای Reality استخراج نشد", "error")
        return None, None, None
    return uuid_out.strip(), pub[0].strip(), priv[0].strip()

# ════════════════ CONFIG GENERATOR ════════════════
def build_config(uuid: str, priv: str, port: int, dest: str, sni: List[str]) -> Dict:
    """تولید پیکربندی Reality برای Xray"""
    return {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": [{
            "tag": "reality-in",
            "listen": "0.0.0.0",
            "port": port,
            "protocol": "vless",
            "settings": {
                "clients": [{
                    "id": uuid,
                    "flow": "xtls-rprx-vision"
                }],
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

# ════════════════ TUNNEL METHODS ════════════════
def install_bore() -> bool:
    """نصب Bore در صورت عدم وجود"""
    if BORE_BIN.exists():
        return True
    log("نصب تونل Bore...", "info")
    code, _, _ = run_cmd(f"curl -sL '{BORE_URL}' | tar xz -C /tmp && sudo mv /tmp/bore {BORE_BIN}", timeout=30)
    if code != 0 or not BORE_BIN.exists():
        log("نصب Bore ناموفق", "error")
        return False
    BORE_BIN.chmod(0o755)
    return True

def start_bore(port: int, timeout: int = TUNNEL_TIMEOUT) -> Optional[str]:
    """ایجاد تونل Bore با تایم‌اوت و نظارت بر فایل خروجی"""
    if not install_bore():
        return None

    log("اجرای تونل Bore...", "info")
    log_file = Path("/tmp/bore_output.txt")
    cmd = f"{BORE_BIN} local {port} --to bore.pub > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)  # detach
    deadline = time.time() + timeout
    tunnel_addr = None
    while time.time() < deadline:
        if log_file.exists() and log_file.stat().st_size > 0:
            content = log_file.read_text(errors='ignore')
            match = re.search(r'listening on\s+(\S+:\d+)', content)
            if match:
                tunnel_addr = match.group(1)
                break
        time.sleep(1)

    if tunnel_addr:
        log(f"Bore فعال شد: {tunnel_addr}", "success")
        return tunnel_addr
    else:
        log("Bore در زمان مقرر پاسخی نداد", "warn")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM) if proc else None
        return None

def start_ssh_tunnel(port: int, timeout: int = TUNNEL_TIMEOUT) -> Optional[str]:
    """تونل SSH با localhost.run (رایگان و بدون ثبت‌نام)"""
    log("اجرای تونل SSH (localhost.run)...", "info")
    log_file = Path("/tmp/ssh_output.txt")
    cmd = f"ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:{port} nokey@localhost.run > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    deadline = time.time() + timeout
    tunnel_host = None
    while time.time() < deadline:
        if log_file.exists() and log_file.stat().st_size > 0:
            content = log_file.read_text(errors='ignore')
            match = re.search(r'https?://(\S+)', content)
            if match:
                raw = match.group(1)
                # حذف پروتکل و / اضافی
                tunnel_host = raw.replace('https://', '').replace('http://', '').rstrip('/')
                break
        time.sleep(1)

    if tunnel_host:
        log(f"SSH تونل فعال: {tunnel_host}", "success")
        return tunnel_host
    else:
        log("SSH تونل پاسخی نداد", "warn")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM) if proc else None
        return None

def obtain_tunnel(port: int) -> str:
    """امتحان تونل‌ها به ترتیب و برگرداندن اولین مورد موفق"""
    for method in (start_bore, start_ssh_tunnel):
        addr = method(port)
        if addr:
            return addr
    return "NO_TUNNEL"

# ════════════════ VLESS LINK BUILDER ════════════════
def make_vless_link(uuid: str, pub_key: str, host: str, port: int, sni: str) -> str:
    """تولید لینک استاندارد VLESS Reality"""
    return (f"vless://{uuid}@{host}:{port}?encryption=none&security=reality"
            f"&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={pub_key}"
            f"#G2Ray-Iran")

# ════════════════ MAIN ORCHESTRATOR ════════════════
def main():
    banner()
    parser = argparse.ArgumentParser(description="G2Ray Ultimate Panel")
    parser.add_argument("--backup", action="store_true",
                        help="استفاده از یک سایت تصادفی ایرانی به جای آپارات")
    parser.add_argument("--sni", help="SNI دلخواه (مثال: www.digikala.com,digikala.com)")
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
    if not all([uid, pub, priv]):
        log("تولید هویت امنیتی شکست خورد", "error")
        sys.exit(1)
    log(f"UUID: {uid[:8]}... | PublicKey: {pub[:12]}...", "success")

    # ۳. ساخت پیکربندی
    config = build_config(uid, priv, LOCAL_PORT, dest, sni)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    log("پیکربندی Reality ذخیره شد", "success")

    # ۴. اجرای Xray-core
    log("راه‌اندازی سرویس Xray...", "info")
    xray_proc = subprocess.Popen(
        [str(XRAY_BIN), "run", "-config", str(CONFIG_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    time.sleep(2)
    if xray_proc.poll() is not None:
        log("Xray نتوانست اجرا شود (پورت شاید در دسترس نباشد)", "error")
        sys.exit(1)
    log("Xray-core با موفقیت اجرا شد", "success")

    # ۵. تهیه تونل
    tunnel_addr = obtain_tunnel(LOCAL_PORT)
    if tunnel_addr == "NO_TUNNEL":
        log("هیچ تونلی فعال نشد. کانفیگ بدون تونل نمایش داده می‌شود.", "warn")
        # ادامه می‌دهیم تا کاربر کانفیگ را دریافت کند (باید خودش تونل تهیه کند)

    # ۶. چاپ اطلاعات اتصال
    endpoint = tunnel_addr if tunnel_addr != "NO_TUNNEL" else "YOUR_TUNNEL_ADDRESS:PORT"
    vless_link = make_vless_link(uid, pub, endpoint, LOCAL_PORT, sni[0])
    print(f"""
{C.BOLD}{C.GREEN}═══════════════════════════════════════════════════════
 ✅  کانفیگ آماده – از لینک زیر استفاده کنید
───────────────────────────────────────────────────
 {C.CYAN}UUID:{C.END}        {uid}
 {C.CYAN}Public Key:{C.END}  {pub}
 {C.CYAN}SNI:{C.END}         {sni[0]}
 {C.CYAN}Port:{C.END}        {LOCAL_PORT}
 {C.CYAN}Destination:{C.END} {dest}
 {C.CYAN}Endpoint:{C.END}    {endpoint}
───────────────────────────────────────────────────
 🔗 لینک اتصال نهایی:
 {C.GREEN}{vless_link}{C.END}
═══════════════════════════════════════════════════════
 ⏳ سرور اکنون فعال است و تا ۶ ساعت کار می‌کند.
    هر ۵ دقیقه یک بار پیام زنده بودن نمایش داده می‌شود.
    برای توقف می‌توانید Workflow را کنسل کنید.
{C.END}
""")

    # ۷. نظارت بر سرور و ارسال heartbeat
    def handler(signum, frame):
        log("دریافت سیگنال توقف", "warn")
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    start_time = time.time()
    try:
        while xray_proc.poll() is None:
            elapsed = int(time.time() - start_time)
            if elapsed % MONITOR_INTERVAL < 30:  # پنجره ۳۰ ثانیه‌ای برای چاپ
                log(f"سرور فعال است ({elapsed//60} دقیقه گذشته)", "heartbeat")
                # چاپ مجدد لینک برای دسترسی آسان در لاگ
                print(f"{C.GREEN}لینک جاری: {vless_link}{C.END}")
            time.sleep(30)
    except KeyboardInterrupt:
        log("خاتمه سرور", "warn")
    finally:
        if xray_proc.poll() is None:
            os.killpg(os.getpgid(xray_proc.pid), signal.SIGTERM)
        log("سرویس G2Ray خاتمه یافت", "info")

if __name__ == "__main__":
    main()
