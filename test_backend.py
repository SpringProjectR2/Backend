import requests
import socketio
import time

BASE_URL = "http://10.137.17.253:5000"

USERNAME = "testuser2"
PASSWORD = "testpass456"


# ---------------------------
# 1. REGISTER
# ---------------------------
print("\n🔐 Registering user...")

r = requests.post(
    f"{BASE_URL}/register",
    json={
        "username": USERNAME,
        "password": PASSWORD
    }
)

print("Status:", r.status_code)
print(r.json())


# ---------------------------
# 2. LOGIN
# ---------------------------
print("\n🔑 Logging in...")

r = requests.post(
    f"{BASE_URL}/login",
    json={
        "username": USERNAME,
        "password": PASSWORD
    }
)

print("Status:", r.status_code)
data = r.json()
print(data)

token = data.get("access_token")

if not token:
    print("❌ No token received")
    exit()


# ---------------------------
# 3. TEST /macs
# ---------------------------
print("\n📡 Testing /macs...")

r = requests.get(
    f"{BASE_URL}/macs",
    headers={"Authorization": f"Bearer {token}"}
)

print("Status:", r.status_code)
macs = r.json()
print(macs)


# ---------------------------
# 3.5 TEST HISTORY (NEW)
# ---------------------------
if macs:
    test_mac = macs[0]  # pick first available device

    print(f"\n📊 Testing /history for MAC: {test_mac}")

    r = requests.get(
        f"{BASE_URL}/history/{test_mac}",
        params={
            "hours": 48,
            "limit": 15
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    print("Status:", r.status_code)

    if r.status_code == 200:
        data = r.json()

        print("\nReceived history:\n")

        for item in data:
            print(
                f"Time: {item['time']}, "
                f"Temp: {item.get('temperature')}, "
                f"Humidity: {item.get('humidity')}, "
                f"Battery: {item.get('battery')}"
            )
    else:
        print("Error:", r.text)
else:
    print("⚠️ No MACs found, skipping history test")


# ---------------------------
# 4. SOCKET.IO TEST
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
def on_sensor(data):
    print("📡 Sensor update:", data)


@sio.on("alarm_start")
def on_alarm_start(data):
    print("🚨 ALARM START:", data)


@sio.on("alarm_end")
def on_alarm_end(data):
    print("🟢 ALARM END:", data)


print("Connecting with JWT...")

sio.connect(
    BASE_URL,
    auth={"token": token}
)


# keep alive
while True:
    time.sleep(1)