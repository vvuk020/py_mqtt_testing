from flask import Flask, render_template, jsonify, send_file, request
import paho.mqtt.client as mqtt
import threading
import time
import io
import struct

BROKER = "192.168.1.163"
PORT = 1883

HEARTBEAT_TIMEOUT = 8
IMAGE_TIMEOUT = 2  # 2 seconds timeout for images

# ================= DEVICES =================

CAMERAS = {
    f"ESP32_CAM_{i}": {
        "pic_req": f"ESP32_CAM_{i}/picture/request",
        "pic_resp": f"ESP32_CAM_{i}/picture/response",
        "hb_req": f"ESP32_CAM_{i}/heartbeat/request",
        "hb_resp": f"ESP32_CAM_{i}/heartbeat/response",
    } for i in range(1,5)
}

WATER = {
    "id": "ESP32_WLEVEL_1",
    "req": "ESP32_WLEVEL_1/distance/request",
    "resp": "ESP32_WLEVEL_1/distance/response",
    "hb_req": "ESP32_WLEVEL_1/heartbeat/request",
    "hb_resp": "ESP32_WLEVEL_1/heartbeat/response",
}

# ================= STATE =================

images = {}
image_time = {}
heartbeats = {}
hb_request_time = {}
water_value = None
water_time = None
lock = threading.Lock()

# ================= MQTT =================

client = mqtt.Client()
def on_message(client, userdata, msg):
    global water_value, water_time
    topic = msg.topic
    payload = msg.payload

    with lock:
        for cam_id, cam in CAMERAS.items():
            if topic == cam["pic_resp"]:
                images[cam_id] = payload
                image_time[cam_id] = time.time()
                # heartbeats[cam_id] = time.time()  # <-- ADD THIS
                return
            if topic == cam["hb_resp"]:
                heartbeats[cam_id] = time.time()
                return
        if topic == WATER["resp"]:
            try:
                water_value = struct.unpack("f", payload)[0]
                water_time = time.time()
            except:
                pass
            return
        if topic == WATER["hb_resp"]:
            heartbeats[WATER["id"]] = time.time()

client.on_message = on_message
client.connect(BROKER, PORT)
subs = [(cam["pic_resp"],0) for cam in CAMERAS.values()] + \
       [(cam["hb_resp"],0) for cam in CAMERAS.values()] + \
       [(WATER["resp"],0), (WATER["hb_resp"],0)]
client.subscribe(subs)
client.loop_start()

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index_2.html", cams=list(CAMERAS.keys()))

# ---------- CAMERA ----------
@app.route("/camera/<cam_id>")
def get_camera(cam_id):
    with lock:
        if cam_id not in images:
            return "No image", 404
        return send_file(io.BytesIO(images[cam_id]), mimetype="image/jpeg")

# ---------- HEARTBEAT ----------
@app.route("/heartbeat")
def get_heartbeat():
    now = time.time()
    result = {}
    with lock:
        for cam_id in CAMERAS:
            ts = heartbeats.get(cam_id)
            
            req_t = hb_request_time.get(cam_id)
            print(f"DEBUG: {cam_id} request time:{req_t:.3f}, response time:{ts:.3f} and diff{(ts-req_t):.3f}s")

            # result[cam_id] = "ack" if ts and now - ts < HEARTBEAT_TIMEOUT else "offline"
            if (ts-req_t) < HEARTBEAT_TIMEOUT:
                result[cam_id] = "ack"
            else:
                result[cam_id] = "offline"
        ts = heartbeats.get(WATER["id"])
        
        result[WATER["id"]] = "ack" if ts and now - ts < HEARTBEAT_TIMEOUT else "offline"
    return jsonify(result)

# ---------- WATER ----------
@app.route("/water")
def get_water():
    with lock:
        if water_value is None:
            return jsonify({"status": "no_data"})
        return jsonify({"value": round(water_value,2)})

# ---------- UPDATE ALL ----------
# @app.route("/update_all")
# def update_all():
#     with lock:
#         images.clear()
#         heartbeats.clear()
#     # Publish requests
#     for cam in CAMERAS.values():
#         client.publish(cam["pic_req"], "get")

#         time.sleep(0.2)
#         client.publish(cam["hb_req"], "ping")
#         # time.sleep(0.2)
#     client.publish(WATER["req"], "get")
#     client.publish(WATER["hb_req"], "ping")
#     # Wait for responses (max 2 sec)
#     start = time.time()
#     while time.time() - start < 2:
#         with lock:
#             if all(cam_id in images for cam_id in CAMERAS):
#                 break
#         time.sleep(0.05)
#     return jsonify({"status": "done"})

@app.route("/update_all")
def update_all():
    for cam_id, cam in CAMERAS.items():
        # request heartbeat first
        hb_request_time[cam_id] = time.time()
        with lock:
            heartbeats.pop(cam_id, None)  # ← clear old response
        client.publish(cam["hb_req"], "ping")
        start = time.time()
        while time.time() - start < 4:
            with lock:
                if cam_id in heartbeats:
                    break
            time.sleep(0.1)

        time.sleep(0.2)

        # request image
        client.publish(cam["pic_req"], "get")

        # wait only for THIS camera
        start = time.time()
        while time.time() - start < 4:
            with lock:
                if cam_id in images:
                    break
            time.sleep(0.1)
        time.sleep(0.2)

    # water sensor
    client.publish(WATER["hb_req"], "ping")
    time.sleep(0.1)
    client.publish(WATER["req"], "get")
    # start = time.time()
    # while time.time() - start < 2:
    #     with lock:
    #         if WATER["id"] in heartbeats or water_value is not None:
    #             break
    #     time.sleep(0.1)



    return jsonify({"status": "done"})

# ---------- MANUAL ----------
@app.route("/manual", methods=["POST"])
def manual():
    data = request.json
    req_topic = data["req"]
    client.publish(req_topic, "get")
    return jsonify({"status": "sent"})

# ================= MAIN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
