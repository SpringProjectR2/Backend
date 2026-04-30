from flask import Flask, jsonify, request
from flask_socketio import SocketIO, join_room
from influxdb import InfluxDBClient
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    create_access_token,
    get_jwt_identity,
    decode_token
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------
# APP SETUP
# ---------------------------

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

app.config["SECRET_KEY"] = "secret!"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["JWT_SECRET_KEY"] = "super-secret-key"

db = SQLAlchemy(app)
jwt = JWTManager(app)

client = InfluxDBClient(host="localhost", port=8086)
client.switch_database("ruuvi")

#----
#TIMESTAMP HELPER
#----

def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------
# MODELS
# ---------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)


class AlarmConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, unique=True)

    battery_threshold = db.Column(db.Float, default=1.5)
    battery_cooldown = db.Column(db.Integer, default=86400)

    temp_threshold = db.Column(db.Float, default=25.0)
    temp_cooldown = db.Column(db.Integer, default=3600)


# ---------------------------
# AUTH
# ---------------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return {"error": "missing"}, 400

    if User.query.filter_by(username=username).first():
        return {"error": "exists"}, 400

    user = User(
        username=username,
        password_hash=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.commit()

    config = AlarmConfig(user_id=user.id)
    db.session.add(config)
    db.session.commit()

    return {"msg": "created"}, 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}

    user = User.query.filter_by(username=data.get("username")).first()

    if not user or not check_password_hash(user.password_hash, data.get("password")):
        return {"error": "bad creds"}, 401

    token = create_access_token(identity=str(user.id))
    return {"access_token": token}


# ---------------------------
# ALARM CONFIG API
# ---------------------------

@app.route("/alarm-config", methods=["GET"])
@jwt_required()
def get_alarm_config():
    user_id = int(get_jwt_identity())

    config = AlarmConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return {"error": "no config"}, 404

    return jsonify({
        "battery_threshold": config.battery_threshold,
        "battery_cooldown": config.battery_cooldown,
        "temp_threshold": config.temp_threshold,
        "temp_cooldown": config.temp_cooldown
    })


@app.route("/alarm-config", methods=["POST"])
@jwt_required()
def update_alarm_config():
    user_id = int(get_jwt_identity())

    config = AlarmConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return {"error": "no config"}, 404

    data = request.json or {}

    if "battery_threshold" in data:
        config.battery_threshold = float(data["battery_threshold"])

    if "battery_cooldown" in data:
        config.battery_cooldown = int(data["battery_cooldown"])

    if "temp_threshold" in data:
        config.temp_threshold = float(data["temp_threshold"])

    if "temp_cooldown" in data:
        config.temp_cooldown = int(data["temp_cooldown"])

    db.session.commit()

    return {"msg": "updated"}


# ---------------------------
# INFLUX QUERY
# ---------------------------

def get_latest_all():
    query = """
        SELECT LAST("temperature") as temperature,
               LAST("humidity") as humidity,
               LAST("batteryVoltage") as battery
        FROM "ruuvi_measurements"
        WHERE "dataFormat" = '5'
        GROUP BY "mac"
    """

    result = client.query(query)
    data = {}

    for (measurement, tags), points in result.items():
        mac = tags.get("mac")

        pts = list(points)
        if not pts:
            continue

        p = pts[0]

        data[mac] = {
            "temperature": p.get("temperature"),
            "humidity": p.get("humidity"),
            "battery": p.get("battery")
        }

    return data


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
    for (measurement, tags), _ in result.items():
        mac = tags.get("mac")
        if mac:
            macs.add(mac)

    return list(macs)


# ---------------------------
# HISTORY API
# ---------------------------

@app.route("/macs", methods=["GET"])
@jwt_required()
def get_macs():
    return jsonify(query_active_macs())

