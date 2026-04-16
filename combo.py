from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from influxdb import InfluxDBClient
import time
from collections import defaultdict

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

client = InfluxDBClient(host="localhost", port=8086)
client.switch_database("ruuvi")


# ---------------------------
# MAC DISCOVERY
# ---------------------------

def query_active_macs(hours=48):
    query = f"""
        SELECT LAST("temperature")
        FROM "ruuvi_measurements"
        WHERE time > now() - {hours}h
        AND "dataFormat" = '5'
        GROUP BY "mac"
    """

    result = client.query(query)

    macs = set()
    for (measurement, tags), points in result.items():
        mac = tags.get("mac")
        if mac:
            macs.add(mac)

    return macs


# ---------------------------
# HISTORY API
# ---------------------------

@app.route("/macs")
def get_macs():
    hours = request.args.get("hours", default=48, type=int)
    return jsonify(list(query_active_macs(hours)))


@app.route("/history/<mac>")
def get_history(mac):
    hours = request.args.get("hours", default=24, type=int)
    limit = request.args.get("limit", default=100, type=int)

    query = f"""
        SELECT "temperature"
        FROM "ruuvi_measurements"
        WHERE time > now() - {hours}h
        AND "mac" = '{mac}'
        AND "dataFormat" = '5'
        ORDER BY time DESC
        LIMIT {limit}
    """

    result = client.query(query)
    points = list(result.get_points())

    return jsonify([
        {"time": p["time"], "temperature": p.get("temperature")}
        for p in points
    ])


# ---------------------------
# MONITOR STATE
# ---------------------------

ALARM_THRESHOLD = 20.0
CHECK_INTERVAL = 5

alarm_state = defaultdict(bool)
last_values = {}   # per MAC caching for streaming


# ---------------------------
# FETCH LAST 5 FOR ALARM
# ---------------------------

def get_last_5_temps(mac):
    query = f"""
        SELECT "temperature"
        FROM "ruuvi_measurements"
        WHERE "mac" = '{mac}'
        AND "dataFormat" = '5'
        ORDER BY time DESC
        LIMIT 5
    """

    result = client.query(query)
    points = list(result.get_points())

    return [float(p["temperature"]) for p in points if p["temperature"] is not None]


def check_mac(mac):
    temps = get_last_5_temps(mac)

    if len(temps) < 5:
        return False

    return all(t > ALARM_THRESHOLD for t in temps)


# ---------------------------
# SINGLE MONITOR LOOP (IMPORTANT)
# ---------------------------

def monitor_loop():
    print("MONITOR STARTED")

    while True:
        try:
            macs = query_active_macs()

            for mac in macs:

                # -------------------
                # STREAMING UPDATE
                # -------------------
                query = f"""
                    SELECT LAST("temperature")
                    FROM "ruuvi_measurements"
                    WHERE "mac" = '{mac}'
                """

                result = client.query(query)
                points = list(result.get_points())

                if points:
                    temp = points[0]["last"]

                    if last_values.get(mac) != temp:
                        socketio.emit("temperature_update", {
                            "mac": mac,
                            "temperature": temp,
                            "time": points[0]["time"]
                        })
                        last_values[mac] = temp


                # -------------------
                # ALARM LOGIC
                # -------------------
                alarm = check_mac(mac)

                if alarm and not alarm_state[mac]:
                    print("ALARM START:", mac)

                    socketio.emit("alarm_start", {
                        "mac": mac,
                        "threshold": ALARM_THRESHOLD
                    })

                    alarm_state[mac] = True

                elif not alarm and alarm_state[mac]:
                    print("ALARM END:", mac)

                    socketio.emit("alarm_end", {
                        "mac": mac
                    })

                    alarm_state[mac] = False

        except Exception as e:
            print("MONITOR ERROR:", e)

        time.sleep(CHECK_INTERVAL)


# ---------------------------
# SOCKET EVENTS
# ---------------------------

@socketio.on("connect")
def on_connect(auth=None):
    print("Client connected")


# ---------------------------
# STARTUP
# ---------------------------

if __name__ == "__main__":
    socketio.start_background_task(monitor_loop)

    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )