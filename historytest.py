import requests

URL = "http://10.137.17.253:5000/history/ruuvitag"

params = {
    "hours": 1,
    "limit": 5
}

response = requests.get(URL, params=params)

if response.status_code == 200:
    data = response.json()
    print("Received data:\n")

    for item in data:
        print(f"Time: {item['time']}, Temp: {item['temperature']}")
else:
    print("Error:", response.status_code, response.text)