from flask import Flask, jsonify, request
from influxdb import InfluxDBClient

app = Flask(__name__)

client = InfluxDBClient(host="localhost", port=8086)
client.switch_database("ruuvi")


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

@app.route("/history/<mac>")
def get_history(mac):
    hours = request.args.get("hours", default=24, type=int)
    limit = request.args.get("limit", default=100, type=int)

    active_macs = query_active_macs(hours)

    if mac not in active_macs:
        return jsonify({"error": "Unknown or inactive sensor"}), 404

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

    data = [
        {"time": p["time"], "temperature": p.get("temperature")}
        for p in points
    ]

    return jsonify(data)

@app.route("/macs")
def get_macs():
    hours = request.args.get("hours", default=48, type=int)
    macs = query_active_macs(hours)
    return jsonify(list(macs))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)