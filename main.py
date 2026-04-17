import random
import threading
from datetime import datetime, timezone, timedelta

from flask import Flask
from flask_socketio import SocketIO, join_room

from models import db
from auth import auth_bp

from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    get_jwt_identity,
    decode_token,
)

app = Flask(__name__)

app.config["SECRET_KEY"] = "secret!"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["JWT_SECRET_KEY"] = "super-secret-key"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

db.init_app(app)
jwt = JWTManager(app)

app.register_blueprint(auth_bp)

background_task_started = False
background_task_lock = threading.Lock()


@app.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    return {"user_id": user_id}


def temperature_sensor_stream():
    while True:
        timestamp = datetime.now(timezone.utc).isoformat()

        for label in ("Sensor1", "Sensor2"):
            payload = {
                "label": label,
                "timestamp": timestamp,
                "value": round(random.uniform(20.0, 32.0), 2),
            }

            socketio.emit("sensor-data", payload, room="authenticated")

        socketio.sleep(2)


@socketio.on("connect")
def handle_connect(auth):
    global background_task_started

    print("🔌 SOCKET CONNECT AUTH RAW:", auth)

    if not auth or "token" not in auth:
        print("❌ Missing token → reject")
        return False

    token = auth["token"]

    print("🔑 TOKEN RECEIVED:", token)

    if not isinstance(token, str) or token.count(".") != 2:
        print("❌ Token is not valid JWT format")
        return False

    try:
        decoded = decode_token(token)
        user_id = decoded["sub"]

        print(f"✅ AUTH SUCCESS user_id={user_id}")

        join_room("authenticated")

    except Exception as e:
        print(f"❌ JWT DECODE FAILED: {e}")
        return False

    with background_task_lock:
        if not background_task_started:
            socketio.start_background_task(temperature_sensor_stream)
            background_task_started = True


@socketio.on("disconnect")
def handle_disconnect():
    print("❌ Client disconnected")


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)