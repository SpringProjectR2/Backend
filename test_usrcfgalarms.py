import requests
import socketio
import time

BASE_URL = "http://10.137.17.253:5000"

USERNAME = "testuser2"
PASSWORD = "testpass456"


# ---------------------------
# SAFE JSON HELPER
# ---------------------------

def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------
# 1. REGISTER (ignore if exists)
# ---------------------------
print("\n🔐 Registering user...")

r = requests.post(
    f"{BASE_URL}/register",
    json={"username": USERNAME, "password": PASSWORD}
)

print("Status:", r.status_code, safe_json(r))


# ---------------------------
# 2. LOGIN
# ---------------------------
print("\n🔑 Logging in...")

r = requests.post(
    f"{BASE_URL}/login",
    json={"username": USERNAME, "password": PASSWORD}
)

data = safe_json(r)
token = data.get("access_token")

print("Status:", r.status_code)
print("Token received:", bool(token))

if not token:
    print("❌ Login failed")
    exit()

headers = {"Authorization": f"Bearer {token}"}


# ---------------------------
# 3. GET ALARM CONFIG
# ---------------------------
print("\n⚙️ Getting alarm config...")

r = requests.get(
    f"{BASE_URL}/alarm-config",
    headers=headers
)

print("Status:", r.status_code)
config = safe_json(r)
print("Config:", config)


# ---------------------------
# 4. UPDATE ALARM CONFIG (TEST VALUES)
# ---------------------------
print("\n⚙️ Updating alarm config...")

r = requests.post(
    f"{BASE_URL}/alarm-config",
    json={
        "battery_threshold": 1.6,
        "temp_threshold": 22.0,
        "battery_cooldown": 30,
        "temp_cooldown": 30
    },
    headers=headers
)

print("Status:", r.status_code)
print("Updated:", safe_json(r))


# ---------------------------
# 5. GET MACS
# ---------------------------
print("\n📡 Fetching MAC list...")

r = requests.get(
    f"{BASE_URL}/macs",
    headers=headers
)

macs = safe_json(r)

print("Status:", r.status_code)
print("MACs:", macs)

if not isinstance(macs, list):
    macs = []

if len(macs) == 0:
    print("⚠️ No MACs available (skipping history test)")


# ---------------------------
# 6. HISTORY TEST
# ---------------------------
if macs:
    test_mac = macs[0]

    print(f"\n📊 Fetching history for {test_mac}...")

    r = requests.get(
        f"{BASE_URL}/history/{test_mac}",
        params={"hours": 2, "limit": 10},
        headers=headers
    )

    print("Status:", r.status_code)
    history = safe_json(r)

    if isinstance(history, list):
        for item in history:
            print(
                f"{item.get('time')} | "
                f"T:{item.get('temperature')} | "
                f"H:{item.get('humidity')} | "
                f"B:{item.get('battery')}"
            )
    else:
        print("History response:", history)


# ---------------------------
# 7. SOCKET.IO TEST
# ---------------------------
print("\n🔌 Connecting to Socket.IO...")

sio = socketio.Client()


@sio.event
def connect():
    print("✅ Socket connected")


@sio.event
def disconnect():
    print("❌ Socket disconnected")


@sio.on("sensor_update")
def sensor(data):
    print("📡 SENSOR UPDATE:", data)


@sio.on("battery_low")
def battery(data):
    print("\n🔋 BATTERY LOW:", data)


@sio.on("temp_high")
def temp(data):
    print("\n🌡️ TEMP HIGH:", data)


# ---------------------------
# CONNECT
# ---------------------------
print("Connecting with JWT...")

sio.connect(
    BASE_URL,
    auth={"token": token}
)


# ---------------------------
# LISTEN LOOP
# ---------------------------
print("\n👂 Listening for realtime updates...\n")

while True:
    time.sleep(1)