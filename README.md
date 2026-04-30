# Backend

## Getting started
```
apt install ansible git -y
git clone https://github.com/ilatvala/ruuvigw.git
cd ruuvigw/
```

## Configuration

Before running the playbook, edit `iot-project.yml` to set your sensor MAC-to-name mappings:

```yaml
ruuvi_sensor_names: |
  C606A8B37ECC=Sensor1
  # Add more sensors here: MAC=Name
```

## Running the playbook

```bash
ansible-playbook -i "127.0.0.1," iot-project.yml --ask-become-pass
```

### Optional: simulator mode

To run `simulator.py` instead of relying on live Ruuvi sensors (e.g. for testing), uncomment the simulator service tasks at the bottom of section 6 in the playbook before running.