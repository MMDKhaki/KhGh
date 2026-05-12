#!/usr/bin/env python3
"""
G2Ray Reality Panel – v2.8 (QR Code + GitHub SNI + Artifacts)
VLESS + XTLS + Reality  |  مخصوص GitHub Actions
"""

import subprocess, json, sys, os, time, argparse, random, re, shutil, signal, socket, urllib.request
from pathlib import Path
from urllib.parse import urlparse
import base64, qrcode, io, textwrap

LOCAL_PORT = 10000
XRAY_DIR = Path("./xray")
XRAY_BIN = XRAY_DIR / "xray"
CONFIG_PATH = Path("/tmp/g2ray_config.json")
BORE_BIN = Path("/usr/local/bin/bore")
BORE_DOWNLOAD_URL = "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz"
MONITOR_INTERVAL = 300

IRANIAN_SITES = [
    {"dest": "www.aparat.com:443", "sni": ["www.aparat.com", "aparat.com"]},
    {"dest": "www.digikala.com:443", "sni": ["www.digikala.com", "digikala.com"]},
    {"dest": "www.varzesh3.com:443", "sni": ["www.varzesh3.com", "varzesh3.com"]},
    {"dest": "www.ninisite.com:443", "sni": ["www.ninisite.com", "ninisite.com"]},
    {"dest": "www.namnak.com:443", "sni": ["www.namnak.com", "namnak.com"]},
    {"dest": "www.beytoote.com:443", "sni": ["www.beytoote.com", "beytoote.com"]},
    {"dest": "www.torob.com:443", "sni": ["www.torob.com", "torob.com"]},
    {"dest": "www.filimo.com:443", "sni": ["www.filimo.com", "filimo.com"]},
    {"dest": "yooz.ir:443", "sni": ["yooz.ir"]},
]

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

def download_file(url, dest_path, desc="file"):
    log(f"دانلود {desc} ...", "progress")
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

def install_xray():
    log("دریافت لینک آخرین نسخه Xray...", "progress")
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/XTLS/Xray-core/releases/latest",
            headers={'User-Agent': 'curl/7.81.0'}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        download_url = None
        for asset in data['assets']:
            if 'linux-64.zip' in asset['name'] and 'dgst' not in asset['name']:
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

    log("استخراج Xray...", "progress")
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
            {
                "protocol": "freedom",
                "tag": "direct",
                "settings": {
                    "domainStrategy": "UseIP",
                    "timeout": 10
                }
            },
            {"protocol": "blackhole", "tag": "block"}
        ]
    }

def test_dest_reachable(dest):
    host, port_str = dest.split(":")
    port = int(port_str)
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except Exception:
        return False

def find_working_dest(backup=False, github_sni=False):
    if github_sni:
        dest = "github.com:443"
        sni = ["github.com"]
        if test_dest_reachable(dest):
            log(f"مقصد GitHub انتخاب شد: {dest}", "success")
            return dest, sni
        else:
            log("github.com:443 در دسترس نیست!", "error")
            return None, None
    if backup:
        random.shuffle(IRANIAN_SITES)
        for site in IRANIAN_SITES:
            if test_dest_reachable(site["dest"]):
                log(f"مقصد سالم: {site['dest']}", "success")
                return site["dest"], site["sni"]
    else:
        default = "www.aparat.com:443"
        if test_dest_reachable(default):
            return default, ["www.aparat.com", "aparat.com"]
        for site in IRANIAN_SITES:
            if test_dest_reachable(site["dest"]):
                log(f"آپارات در دسترس نبود. استفاده از {site['dest']}", "warn")
                return site["dest"], site["sni"]
    return None, None

def install_bore():
    if BORE_BIN.exists():
        return True
    log("نصب تونل Bore...", "progress")
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

    log("بررسی دسترسی به bore.pub...", "progress")
    try:
        with socket.create_connection(("bore.pub", 7835), timeout=5):
            log("bore.pub در دسترس است", "success")
    except Exception:
        log("bore.pub در حال حاضر از این رانر مسدود یا قطع است", "warn")
        return None, None

    for attempt in range(1, 3):
        if attempt > 1:
            log(f"تلاش مجدد Bore (بار {attempt})...", "warn")
            time.sleep(5)
        else:
            log(f"اجرای تونل Bore (تلاش {attempt})...", "progress")

        log_file = Path("/tmp/bore_output.txt")
        cmd = f"{BORE_BIN} local {port} --to bore.pub > {log_file} 2>&1"
        proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 35
        tunnel_addr = None
        while time.time() < deadline:
            if log_file.exists():
                content = log_file.read_text(errors='ignore')
                match = re.search(r'listening (?:on|at)\s+(\S+):(\d+)', content)
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
            if log_file.exists():
                stderr_content = log_file.read_text(errors='ignore')
                if stderr_content.strip():
                    log(f"خروجی Bore:\n{stderr_content.strip()}", "error")
            log("Bore در این تلاش پاسخی نداد", "warn")
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

    return None, None

