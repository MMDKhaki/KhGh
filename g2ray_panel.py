#!/usr/bin/env python3
"""
G2Ray Reality Panel – Ultimate Robust Version (Fixed & Secured)
VLESS + XTLS + Reality  |  شبیه‌ساز آپارات  |  مخصوص GitHub Actions
"""

import subprocess, json, sys, os, time, argparse, random, re, shutil, signal, socket, urllib.request

# ════════════════ CONFIGURATION ════════════════
LOCAL_PORT          = 10000
XRAY_DIR            = Path("./xray")
XRAY_BIN            = XRAY_DIR / "xray"
CONFIG_PATH         = Path("/tmp/g2ray_config.json")
BORE_BIN            = Path("/usr/local/bin/bore")
BORE_DOWNLOAD_URL   = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"
TUNNEL_TIMEOUT      = 20
MONITOR_INTERVAL    = 300       # ۵ دقیقه
HEARTBEAT_WINDOW    = 30        # هر ۳۰ ثانیه در بازه‌ی ۵ دقیقه

# سایت‌های ایرانی دارای HTTP/2 (شبیه‌سازی‌شده)
IRANIAN_SITES = [
    {"dest": "www.aparat.com:443",     "sni": ["www.aparat.com", "aparat.com"]},
    {"dest": "www.digikala.com:443",   "sni": ["www.digikala.com", "digikala.com"]},
    {"dest": "www.varzesh3.com:443",   "sni": ["www.varzesh3.com", "varzesh3.com"]},
    {"dest": "www.ninisite.com:443",   "sni": ["www.ninisite.com", "ninisite.com"]},
    {"dest": "www.namnak.com:443",     "sni": ["www.namnak.com", "namnak.com"]},
    {"dest": "www.beytoote.com:443",   "sni": ["www.beytoote.com", "beytoote.com"]},
    {"dest": "www.torob.com:443",      "sni": ["www.torob.com", "torob.com"]},
    {"dest": "www.filimo.com:443",     "sni": ["www.filimo.com", "filimo.com"]},
    {"dest": "yooz.ir:443",            "sni": ["yooz.ir"]},
]

# ════════════════ COLORS & LOGGING ════════════════
class C:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log(msg: str, level: str = "info") -> None:
    prefixes = {
        "info": f"{C.BLUE}[>]{C.END}",
        "success": f"{C.GREEN}[✓]{C.END}",
        "warn": f"{C.YELLOW}[!]{C.END}",
        "error": f"{C.RED}[✗]{C.END}",
        "heartbeat": f"{C.HEADER}[♥]{C.END}",
        "progress": f"{C.CYAN}[…]{C.END}"
    }
    print(f"{prefixes.get(level, '[ ]')} {msg}", flush=True)

def banner():
    print(f"""
{C.BOLD}{C.CYAN}
╔══════════════════════════════════════════════════╗
║       G2Ray Reality Panel – Ultimate Robust      ║
║    VLESS + XTLS + Reality  |  شبیه‌ساز آپارات     ║
╚══════════════════════════════════════════════════╝
{C.END}
""", flush=True)

# ════════════════ SYSTEM UTILS ════════════════
def run_cmd(cmd, shell=True, timeout=30):
    try:
        proc = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def check_command(cmd_name):
    """Returns True if command exists in PATH."""
    return shutil.which(cmd_name) is not None

def is_port_open(port):
    """Check if a TCP port is available on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

# ════════════════ FILE DOWNLOAD (using urllib) ════════════════
def download_file(url, dest_path, desc="file"):
    """Download file using Python's urllib with timeout."""
    log(f"دانلود {desc} ...", "progress")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.81.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(dest_path, 'wb') as f:
                shutil.copyfileobj(response, f)
        if Path(dest_path).stat().st_size == 0:
            log(f"فایل {desc} خالی است", "error")
            return False
        log(f"دانلود {desc} با موفقیت انجام شد", "success")
        return True
    except Exception as e:
        log(f"دانلود ناموفق ({desc}): {e}", "error")
        return False

