#!/usr/bin/env python3
import os
import json
import time
import uuid
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests
from qrcode_terminal import draw

# ─────────────────────────────────────────────────────
# 1. Get the workflow runner’s public IP
# ─────────────────────────────────────────────────────
try:
    resp = requests.get("https://api.ipify.org?format=json", timeout=10)
    PUBLIC_IP = resp.json()["ip"]
except Exception:
    # fallback
    PUBLIC_IP = subprocess.check_output(
        "curl -s ifconfig.me", shell=True
    ).decode().strip()

print(f"🌍 Detected public IP: {PUBLIC_IP}")

# ─────────────────────────────────────────────────────
# 2. Prepare Xray (download if missing)
# ─────────────────────────────────────────────────────
XRAY_ZIP = "Xray-linux-64.zip"
XRAY_BIN = "./xray"
if not os.path.exists(XRAY_BIN):
    print("⬇️ Downloading Xray core ...")
    url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
    r = requests.get(url, allow_redirects=True)
    with open(XRAY_ZIP, "wb") as f:
        f.write(r.content)
    os.system(f"unzip -o {XRAY_ZIP} && chmod +x xray")
    os.remove(XRAY_ZIP)

# ─────────────────────────────────────────────────────
# 3. Generate a random port and UUID + expiry (6 h from now)
# ─────────────────────────────────────────────────────
PORT = random.randint(10000, 60000)
USER_UUID = str(uuid.uuid4())
EXPIRE_UTC = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

# ─────────────────────────────────────────────────────
# 4. Create Xray server config (VLESS over TCP)
# ─────────────────────────────────────────────────────
config = {
    "log": {"loglevel": "warning"},
    "inbounds": [
        {
            "port": PORT,
            "protocol": "vless",
            "settings": {
                "clients": [
                    {
                        "id": USER_UUID,
                        "level": 0,
                        "email": "gh-user",
                        "expiry": EXPIRE_UTC,
                    }
                ],
                "decryption": "none",
            },
            "streamSettings": {"network": "tcp"},
        }
    ],
    "outbounds": [{"protocol": "freedom"}],
}

with open("config.json", "w") as f:
    json.dump(config, f, indent=2)

print(f"✅ Config written – port {PORT}, expiry {EXPIRE_UTC}")

# ─────────────────────────────────────────────────────
# 5. Start Xray in the background
# ─────────────────────────────────────────────────────
proc = subprocess.Popen([XRAY_BIN, "run", "-c", "config.json"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
print(f"🚀 Xray started (PID {proc.pid})")

# Wait a second to ensure it's listening
time.sleep(2)

# ─────────────────────────────────────────────────────
# 6. Build the VLESS client link and print QR code
# ─────────────────────────────────────────────────────
vless_link = f"vless://{USER_UUID}@{PUBLIC_IP}:{PORT}?encryption=none&security=none&type=tcp#{PUBLIC_IP}"

print("\n" + "=" * 50)
print("🔗 VLESS config (valid 6 hours):")
print(vless_link)
print("=" * 50 + "\n")

print("📱 Scan this QR code in your v2ray client:")
draw(vless_link)

# ─────────────────────────────────────────────────────
# 7. (Optional) Print a client‑side routing snippet
#    that sends top Iranian sites directly,
#    making the tunnel less suspicious.
# ─────────────────────────────────────────────────────
IRANIAN_DOMAINS = [
    "aparat.com","varzesh3.com","digikala.com","namnak.com",
    "beytoote.com","niniban.com","telewebion.com","filimo.com",
    "snapp.ir","tapsi.ir","divar.ir","sheypoor.com",
    "isna.ir","irna.ir","tabnak.ir","khabaronline.ir",
    "yjc.ir","mehrnews.com","farsnews.ir","tasnimnews.com",
    "eghtesadnews.com","asarayan.com","bartarinha.ir",
    "delgarm.com","akharinkhabar.ir"
]

print("\n🧩 Suggested routing config for your client (V2RayN / Nekoray etc.):")
print("Add the following domains as 'direct' outbound so that only")
print("international traffic goes through the VPN.")
print("-" * 30)
print("domainStrategy: AsIs")
for d in IRANIAN_DOMAINS:
    print(f"domain: {d} -> direct")
print("-" * 30)

# ─────────────────────────────────────────────────────
# 8. Keep the workflow alive for 6 hours + dummy traffic
#    (download/upload activity prevents idle‑kill)
# ─────────────────────────────────────────────────────
def generate_traffic():
    """Small download to simulate active usage."""
    try:
        # Download a small file (approx 1 MB)
        r = requests.get("https://speed.hetzner.de/1MB.bin", timeout=15)
        print(f"⬇️ Traffic: received {len(r.content)} bytes")
    except Exception:
        print("⚠️ Traffic fetch failed (non‑critical)")

    # Fake "upload" via a POST request (tiny payload)
    try:
        r = requests.post("https://httpbin.org/post", data=b"A"*512, timeout=10)
        print(f"⬆️ Upload test: {r.status_code}")
    except Exception:
        pass

print("\n⏳ Running for 6 hours – do NOT close this tab...\n")

DEADLINE = time.time() + 6 * 3600
while time.time() < DEADLINE:
    generate_traffic()
    time.sleep(120)   # every 2 minutes

# Clean exit – the workflow will stop on its own.
print("⏰ 6‑hour window ended. Config expired. Workflow will now stop.")