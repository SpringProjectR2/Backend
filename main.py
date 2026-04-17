import random
import threading
from datetime import datetime, timezone

from flask import Flask
from flask_socketio import SocketIO

from models import db
from auth import auth_bp
from flask_jwt_extended import JWTManager

from flask_jwt_extended import jwt_required, get_jwt_identity

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["JWT_SECRET_KEY"] = "super-secret-key"
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

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
            socketio.emit("sensor-data", payload)
        socketio.sleep(2)

@socketio.on("connect")
def handle_connect():
    global background_task_started
    print("Client connected")
    with background_task_lock:
        if not background_task_started:
            socketio.start_background_task(temperature_sensor_stream)
            background_task_started = True

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
