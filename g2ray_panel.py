#!/usr/bin/env python3
"""
G2Ray Reality Panel – Ultimate Robust Version (v2.1 – Debuggable)
VLESS + XTLS + Reality  |  شبیه‌ساز آپارات  |  مخصوص GitHub Actions
"""

import subprocess, json, sys, os, time, argparse, random, re, shutil, signal, socket, urllib.request, traceback
from pathlib import Path

# ════════════════ CONFIGURATION ════════════════
LOCAL_PORT          = 10000
XRAY_DIR            = Path("./xray")
XRAY_BIN            = XRAY_DIR / "xray"
CONFIG_PATH         = Path("/tmp/g2ray_config.json")
BORE_BIN            = Path("/usr/local/bin/bore")
BORE_DOWNLOAD_URL   = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"
TUNNEL_TIMEOUT      = 20
MONITOR_INTERVAL    = 300

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

def log(msg, level="info"):
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

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

# ════════════════ FILE DOWNLOAD (urllib with redirect handling) ════════════════
def download_file(url, dest_path, desc="file"):
    log(f"دانلود {desc} از {url[:60]}...", "progress")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.81.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(dest_path, 'wb') as f:
                shutil.copyfileobj(response, f)
        if Path(dest_path).stat().st_size == 0:
            log(f"فایل {desc} خالی است", "error")
            return False
        log(f"دانلود {desc} موفق", "success")
        return True
    except Exception as e:
        log(f"دانلود ناموفق ({desc}): {e}", "error")
        return False

# ════════════════ XRAY INSTALLATION ════════════════
def install_xray():
    log("دریافت لینک آخرین نسخه Xray ...", "progress")
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/XTLS/Xray-core/releases/latest",
            headers={'User-Agent': 'curl/7.81.0'}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        download_url = None
        for asset in data['assets']:
            name = asset['name']
            if 'linux-64.zip' in name and 'dgst' not in name:
                download_url = asset['browser_download_url']
                break
        if not download_url:
            log("لینک دانلود پیدا نشد", "error")
            return False
    except Exception as e:
        log(f"خطا در دریافت ریلیز: {e}", "error")
        return False

    XRAY_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = XRAY_DIR / "xray.zip"
    if not download_file(download_url, zip_path, "Xray-core"):
        return False

    log("استخراج Xray ...", "progress")
    code, _, err = run_cmd(f"unzip -o {zip_path} -d {XRAY_DIR}")
    if code != 0:
        log(f"خطای unzip: {err}", "error")
        return False

    binary = XRAY_DIR / "xray"
    if not binary.exists():
        log("فایل xray پیدا نشد", "error")
        return False
    binary.chmod(0o755)
    log("Xray-core نصب شد", "success")
    return True

# ════════════════ REALITY IDENTITY ════════════════
def generate_identity():
    code, uuid_out, err = run_cmd(f"{XRAY_BIN} uuid")
    if code != 0:
        log(f"خطای UUID: {err}", "error")
        return None, None, None
    code, keys_out, err = run_cmd(f"{XRAY_BIN} x25519")
    if code != 0:
        log(f"خطای تولید کلید: {err}", "error")
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
        log("فایل bore پیدا نشد", "error")
        return False
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
    log("اجرای تونل SSH ...", "progress")
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
        log(f"SSH تونل فعال: {tunnel_host} (پورت ۴۴۳)", "success")
        return tunnel_host, 443
    else:
        log("SSH تونل پاسخی نداد", "warn")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        return None, None

def obtain_tunnel(port):
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
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--sni")
    args = parser.parse_args()

    if args.backup:
        site = random.choice(IRANIAN_SITES)
        dest, sni = site["dest"], site["sni"]
    else:
        dest = "www.aparat.com:443"
        sni = args.sni.split(",") if args.sni else ["www.aparat.com", "aparat.com"]

    if not is_port_open(LOCAL_PORT):
        log(f"پورت {LOCAL_PORT} اشغال است", "error")
        sys.exit(1)

    if not install_xray():
        log("نصب Xray شکست خورد", "error")
        sys.exit(1)

    uid, pub, priv = generate_identity()
    if not all([uid, pub, priv]):
        log("تولید هویت شکست خورد", "error")
        sys.exit(1)
    log(f"UUID: {uid[:8]}... | PublicKey: {pub[:12]}...", "success")

    config = build_config(uid, priv, LOCAL_PORT, dest, sni)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    log("پیکربندی Reality ذخیره شد", "success")

    log("راه‌اندازی Xray ...", "progress")
    xray_proc = subprocess.Popen(
        [str(XRAY_BIN), "run", "-config", str(CONFIG_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    time.sleep(2)
    if xray_proc.poll() is not None:
        log("Xray نتوانست اجرا شود", "error")
        sys.exit(1)
    log("Xray-core فعال است", "success")

    tunnel_host, tunnel_port = obtain_tunnel(LOCAL_PORT)
    if not tunnel_host:
        log("هیچ تونلی برقرار نشد", "error")
        os.killpg(os.getpgid(xray_proc.pid), signal.SIGTERM)
        sys.exit(1)

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
            if elapsed - last_heartbeat >= MONITOR_INTERVAL:
                log(f"سرور فعال – {elapsed//60} دقیقه گذشته", "heartbeat")
                last_heartbeat = elapsed
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"{C.RED}[✗] خطای بحرانی:{C.END} {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
