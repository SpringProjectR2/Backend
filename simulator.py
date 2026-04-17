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

    parser.add_argument("--alarm-mac", default=None,
                        help="MAC that will intentionally exceed alarm threshold")

    return parser.parse_args()


# ---------------------------
# STATE (per MAC)
# ---------------------------

def init_state(macs):
    return {
        mac: {
            "temp": random.uniform(18, 19),
            "trend": random.choice([-0.08, 0.08])
        }
        for mac in macs
    }


def next_temp(mac, state, forced_alarm_mac=None):
    # Force alarm behavior if specified
    if forced_alarm_mac and mac == forced_alarm_mac:
        return round(random.uniform(21.0, 25.0), 2)

    s = state[mac]

    # Smooth drift
    s["temp"] += s["trend"] + random.uniform(-0.05, 0.05)

    # Occasionally flip direction
    if random.random() < 0.1:
        s["trend"] *= -1

    # Clamp realistic range
    s["temp"] = max(15.0, min(30.0, s["temp"]))

    return round(s["temp"], 2)


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

    if args.alarm_mac:
        print(f"Alarm forced on: {args.alarm_mac}")

    print("-" * 40)

    while True:
        points = []

        for mac in args.macs:
            temp = next_temp(mac, state, args.alarm_mac)

            point = {
                "measurement": "ruuvi_measurements",
                "tags": {
                    "mac": mac,
                    "dataFormat": "5"
                },
                "fields": {
                    "temperature": temp
                }
            }

            points.append(point)
            print(f"{mac} -> {temp:.2f} °C")

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