#!/usr/bin/env python3
"""
GitHub Actions VLESS Config Generator
نسخه 1.0 - دیباگ شده و بهینه
"""

import os, json, uuid, subprocess, sys, base64, time
import requests

# ---------- تنظیمات ثابت ----------
CONFIG_OUTPUT_FILE = "config_output.txt"
QR_OUTPUT_FILE = "config_qr.png"
XRAY_CONFIG_FILE = "xray_config.json"
XRAY_BIN = "./xray"
XRAY_VERSION = "v1.8.23"

# برای امنیت بیشتر، این مقادیر رو میتونی عوض کنی
FALLBACK_DEST = "www.aparat.com" # سایت ایرانی برای fallback
FALLBACK_PORT = 443

# لیست ۲۵ سایت برتر ایران برای مسیریابی (بر اساس Similarweb 2025)
IRAN_TOP_SITES = [
    "aparat.com", "digikala.com", "varzesh3.com", "shaparak.ir",
    "namava.ir", "filimo.com", "bama.ir", "divar.ir", "snapp.ir",
    "zoomit.ir", "isna.ir", "irna.ir", "namnak.com", "emalls.ir",
    "cafebazaar.ir", "ninisite.com", "torob.com", "soft98.ir",
    "digiato.com", "zoomnews.ir", "telewebion.com", "yjc.ir",
    "khabaronline.ir", "farsnews.ir", "mehrnews.com"
]

def run_cmd(cmd, check=True):
    """اجرای دستورات سیستم با مدیریت خطا"""
    print(f"[CMD] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e}")
        print(f"[ERROR] stderr: {e.stderr}")
        raise

def get_public_ip():
    """دریافت IP عمومی Runner با چند منبع پشتیبان"""
    apis = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]
    for api in apis:
        try:
            print(f"[*] Trying to get IP from {api}...")
            ip = requests.get(api, timeout=10).text.strip()
            if ip and '.' in ip:
                print(f"[OK] Public IP: {ip}")
                return ip
        except Exception as e:
            print(f"[WARN] Could not fetch IP from {api}: {e}")
    raise Exception("Failed to get public IP from all sources")

def download_xray():
    """دانلود Xray-core از گیت‌هاب (مستقیم)"""
    url = f"https://github.com/XTLS/Xray-core/releases/download/{XRAY_VERSION}/Xray-linux-64.zip"
    print(f"[*] Downloading Xray-core {XRAY_VERSION}...")
    
    # تلاش دانلود با حداکثر 3 بار
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=120, stream=True)
            response.raise_for_status()
            with open("xray.zip", "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("[OK] Xray downloaded successfully")
            break
        except Exception as e:
            print(f"[WARN] Download attempt {attempt+1} failed: {e}")
            time.sleep(2)
    else:
        raise Exception("Failed to download Xray after 3 attempts")
    
    # استخراج فایل
    run_cmd(["unzip", "-o", "xray.zip", "xray"])
    os.chmod("xray", 0o755)
    print("[OK] Xray binary is ready")

def generate_keys():
    """تولید کلیدهای امنیتی و UUID"""
    # اجرای Xray برای تولید UUID
    uuid_output = run_cmd([XRAY_BIN, "uuid"])
    uid = uuid_output.strip()
    
    # تولید کلید خصوصی x25519
    keys_output = run_cmd([XRAY_BIN, "x25519"])
    # خروجی شامل "Private key: ..." و "Public key: ..." است
    lines = keys_output.split('\n')
    private_key = lines[0].replace("Private key:", "").strip()
    public_key = lines[1].replace("Public key:", "").strip()
    
    # تولید shortId تصادفی
    short_id = uuid.uuid4().hex[:16]
    
    print(f"[OK] UUID: {uid}")
    print(f"[OK] Private Key: {private_key[:20]}...")
    print(f"[OK] Short ID: {short_id}")
    
    return uid, private_key, public_key, short_id

def generate_xray_config(public_ip, uid, private_key, short_id):
    """ایجاد فایل کانفیگ Xray-core با قابلیت مسیریابی سایت‌های ایرانی"""
    config = {
        "log": {
            "loglevel": "warning",
            "access": "/dev/null",
            "error": "/dev/null"
        },
        "inbounds": [{
            "listen": "0.0.0.0",
            "port": 443,
            "protocol": "vless",
            "settings": {
                "clients": [{
                    "id": uid,
                    "flow": "xtls-rprx-vision"
                }],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "show": False,
                    "dest": f"{FALLBACK_DEST}:{FALLBACK_PORT}",
                    "xver": 0,
                    "serverNames": [FALLBACK_DEST],
                    "privateKey": private_key,
                    "shortIds": [short_id]
                }
            }
        }],
        "outbounds": [
            {
                "protocol": "freedom",
                "tag": "direct",
                "settings": {
                    "domainStrategy": "UseIP"
                }
            },
            {
                "protocol": "blackhole",
                "tag": "block"
            }
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                {
                    # مسیر مستقیم برای سایت‌های ایرانی
                    "type": "field",
                    "domain": [f"domain:{site}" for site in IRAN_TOP_SITES],
                    "outboundTag": "direct"
                },
                {
                    # مسیر مستقیم برای IPهای ایران
                    "type": "field",
                    "ip": ["geoip:ir"],
                    "outboundTag": "direct"
                },
                {
                    # بلاک کردن ترافیک به پورت‌های مخرب
                    "type": "field",
                    "port": "135,137-139,445",
                    "outboundTag": "block"
                }
            ]
        }
    }
    
    with open(XRAY_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"[OK] Xray config written to {XRAY_CONFIG_FILE}")
    return config

