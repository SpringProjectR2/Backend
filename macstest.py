import requests

BASE_URL = "http://10.137.17.253:5000"  # change if needed

def get_macs(hours=24):
    url = f"{BASE_URL}/macs"

    try:
        print(f"Requesting: {url}?hours={hours}")
        response = requests.get(url, params={"hours": hours}, timeout=5)

        print("Status code:", response.status_code)
        response.raise_for_status()

        macs = response.json()

        if not macs:
            print("\nNo active sensors found.")
        else:
            print(f"\nFound {len(macs)} active sensor(s):\n")
            for mac in macs:
                print(f"- {mac}")

        return macs

    except requests.exceptions.RequestException as e:
        print("Request failed:", e)


if __name__ == "__main__":
    get_macs()