@app.route("/history/<mac>", methods=["GET"])
@jwt_required()
def get_history(mac):

    start = request.args.get("start")  # ISO string
    end = request.args.get("end")      # ISO string
    limit = request.args.get("limit", default=1000000, type=int)

    # ---------------------------
    # BACKWARD COMPATIBILITY
    # ---------------------------
    if not start:
        hours = request.args.get("hours", type=int)

        if hours:
            start = (
                datetime.now(timezone.utc) - timedelta(hours=hours)
            ).isoformat()
        else:
            return {"error": "start or hours required"}, 400

    # ---------------------------
    # BUILD TIME FILTER
    # ---------------------------
    time_filter = f"time >= '{start}'"

    if end:
        time_filter += f" AND time <= '{end}'"

    # ---------------------------
    # INFLUX QUERY
    # ---------------------------
    query = f"""
        SELECT "temperature", "humidity", "batteryVoltage"
        FROM "ruuvi_measurements"
        WHERE {time_filter}
        AND "mac" = '{mac}'
        AND "dataFormat" = '5'
        ORDER BY time ASC
        LIMIT {limit}
    """

    result = client.query(query)
    points = []
    for (_, _), series in result.items():
        points.extend(series)

    # ---------------------------
    # NORMALIZE TIMESTAMPS
    # ---------------------------
    return jsonify([
    {
        "time": datetime.fromisoformat(
            p.get("time").replace("Z", "+00:00")
        ).isoformat(),
        "temperature": p.get("temperature"),
        "humidity": p.get("humidity"),
        "battery": p.get("batteryVoltage")
    }
    for p in points
    ])

# ---------------------------
# SOCKET AUTH (NAMESPACES)
# ---------------------------

connected_users = {}

@socketio.on("connect", namespace="/sensor-data")
def connect_sensor_data(auth):
    if not auth or "token" not in auth:
        return False

    try:
        decoded = decode_token(auth["token"])
        user_id = int(decoded["sub"])
        connected_users[request.sid] = user_id
        print(f"Sensor-data connected: user {user_id}")
    except Exception:
        return False


@socketio.on("connect", namespace="/sensor-alarm")
def connect_sensor_alarm(auth):
    if not auth or "token" not in auth:
        return False

    try:
        decoded = decode_token(auth["token"])
        user_id = int(decoded["sub"])

        connected_users[request.sid] = user_id
        join_room(f"user:{user_id}", namespace="/sensor-alarm")

        print(f"Sensor-alarm connected: user {user_id}")

    except Exception:
        return False


@socketio.on("disconnect", namespace="/sensor-data")
def disconnect_sensor_data():
    connected_users.pop(request.sid, None)


@socketio.on("disconnect", namespace="/sensor-alarm")
def disconnect_sensor_alarm():
    connected_users.pop(request.sid, None)


# ---------------------------
# ALARM STATE
# ---------------------------

history = defaultdict(list)
last_sent = {}

CONSECUTIVE = 3


def check_alarm(user_id, mac, value, threshold, cooldown, alarm_type):
    if value is None:
        return False

    key = (user_id, mac, alarm_type)

    h = history[key]
    h.append(value)

    if len(h) > CONSECUTIVE:
        h.pop(0)

    if len(h) < CONSECUTIVE:
        return False

    if alarm_type == "battery":
        valid = all(v < threshold for v in h)
    else:
        valid = all(v > threshold for v in h)

    if not valid:
        return False

    now = time.time()
    if now - last_sent.get(key, 0) < cooldown:
        return False

    last_sent[key] = now
    return True




# ---------------------------
# MONITOR LOOP
# ---------------------------

CHECK_INTERVAL = 5
last_values = {}


def monitor_loop():
    print("MONITOR STARTED")

    with app.app_context():

        while True:
            try:
                data = get_latest_all()
                users = AlarmConfig.query.all()

                for mac, current in data.items():

                    # sensor stream → /sensor-data
                    if last_values.get(mac) != current:
                        socketio.emit(
                            "sensor_update",
                            {"mac": mac, **current, "time": now_iso()},
                            namespace="/sensor-data"
                        )
                        last_values[mac] = current

                    # alarms → /sensor-alarm
                    for cfg in users:
                        uid = cfg.user_id

                        if check_alarm(uid, mac,
                                       current["battery"],
                                       cfg.battery_threshold,
                                       cfg.battery_cooldown,
                                       "battery"):

                            socketio.emit(
                                "battery_low",
                                {
                                    "mac": mac,
                                    "battery": current["battery"]
                                },
                                room=f"user:{uid}",
                                namespace="/sensor-alarm"
                            )

                        if check_alarm(uid, mac,
                                       current["temperature"],
                                       cfg.temp_threshold,
                                       cfg.temp_cooldown,
                                       "temp"):

                            socketio.emit(
                                "temp_high",
                                {
                                    "mac": mac,
                                    "temperature": current["temperature"]
                                },
                                room=f"user:{uid}",
                                namespace="/sensor-alarm"
                            )

            except Exception as e:
                print("MONITOR ERROR:", e)

            time.sleep(CHECK_INTERVAL)


# ---------------------------
# STARTUP
# ---------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.start_background_task(monitor_loop)

    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
