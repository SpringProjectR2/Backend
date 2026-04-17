from flask import Flask, jsonify, request
from flask_socketio import SocketIO, join_room
from influxdb import InfluxDBClient
import time
from collections import defaultdict

# NEW: auth + db
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

# JWT + DB config
app.config["SECRET_KEY"] = "secret!"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["JWT_SECRET_KEY"] = "super-secret-key"

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Influx
client = InfluxDBClient(host="localhost", port=8086)
client.switch_database("ruuvi")


# ---------------------------
# USER MODEL
# ---------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)


# ---------------------------
# AUTH ROUTES
# ---------------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return {"error": "username and password required"}, 400

    if len(password) < 6:
        return {"error": "password too short"}, 400

    if User.query.filter_by(username=username).first():
        return {"error": "user exists"}, 400

    user = User(
        username=username,
        password_hash=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.commit()

    return {"msg": "user created"}, 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}

    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password_hash, password):
        return {"error": "wrong credentials"}, 401

    token = create_access_token(identity=str(user.id))
    return {"access_token": token}, 200


@app.route("/me")
@jwt_required()
def me():
    return {"user_id": get_jwt_identity()}


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
# HISTORY API (PROTECTED)
# ---------------------------

@app.route("/macs")
@jwt_required()
def get_macs():
    hours = request.args.get("hours", default=48, type=int)
    return jsonify(list(query_active_macs(hours)))


@app.route("/history/<mac>")
@jwt_required()
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
last_values = {}


# ---------------------------
# ALARM HELPERS
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
# MONITOR LOOP
# ---------------------------

def monitor_loop():
    print("MONITOR STARTED")

    while True:
        try:
            macs = query_active_macs()

            for mac in macs:

                # STREAM
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
                        }, room="authenticated")

                        last_values[mac] = temp

                # ALARM
                alarm = check_mac(mac)

                if alarm and not alarm_state[mac]:
                    socketio.emit("alarm_start", {
                        "mac": mac,
                        "threshold": ALARM_THRESHOLD
                    }, room="authenticated")

                    alarm_state[mac] = True

                elif not alarm and alarm_state[mac]:
                    socketio.emit("alarm_end", {
                        "mac": mac
                    }, room="authenticated")

                    alarm_state[mac] = False

        except Exception as e:
            print("MONITOR ERROR:", e)

        time.sleep(CHECK_INTERVAL)


# ---------------------------
# SOCKET AUTH
# ---------------------------

@socketio.on("connect")
def on_connect(auth=None):
    print("Socket connect attempt")

    if not auth or "token" not in auth:
        print("Missing token")
        return False

    token = auth["token"]

    try:
        decoded = decode_token(token)
        user_id = decoded["sub"]

        print(f"Authenticated user: {user_id}")
        join_room("authenticated")

    except Exception as e:
        print("JWT error:", e)
        return False


@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected")


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
        use_reloader=False
    )