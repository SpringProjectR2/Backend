import requests

BASE_URL = "http://10.137.17.253:5000"

def get_macs(hours=24):
    url = f"{BASE_URL}/macs"
    print(f"Fetching MACs from {url}")

    r = requests.get(url, params={"hours": hours}, timeout=5)
    r.raise_for_status()

    macs = r.json()
    return macs


def get_history(mac, hours=24, limit=10):
    url = f"{BASE_URL}/history/{mac}"
    print(f"\nFetching history for {mac}")

    r = requests.get(url, params={"hours": hours, "limit": limit}, timeout=5)
    r.raise_for_status()

    return r.json()


def main():
    macs = get_macs(hours=24)

    if not macs:
        print("No active sensors found.")
        return

    print(f"\nFound {len(macs)} sensor(s):")
    for m in macs:
        print(" -", m)

    # pick first mac
    mac = macs[0]

    history = get_history(mac, hours=24, limit=10)

    print(f"\nLast {len(history)} readings for {mac}:\n")
    for h in history:
        print(h)


if __name__ == "__main__":
    main()