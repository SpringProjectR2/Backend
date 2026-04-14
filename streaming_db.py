from flask import Flask
from flask_socketio import SocketIO
from influxdb import InfluxDBClient
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# InfluxDB config
client = InfluxDBClient(host="localhost", port=8086)
client.switch_database("ruuvi")

def fetch_latest_temperature():
    query = """
        SELECT LAST("temperature")
        FROM "ruuvi"
    """
    result = client.query(query)
    points = list(result.get_points())

    if points:
        return {
            "time": points[0]["time"],
            "temperature": points[0]["last"]
        }
    return None

# Background thread to push updates
def stream_data():
    last_value = None

    while True:
        data = fetch_latest_temperature()

        # Only emit if value changed (avoid spam)
        if data and data != last_value:
            socketio.emit("temperature_update", data)
            last_value = data

        time.sleep(2)  # adjust frequency

@socketio.on("connect")
def handle_connect():
    print("Client connected")

if __name__ == "__main__":
    socketio.start_background_task(stream_data)
    socketio.run(app, host="0.0.0.0", port=5000)