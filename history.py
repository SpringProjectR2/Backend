from flask import Flask, jsonify, request
from influxdb import InfluxDBClient

app = Flask(__name__)

client = InfluxDBClient(host="localhost", port=8086)
client.switch_database("ruuvi")

# Map friendly names → MAC addresses
SENSORS = {
    "ruuvitag": "C606A8B37ECC"
}

@app.route("/history/<sensor>")
def get_history(sensor):
    if sensor not in SENSORS:
        return jsonify({"error": "Unknown sensor"}), 404

    mac = SENSORS[sensor]

    # Optional query params
    hours = request.args.get("hours", default=24, type=int)
    limit = request.args.get("limit", default=100, type=int)

    query = f"""
        SELECT "temperature"
        FROM "ruuvi_measurements"
        WHERE time > now() - {hours}h
        AND "mac" = '{mac}'
        ORDER BY time DESC
        LIMIT {limit}
    """

    result = client.query(query)
    points = list(result.get_points())

    data = [
        {
            "time": p["time"],
            "temperature": p.get("temperature")
        }
        for p in points
    ]

    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