# ════════════════ XRAY INSTALLATION ════════════════
def install_xray():
    """نصب آخرین نسخه Xray-core با استفاده از API رسمی."""
    log("دریافت لینک آخرین نسخه Xray ...", "progress")
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/XTLS/Xray-core/releases/latest",
            headers={'User-Agent': 'curl/7.81.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        # پیدا کردن فایل linux-64.zip (اصلی)
        download_url = None
        for asset in data['assets']:
            name = asset['name']
            if 'linux-64.zip' in name and 'dgst' not in name:
                download_url = asset['browser_download_url']
                break
        if not download_url:
            log("لینک دانلود در ریلیز پیدا نشد", "error")
            return False
    except Exception as e:
        log(f"خطا در دریافت اطلاعات نسخه: {e}", "error")
        return False

    XRAY_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = XRAY_DIR / "xray.zip"
    if not download_file(download_url, zip_path, "Xray-core"):
        return False

    log("استخراج فایل Xray ...", "progress")
    code, _, err = run_cmd(f"unzip -o {zip_path} -d {XRAY_DIR}")
    if code != 0:
        log(f"خطای unzip: {err}", "error")
        return False

    binary = XRAY_DIR / "xray"
    if not binary.exists():
        log("فایل اجرایی xray یافت نشد", "error")
        return False
    binary.chmod(0o755)
    log("Xray-core با موفقیت نصب شد", "success")
    return True

# ════════════════ REALITY IDENTITY ════════════════
def generate_identity():
    code, uuid_out, err = run_cmd(f"{XRAY_BIN} uuid")
    if code != 0:
        log(f"خطای UUID: {err}", "error")
        return None, None, None
    code, keys_out, err = run_cmd(f"{XRAY_BIN} x25519")
    if code != 0:
        log(f"خطای تولید کلیدها: {err}", "error")
        return None, None, None

    priv = [l.split()[-1] for l in keys_out.splitlines() if "Private" in l]
    pub  = [l.split()[-1] for l in keys_out.splitlines() if "Public" in l]
    if not priv or not pub:
        return None, None, None
    return uuid_out.strip(), pub[0].strip(), priv[0].strip()

# ════════════════ CONFIG BUILDER ════════════════
def build_config(uuid, priv, port, dest, sni):
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

# ════════════════ TUNNEL MANAGEMENT ════════════════
def install_bore():
    if BORE_BIN.exists():
        return True
    log("نصب تونل Bore ...", "progress")
    # ساخت دایرکتوری موقت برای استخراج
    tmp_dir = Path("/tmp/bore_install")
    tmp_dir.mkdir(exist_ok=True)
    tar_path = tmp_dir / "bore.tar.gz"
    if not download_file(BORE_DOWNLOAD_URL, tar_path, "Bore"):
        return False
    code, _, err = run_cmd(f"tar xzf {tar_path} -C {tmp_dir}")
    if code != 0:
        log(f"خطای استخراج bore: {err}", "error")
        return False
    extracted_bin = tmp_dir / "bore"
    if not extracted_bin.exists():
        log("فایل اجرایی bore یافت نشد", "error")
        return False
    # انتقال به محل نصب (با sudo در صورت نیاز)
    try:
        if os.geteuid() == 0:
            shutil.move(str(extracted_bin), str(BORE_BIN))
        else:
            run_cmd(f"sudo mv {extracted_bin} {BORE_BIN}", timeout=10)
        BORE_BIN.chmod(0o755)
        log("Bore نصب شد", "success")
        return True
    except Exception as e:
        log(f"خطای نصب bore: {e}", "error")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def start_bore(port):
    if not install_bore():
        return None, None
    log("اجرای تونل Bore ...", "progress")
    log_file = Path("/tmp/bore_output.txt")
    cmd = f"{BORE_BIN} local {port} --to bore.pub > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TUNNEL_TIMEOUT
    tunnel_addr = None
    while time.time() < deadline:
        if log_file.exists():
            content = log_file.read_text(errors='ignore')
            match = re.search(r'listening on\s+(\S+):(\d+)', content)
            if match:
                host = match.group(1)
                port_num = int(match.group(2))
                tunnel_addr = (host, port_num)
                break
        time.sleep(1)
    if tunnel_addr:
        log(f"Bore فعال: {tunnel_addr[0]}:{tunnel_addr[1]}", "success")
        return tunnel_addr
    else:
        log("Bore پاسخی نداد", "warn")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        return None, None

def start_ssh_tunnel(port):
    if not check_command("ssh"):
        log("ssh یافت نشد (نیاز به openssh-client)", "error")
        return None, None
    log("اجرای تونل SSH (localhost.run) ...", "progress")
    log_file = Path("/tmp/ssh_output.txt")
    cmd = f"ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:{port} nokey@localhost.run > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TUNNEL_TIMEOUT
    tunnel_host = None
    while time.time() < deadline:
        if log_file.exists():
            content = log_file.read_text(errors='ignore')
            match = re.search(r'https?://(\S+)', content)
            if match:
                raw = match.group(1).rstrip('/')
                tunnel_host = raw
                break
        time.sleep(1)
    if tunnel_host:
        # localhost.run معمولاً روی پورت ۴۴۳ (https) در دسترس است
        log(f"SSH تونل فعال: {tunnel_host} (پورت ۴۴۳)", "success")
        return tunnel_host, 443
    else:
        log("SSH تونل پاسخی نداد", "warn")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        return None, None

def obtain_tunnel(port):
    """یک تونل Bore یا SSH ایجاد می‌کند و host, port را برمی‌گرداند."""
    for method in (start_bore, start_ssh_tunnel):
        host, port_num = method(port)
        if host:
            return host, port_num
    return None, None

# ════════════════ VLESS LINK ════════════════
def make_vless_link(uuid, pub_key, host, port, sni):
    return (f"vless://{uuid}@{host}:{port}?encryption=none&security=reality"
            f"&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={pub_key}#G2Ray-Iran")

# ════════════════ MAIN ════════════════
def main():
    banner()
    parser = argparse.ArgumentParser(description="G2Ray Ultimate Panel")
    parser.add_argument("--backup", action="store_true", help="استفاده از سایت تصادفی ایرانی")
    parser.add_argument("--sni", help="SNI دلخواه (مثال: www.digikala.com,digikala.com)")
    args = parser.parse_args()

    if args.backup:
        site = random.choice(IRANIAN_SITES)
        dest, sni = site["dest"], site["sni"]
    else:
        dest = "www.aparat.com:443"
        sni = args.sni.split(",") if args.sni else ["www.aparat.com", "aparat.com"]

    # بررسی پورت
    if not is_port_open(LOCAL_PORT):
        log(f"پورت {LOCAL_PORT} در حال استفاده است. آن را آزاد کنید.", "error")
        sys.exit(1)

    # ۱. نصب Xray
    if not install_xray():
        sys.exit(1)

    # ۲. تولید هویت
    uid, pub, priv = generate_identity()
    if not all([uid, pub, priv]):
        sys.exit(1)
    log(f"UUID: {uid[:8]}... | PublicKey: {pub[:12]}...", "success")

    # ۳. ساخت پیکربندی
    config = build_config(uid, priv, LOCAL_PORT, dest, sni)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    log("پیکربندی Reality ذخیره شد", "success")

    # ۴. راه‌اندازی Xray
    log("راه‌اندازی سرویس Xray ...", "progress")
    xray_proc = subprocess.Popen(
        [str(XRAY_BIN), "run", "-config", str(CONFIG_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    time.sleep(2)
    if xray_proc.poll() is not None:
        log("Xray اجرا نشد – پورت ۱۰۰۰۰ ممکن است اشغال باشد", "error")
        sys.exit(1)
    log("Xray-core فعال است", "success")

    # ۵. تونل
    tunnel_host, tunnel_port = obtain_tunnel(LOCAL_PORT)
    if not tunnel_host:
        log("هیچ تونلی برقرار نشد. کانفیگ بدون تونل معتبر نیست.", "error")
        os.killpg(os.getpgid(xray_proc.pid), signal.SIGTERM)
        sys.exit(1)

    # ۶. نمایش نهایی
    vless_link = make_vless_link(uid, pub, tunnel_host, tunnel_port, sni[0])
    print(f"""
{C.BOLD}{C.GREEN}═══════════════════════════════════════════════════════
 ✅  کانفیگ آماده
───────────────────────────────────────────────────
 {C.CYAN}UUID:{C.END}        {uid}
 {C.CYAN}Public Key:{C.END}  {pub}
 {C.CYAN}SNI:{C.END}         {sni[0]}
 {C.CYAN}Port:{C.END}        {LOCAL_PORT} (محلی) | {tunnel_port} (عمومی)
 {C.CYAN}Destination:{C.END} {dest}
 {C.CYAN}Endpoint:{C.END}    {tunnel_host}:{tunnel_port}
───────────────────────────────────────────────────
 🔗 لینک اتصال:
 {C.GREEN}{vless_link}{C.END}
═══════════════════════════════════════════════════════
 ⏳ سرور فعال است (تا ۶ ساعت). پیام‌های زنده بودن
    هر ۵ دقیقه نمایش داده می‌شود.
{C.END}
""", flush=True)

    # ۷. نگهداری سرور
    def cleanup(signum=None, frame=None):
        log("پایان سرور", "warn")
        if xray_proc.poll() is None:
            os.killpg(os.getpgid(xray_proc.pid), signal.SIGTERM)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    start_time = time.time()
    last_heartbeat = 0
    try:
        while xray_proc.poll() is None:
            time.sleep(30)
            elapsed = int(time.time() - start_time)
            # heartbeat هر ۵ دقیقه یکبار
            if elapsed - last_heartbeat >= MONITOR_INTERVAL:
                log(f"سرور فعال – {elapsed//60} دقیقه گذشته", "heartbeat")
                last_heartbeat = elapsed
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
