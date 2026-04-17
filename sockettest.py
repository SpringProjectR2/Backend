import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("Connected to server")

@sio.on("temperature_update")
def handle_data(data):
    print("Temperature:", data)

sio.connect("http://10.137.17.253:5000")
sio.wait()