def start_ssh_tunnel(port):
    if not shutil.which("ssh"):
        log("ssh یافت نشد", "error")
        return None, None
    log("اجرای تونل SSH (localhost.run)...", "progress")
    log_file = Path("/tmp/ssh_output.txt")
    cmd = f"ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:{port} nokey@localhost.run > {log_file} 2>&1"
    proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 20
    tunnel_host = None
    tunnel_port = None
    while time.time() < deadline:
        if log_file.exists():
            content = log_file.read_text(errors='ignore')
            for match in re.finditer(r'(https?://[^\s\]]+)', content):
                url = match.group(0)
                parsed = urlparse(url)
                hostname = parsed.hostname
                if hostname and (hostname.endswith('localhost.run') or hostname.endswith('lhr.life')):
                    tunnel_host = hostname
                    tunnel_port = parsed.port if parsed.port else (443 if parsed.scheme == 'https' else 80)
                    break
            if tunnel_host:
                break
        time.sleep(1)
    if tunnel_host:
        log(f"SSH تونل فعال: {tunnel_host}:{tunnel_port}", "success")
        return tunnel_host, tunnel_port
    else:
        log("SSH تونل پاسخی نداد", "warn")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        return None, None

def obtain_tunnel(port):
    host, port_num = start_bore(port)
    if host:
        return host, port_num
    return start_ssh_tunnel(port)

def make_vless_link(uuid, pub_key, host, port, sni):
    host = re.sub(r'[\[\]\s]', '', host.strip())
    return (f"vless://{uuid}@{host}:{port}?encryption=none&security=reality"
            f"&flow=xtls-rprx-vision&type=tcp&sni={sni}&fp=chrome&pbk={pub_key}#G2Ray-Iran")

def generate_qr(data: str, output_png="qr.png", ascii_art=True):
    """Generate QR code PNG and ASCII representation."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_png)
    log(f"QR code saved as {output_png}", "success")
    if ascii_art:
        # Print ASCII QR to terminal
        qr_img = img.convert('L')
        width, height = qr_img.size
        ascii_str = ""
        for y in range(0, height, 10):
            row = ""
            for x in range(0, width, 10):
                pixel = qr_img.getpixel((x, y))
                row += "█" if pixel < 128 else " "
            ascii_str += row + "\n"
        print(f"\n{C.BOLD}{C.CYAN}QR Code (ASCII):{C.END}\n{ascii_str}")

def main():
    banner()
    parser = argparse.ArgumentParser(description="G2Ray Ultimate Panel")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--github", action="store_true", help="Use github.com as SNI/destination")
    parser.add_argument("--sni")
    args = parser.parse_args()

    if args.github:
        dest, sni = find_working_dest(github_sni=True)
        if not dest:
            log("GitHub mode failed", "error")
            sys.exit(1)
    elif args.backup:
        dest, sni = find_working_dest(backup=True)
    else:
        if args.sni:
            sni = args.sni.split(",")
            dest = f"{sni[0]}:443" if ":" not in sni[0] else sni[0]
            if not test_dest_reachable(dest):
                log(f"مقصد {dest} در دسترس نیست", "error")
                sys.exit(1)
        else:
            dest, sni = find_working_dest(backup=False)
            if not dest:
                log("هیچ مقصد سالمی پیدا نشد", "error")
                sys.exit(1)

    if not is_port_open(LOCAL_PORT):
        log(f"پورت {LOCAL_PORT} اشغال است", "error")
        sys.exit(1)

    if not install_xray():
        sys.exit(1)

    uid, pub, priv = generate_identity()
    if not all([uid, pub, priv]):
        sys.exit(1)

    config = build_config(uid, priv, LOCAL_PORT, dest, sni)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    log("پیکربندی Reality ذخیره شد", "success")

    log("راه‌اندازی Xray...", "progress")
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

    log("تست اتصال به تونل...", "progress")
    try:
        with socket.create_connection((tunnel_host, tunnel_port), timeout=5) as s:
            log("تونل قابل دسترسی است", "success")
    except Exception as e:
        log(f"اتصال به تونل ناموفق: {e}", "error")
        os.killpg(os.getpgid(xray_proc.pid), signal.SIGTERM)
        sys.exit(1)

    vless_link = make_vless_link(uid, pub, tunnel_host, tunnel_port, sni[0])

    # --- Write artifacts ---
    Path("vless_link.txt").write_text(vless_link)
    Path("config_summary.json").write_text(json.dumps({
        "uuid": uid,
        "public_key": pub,
        "sni": sni[0],
        "local_port": LOCAL_PORT,
        "tunnel_host": tunnel_host,
        "tunnel_port": tunnel_port,
        "destination": dest,
        "vless_link": vless_link
    }, indent=2))

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
""", flush=True)

    # Generate QR code
    try:
        generate_qr(vless_link, output_png="qr.png", ascii_art=True)
    except Exception as e:
        log(f"QR generation failed: {e}", "warn")

    print(f"\n{C.BOLD}{C.YELLOW}⬇️  Download your config at workflow artifacts.{C.END}\n", flush=True)
    sys.exit(0)   # Exit cleanly for workflow artifacts to be uploaded

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"{C.RED}[✗] خطای بحرانی:{C.END} {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