def generate_vless_link(public_ip, uid, public_key, short_id):
    """تولید لینک VLESS قابل استفاده در کلاینت"""
    # قالب لینک VLESS:
    # vless://UUID@IP:PORT?type=tcp&security=reality&flow=xtls-rprx-vision
    # &fp=chrome&pbk=PUBLIC_KEY&sni=FALLBACK_DEST&sid=SHORT_ID#NAME
    
    name = f"GitHub-Actions-{public_ip}"
    params = {
        "type": "tcp",
        "security": "reality",
        "flow": "xtls-rprx-vision",
        "pbk": public_key,
        "sni": FALLBACK_DEST,
        "sid": short_id,
        "fp": "chrome",
        "spx": "/"
    }
    
    param_str = "&".join([f"{k}={v}" for k, v in params.items()])
    vless_link = f"vless://{uid}@{public_ip}:443?{param_str}#{name}"
    
    return vless_link

def generate_qr_code(vless_link):
    """تولید QR Code با کتابخانه qrencode"""
    # ذخیره لینک در فایل موقت
    with open("temp_link.txt", "w") as f:
        f.write(vless_link)
    
    # تولید QR code
    run_cmd(["qrencode", "-o", QR_OUTPUT_FILE, "-r", "temp_link.txt"])
    print(f"[OK] QR Code saved to {QR_OUTPUT_FILE}")

def main():
    print("="*50)
    print("VLESS Config Generator for GitHub Actions")
    print("="*50)
    
    # ۱. دریافت IP
    public_ip = get_public_ip()
    
    # ۲. دانلود Xray
    download_xray()
    
    # ۳. تولید کلیدها
    uid, private_key, public_key, short_id = generate_keys()
    
    # ۴. ایجاد کانفیگ Xray
    generate_xray_config(public_ip, uid, private_key, short_id)
    
    # ۵. اجرای موقت Xray برای تایید سلامت
    print("[*] Starting Xray for health check...")
    xray_process = subprocess.Popen([XRAY_BIN, "run", "-config", XRAY_CONFIG_FILE],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)  # انتظار برای شروع
    
    if xray_process.poll() is not None:
        print("[ERROR] Xray failed to start. Check configuration.")
        sys.exit(1)
    print("[OK] Xray started successfully")
    
    # ۶. توقف Xray (نیاز نیست همیشه روشن باشه)
    xray_process.terminate()
    xray_process.wait()
    print("[*] Xray stopped after health check")
    
    # ۷. تولید لینک VLESS
    vless_link = generate_vless_link(public_ip, uid, public_key, short_id)
    print("\n" + "="*50)
    print("VLESS CONFIG LINK:")
    print(vless_link)
    print("="*50 + "\n")
    
    # ۸. تولید QR Code
    generate_qr_code(vless_link)
    
    # ۹. ذخیره نهایی در فایل
    output_content = f"""VLESS Config - Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}
Server IP: {public_ip}
Port: 443
Protocol: VLESS + XTLS + Reality
Flow: xtls-rprx-vision
UUID: {uid}
Public Key: {public_key}
Short ID: {short_id}
SNI: {FALLBACK_DEST}
Fallback: {FALLBACK_DEST}:{FALLBACK_PORT}

VLESS Link:
{vless_link}

QR Code saved as: {QR_OUTPUT_FILE}

Routing Rules:
- Iranian top sites (25 sites) → Direct connection (no VPN)
- Iranian IP ranges (geoip:ir) → Direct connection
- Other traffic → Routed through VPN
"""
    
    with open(CONFIG_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output_content)
    
    print(f"[OK] Results saved to {CONFIG_OUTPUT_FILE}")
    print("[*] Done! Check the workflow artifacts for the config and QR code.")

if __name__ == "__main__":
    main()
