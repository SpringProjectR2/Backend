import random
import threading
from datetime import datetime, timezone

from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

background_task_started = False
background_task_lock = threading.Lock()

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
