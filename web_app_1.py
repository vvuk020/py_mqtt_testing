from flask import Flask, render_template, jsonify, send_file
import paho.mqtt.client as mqtt
import struct
import threading
import time
import random
import io

BROKER = "192.168.1.100"
PORT = 1883

# === Ultrasonic ===
ULTRASONIC_REQ = "esp32/ultrasonic/request"
ULTRASONIC_RESP = "esp32/ultrasonic/response"
last_distance = None
distance_lock = threading.Lock()
ultrasonic_continuous = False

# === Heartbeat ===
HEART_REQ = "esp32/heartbeat/request"
HEART_RESP = "esp32/heartbeat/response"
last_heartbeat = None
last_heartbeat_time = None
heartbeat_lock = threading.Lock()
heartbeat_continuous = False
HEARTBEAT_TIMEOUT = 3  # seconds

# === Camera ===
CAM_REQ = "esp32/picture/request"
CAM_RESP = "esp32/picture/response"
latest_image = None
image_lock = threading.Lock()
camera_continuous = False
CAMERA_TIMEOUT = 2  # seconds
last_image_time = None

# === Flask app ===
app = Flask(__name__)

# === MQTT setup ===
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_message(client, userdata, msg):
    global last_distance, last_heartbeat, last_heartbeat_time, latest_image, last_image_time
    # Ultrasonic
    if msg.topic == ULTRASONIC_RESP:
        dist = struct.unpack('f', msg.payload)[0]
        with distance_lock:
            last_distance = dist
    # Heartbeat
    elif msg.topic == HEART_RESP:
        with heartbeat_lock:
            last_heartbeat = msg.payload.decode()
            last_heartbeat_time = time.time()
    # Camera
    elif msg.topic == CAM_RESP:
        with image_lock:
            latest_image = msg.payload
            last_image_time = time.time()

client.on_message = on_message
client.connect(BROKER, PORT)
client.subscribe([(ULTRASONIC_RESP,0), (HEART_RESP,0), (CAM_RESP,0)])
client.loop_start()

# === Background loops ===
def ultrasonic_loop():
    while True:
        if ultrasonic_continuous:
            client.publish(ULTRASONIC_REQ, "get")
        time.sleep(0.5)

def heartbeat_loop():
    while True:
        if heartbeat_continuous:
            payload = f"alive:{int(time.time())}:{random.randint(1000,9999)}"
            client.publish(HEART_REQ, payload)
        time.sleep(2)  # heartbeat every 2s

def camera_loop():
    while True:
        if camera_continuous:
            client.publish(CAM_REQ, "get")
        time.sleep(0.5)  # camera request every 0.5s

# Start threads
threading.Thread(target=ultrasonic_loop, daemon=True).start()
threading.Thread(target=heartbeat_loop, daemon=True).start()
threading.Thread(target=camera_loop, daemon=True).start()

# === Routes ===
@app.route("/")
def index():
    return render_template("index_1.html")

# --- Ultrasonic ---
@app.route("/request_once")
def request_once():
    client.publish(ULTRASONIC_REQ, "get")
    start = time.time()
    while time.time() - start < 3:
        with distance_lock:
            if last_distance is not None:
                return jsonify({"distance": last_distance})
        time.sleep(0.05)
    return jsonify({"distance": None, "error": "Timeout"})

@app.route("/start_continuous_ultrasonic")
def start_continuous_ultrasonic():
    global ultrasonic_continuous
    ultrasonic_continuous = True
    return "Ultrasonic continuous started"

@app.route("/stop_continuous_ultrasonic")
def stop_continuous_ultrasonic():
    global ultrasonic_continuous
    ultrasonic_continuous = False
    return "Ultrasonic continuous stopped"

@app.route("/get_last_ultrasonic")
def get_last_ultrasonic():
    with distance_lock:
        return jsonify({"distance": last_distance})

# --- Heartbeat ---
@app.route("/send_heartbeat")
def send_heartbeat():
    global last_heartbeat, last_heartbeat_time

    # Clear previous state
    with heartbeat_lock:
        last_heartbeat = None
        last_heartbeat_time = None

    payload = f"alive:{int(time.time())}:{random.randint(1000,9999)}"
    client.publish(HEART_REQ, payload)

    # Wait up to 2 seconds for reply
    start = time.time()
    while time.time() - start < 2:
        with heartbeat_lock:
            if last_heartbeat_time is not None:
                return jsonify({
                    "status": "ok",
                    "reply": last_heartbeat,
                    "time": last_heartbeat_time
                })
        time.sleep(0.05)

    return jsonify({"status": "timeout"})


@app.route("/start_continuous_heartbeat")
def start_continuous_heartbeat():
    global heartbeat_continuous
    heartbeat_continuous = True
    return "Heartbeat continuous started"

@app.route("/stop_continuous_heartbeat")
def stop_continuous_heartbeat():
    global heartbeat_continuous
    heartbeat_continuous = False
    return "Heartbeat continuous stopped"

@app.route("/get_heartbeat")
def get_heartbeat():
    if not heartbeat_continuous:
        return jsonify({"status": "stopped"})

    with heartbeat_lock:
        if last_heartbeat_time is None:
            return jsonify({"status": "no_reply"})

        age = time.time() - last_heartbeat_time
        if age > HEARTBEAT_TIMEOUT:
            return jsonify({"status": "timeout"})

        return jsonify({
            "status": "ok",
            "reply": last_heartbeat,
            "time": last_heartbeat_time
        })



# --- Camera ---
@app.route("/request_image")
def request_image():
    client.publish(CAM_REQ, "get")
    return "Image request sent"

@app.route("/start_continuous_camera")
def start_continuous_camera():
    global camera_continuous
    camera_continuous = True
    return "Camera continuous started"

@app.route("/stop_continuous_camera")
def stop_continuous_camera():
    global camera_continuous
    camera_continuous = False
    return "Camera continuous stopped"

@app.route("/get_image")
def get_image():
    with image_lock:
        if latest_image is None or last_image_time is None:
            return "No image", 404

        if time.time() - last_image_time > CAMERA_TIMEOUT:
            return "Image timeout", 404

        return send_file(io.BytesIO(latest_image), mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
