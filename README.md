# Backend
# assumes PI has ruuvicollector and influxdb installed and configured, TODO: installer to fix these
## Getting started

Create virtual environment
```bash
python3 -m venv .venv
. .venv/bin/activate
```

Install dependencies
```bash
pip install -r requirements.txt
```

Run app
```bash
python main.py
```

Simulator.py is for generating sensor data serverside for testing.
test_features.py simulates a frontend and tests main features.
