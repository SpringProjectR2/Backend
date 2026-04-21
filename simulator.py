#!/usr/bin/env python3

import time
import random
import argparse
from influxdb import InfluxDBClient


# ---------------------------
# CONFIG / CLI
# ---------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="RuuviTag InfluxDB simulator")

    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8086)
    parser.add_argument("--db", default="ruuvi")

    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds between writes")

    parser.add_argument("--macs", nargs="+",
                        default=[
                            "AABBCCDDEE01",
                            "AABBCCDDEE02"
                        ],
                        help="List of simulated MAC addresses")

    parser.add_argument("--low-battery-mac", default=None,
                        help="MAC that will simulate draining battery")

    return parser.parse_args()


# ---------------------------
# STATE (per MAC)
# ---------------------------

def init_state(macs):
    return {
        mac: {
            "temp": random.uniform(18, 19),
            "temp_trend": random.choice([-0.08, 0.08]),

            "humidity": random.uniform(40, 60),
            "hum_trend": random.choice([-0.2, 0.2]),

            "battery": random.uniform(2.7, 3.0)
        }
        for mac in macs
    }


# ---------------------------
# SIMULATION HELPERS
# ---------------------------

def next_temp(mac, state):
    s = state[mac]

    s["temp"] += s["temp_trend"] + random.uniform(-0.05, 0.05)

    if random.random() < 0.1:
        s["temp_trend"] *= -1

    s["temp"] = max(15.0, min(30.0, s["temp"]))

    return round(s["temp"], 2)


def next_humidity(mac, state):
    s = state[mac]

    s["humidity"] += s["hum_trend"] + random.uniform(-0.5, 0.5)

    if random.random() < 0.1:
        s["hum_trend"] *= -1

    s["humidity"] = max(20.0, min(90.0, s["humidity"]))

    return round(s["humidity"], 2)


def next_battery(mac, state, low_battery_mac=None):
    s = state[mac]

    # Simulate draining battery for selected MAC
    if low_battery_mac and mac == low_battery_mac:
        # gradual drain
        s["battery"] -= random.uniform(0.01, 0.03)

    else:
        # stable battery with tiny noise
        s["battery"] += random.uniform(-0.005, 0.005)

    # clamp realistic range
    s["battery"] = max(1.0, min(3.2, s["battery"]))

    return round(s["battery"], 3)


# ---------------------------
# MAIN LOOP
# ---------------------------

def run():
    args = parse_args()

    client = InfluxDBClient(host=args.host, port=args.port)
    client.switch_database(args.db)

    state = init_state(args.macs)

    print("Ruuvi simulator started")
    print(f"Target DB: {args.host}:{args.port}/{args.db}")
    print(f"MACs: {', '.join(args.macs)}")
    print(f"Interval: {args.interval}s")

    if args.low_battery_mac:
        print(f"Battery drain enabled for: {args.low_battery_mac}")

    print("-" * 40)

    while True:
        points = []

        for mac in args.macs:
            temp = next_temp(mac, state)
            humidity = next_humidity(mac, state)
            battery = next_battery(mac, state, args.low_battery_mac)

            point = {
                "measurement": "ruuvi_measurements",
                "tags": {
                    "mac": mac,
                    "dataFormat": "5"
                },
                "fields": {
                    "temperature": temp,
                    "humidity": humidity,
                    "batteryVoltage": battery
                }
            }

            points.append(point)

            print(
                f"{mac} -> "
                f"{temp:.2f} °C | "
                f"{humidity:.2f} % | "
                f"{battery:.3f} V"
            )

        try:
            client.write_points(points)
        except Exception as e:
            print("Write error:", e)

        time.sleep(args.interval)


# ---------------------------
# ENTRY
# ---------------------------

if __name__ == "__main__":
    run()