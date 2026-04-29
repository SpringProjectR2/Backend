import requests
import socketio
import time

BASE_URL = "http://10.137.17.253:5000"

USERNAME = "testuser_auto"
PASSWORD = "testpass123"


def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def print_section(title):
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)


# ---------------------------
# REGISTER
# ---------------------------
print_section("REGISTER USER")

r = requests.post(
    f"{BASE_URL}/register",
    json={"username": USERNAME, "password": PASSWORD}
)

print("Status:", r.status_code)
print("Response:", safe_json(r))


# ---------------------------
# LOGIN
# ---------------------------
print_section("LOGIN")

r = requests.post(
    f"{BASE_URL}/login",
    json={"username": USERNAME, "password": PASSWORD}
)

data = safe_json(r)
token = data.get("access_token")

print("Status:", r.status_code)
print("Response:", data)

if not token:
    print("Login failed, exiting")
    exit()


headers = {"Authorization": f"Bearer {token}"}


# ---------------------------
# GET MAC LIST
# ---------------------------
print_section("GET MAC LIST")

r = requests.get(f"{BASE_URL}/macs", headers=headers)

macs = safe_json(r)

print("Status:", r.status_code)
print("MACs:", macs)

if not isinstance(macs, list) or not macs:
    print("No MACs available, skipping history test")
    selected_mac = None
else:
    selected_mac = macs[0]


# ---------------------------
# GET HISTORY
# ---------------------------
if selected_mac:
    print_section(f"GET HISTORY FOR {selected_mac}")

    r = requests.get(
        f"{BASE_URL}/history/{selected_mac}",
        headers=headers,
        params={"hours": 1, "limit": 10}
    )

    history = safe_json(r)

    print("Status:", r.status_code)
    print("History sample (first 3 rows):")
    for row in history[:3]:
        print(row)


# ---------------------------
# SOCKET.IO CLIENT
# ---------------------------
print_section("SOCKET TEST")

sio = socketio.Client(logger=False, engineio_logger=False)


# ---- SENSOR DATA ----
@sio.event(namespace="/sensor-data")
def connect():
    print("Connected to /sensor-data")


@sio.event(namespace="/sensor-data")
def disconnect():
    print("Disconnected from /sensor-data")


@sio.on("sensor_update", namespace="/sensor-data")
def on_sensor(data):
    print("SENSOR UPDATE:", data)


# ---- SENSOR ALARM ----
@sio.event(namespace="/sensor-alarm")
def connect_alarm():
    print("Connected to /sensor-alarm")


@sio.event(namespace="/sensor-alarm")
def disconnect_alarm():
    print("Disconnected from /sensor-alarm")


@sio.on("battery_low", namespace="/sensor-alarm")
def on_battery(data):
    print("BATTERY LOW:", data)


@sio.on("temp_high", namespace="/sensor-alarm")
def on_temp(data):
    print("TEMP HIGH:", data)


# ---------------------------
# CONNECT
# ---------------------------
print("Connecting to Socket.IO namespaces")

try:
    sio.connect(
        BASE_URL,
        auth={"token": token},
        namespaces=["/sensor-data", "/sensor-alarm"],
        wait_timeout=10
    )
except Exception as e:
    print("Connection failed:", e)
    exit()

print("Listening for events")


# ---------------------------
# LOOP
# ---------------------------
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down client")
    sio.disconnect()