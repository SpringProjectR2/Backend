import requests
import socketio
import time

BASE_URL = "http://10.137.17.253:5000"

USERNAME = "testuser"
PASSWORD = "testpass123"


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
# 3. TEST PROTECTED REST API
# ---------------------------
print("\n📡 Testing /macs (protected endpoint)...")

r = requests.get(
    f"{BASE_URL}/macs",
    headers={
        "Authorization": f"Bearer {token}"
    }
)

print("Status:", r.status_code)
print(r.json())


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


@sio.on("temperature_update")
def on_temp(data):
    print("🌡️ Temp update:", data)


@sio.on("alarm_start")
def on_alarm_start(data):
    print("🚨 ALARM START:", data)


@sio.on("alarm_end")
def on_alarm_end(data):
    print("🟢 ALARM END:", data)


print("Connecting with JWT...")

sio.connect(
    BASE_URL,
    auth={
        "token": token
    }
)


# keep alive
while True:
    time.sleep(1)