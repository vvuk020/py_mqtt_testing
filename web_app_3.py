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


# ================= ACTUATORS =================

ACTUATOR = {
    "id": "ESP32_ACT_1",
    "hb_req": "ESP32_ACT_1/heartbeat/request",
    "hb_resp": "ESP32_ACT_1/heartbeat/response",
}
PUMP_REQ_TOPIC = "ESP32_ACT_1/pump/digital/request"
LIGHT_REQ_TOPIC = "ESP32_ACT_1/light/digital/request"

pump_state = 0   # 0 = OFF, 1 = ON
light_state = 0


# ================= STATE =================

images = {}
image_time = {}
heartbeats = {}
hb_request_time = {}
water_value = None
water_time = None
lock = threading.Lock()

# ================= MQTT =================

# client = mqtt.Client()
# client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client = None
def on_message(client, userdata, message):
    global water_value, water_time
    topic = message.topic
    payload = message.payload
    print(f"Got msg at topic: {topic}")
    with lock:
        for cam_id, cam in CAMERAS.items():
            if topic == cam["pic_resp"]:
                images[cam_id] = payload
                image_time[cam_id] = time.time()
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
        
        if topic == ACTUATOR["hb_resp"]:
            heartbeats[ACTUATOR["id"]] = time.time()
            print(f"RESPONSE: Actuator msg: {payload}")
            print(f"RESPONSE: Actuator hbeat: {heartbeats[ACTUATOR['id']]}")
            return

# client.on_message = on_message
# client.connect(BROKER, PORT)
# subs = [(cam["pic_resp"],0) for cam in CAMERAS.values()] + \
#        [(cam["hb_resp"],0) for cam in CAMERAS.values()] + \
#        [(WATER["resp"],0), (WATER["hb_resp"],0)]
# client.subscribe(subs)
# client.loop_start()

def init_mqtt():
    global client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(BROKER, PORT)
    subs = [(cam["pic_resp"],0) for cam in CAMERAS.values()] + \
           [(cam["hb_resp"],0) for cam in CAMERAS.values()] + \
           [(WATER["resp"],0), (WATER["hb_resp"],0)] + \
           [(ACTUATOR["hb_resp"], 0)]

    client.subscribe(subs)
    client.loop_start()

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index_3.html", cams=list(CAMERAS.keys()))

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
        # --- Cameras ---
        for cam_id in CAMERAS:
            ts = heartbeats.get(cam_id)            
            req_t = hb_request_time.get(cam_id)
            
            # Skip if either is missing
            if ts is None or req_t is None:
                result[cam_id] = "offline"
                continue

            ts_str = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(ts))
            
            print(f"DEBUG: {cam_id} request time: {req_t:.3f}, response time: {ts:.3f} and diff: {(ts-req_t):.3f}s")

            # result[cam_id] = "ack" if ts and now - ts < HEARTBEAT_TIMEOUT else "offline"
            if (ts-req_t) < HEARTBEAT_TIMEOUT:
                result[cam_id] = f"ack {ts_str}" 
            else:
                result[cam_id] = f"offline {ts_str}"
        # ts = heartbeats.get(WATER["id"])
        
        # --- Water sensor ---
        wl_id = WATER["id"]
        res_wl = heartbeats.get(wl_id)
        req_wl = hb_request_time.get(wl_id)

        # Skip if either is missing
        if res_wl is None or req_wl is None:
            result[wl_id] = "offline"
        else:
            res_wl_str = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(res_wl))
            print(f"DEBUG: {wl_id} request time: {req_wl:.3f}, response time: {res_wl:.3f} and diff: {(res_wl - req_wl):.3f}s")
            if (res_wl - req_wl) < HEARTBEAT_TIMEOUT:
                result[wl_id] = f"ack {res_wl_str}"
            else:
                result[wl_id] = f"offline {res_wl_str}"

        # result[WATER["id"]] = "ack" if ts and now - ts < HEARTBEAT_TIMEOUT else "offline"



        # --- Actuator ---
        act_id = ACTUATOR["id"]
        res_act = heartbeats.get(act_id)
        req_act = hb_request_time.get(act_id)
        # print(f"DEBUG:")

        # Always show actuator status (default to offline if no data)
        if res_act is None or req_act is None:
            result[act_id] = "offline"
        else:
            act_rs_str = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(res_act))
            print(f"DEBUG: {act_id} request time: {req_act:.3f}, response time: {res_act:.3f} and diff: {(res_act - req_act):.3f}s")
            if (res_act - req_act) < HEARTBEAT_TIMEOUT:
                result[act_id] = f"ack {act_rs_str}"
            else:
                result[act_id] = f"offline {act_rs_str}"

    
    print("HEARTBEAT ORDER:", list(result.keys()))
    
    return jsonify(result)

# ---------- WATER ----------
@app.route("/water")
def get_water():
    with lock:
        if water_value is None:
            return jsonify({"status": "no_data"})
        return jsonify({"value": round(water_value,2)})

# ---------- ACTUATORS ----------

@app.route("/pump/toggle", methods=["POST"])
def toggle_pump():
    global pump_state
    pump_state = 0 if pump_state else 1
    client.publish(PUMP_REQ_TOPIC, str(pump_state))
    print("Pump state: ", pump_state)
    return jsonify({"state": pump_state})

@app.route("/light/toggle", methods=["POST"])
def toggle_light():
    global light_state
    light_state = 0 if light_state else 1
    client.publish(LIGHT_REQ_TOPIC, str(light_state))
    print("Pump state: ", light_state)
    return jsonify({"state": light_state})

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
    hb_request_time[WATER["id"]] = time.time()
    client.publish(WATER["hb_req"], "ping")
    
    # wait for heatbeat for water level sensor
    start = time.time()
    while time.time() - start < 4:
        with lock:
            if WATER["id"] in heartbeats:
                break
        time.sleep(0.1)

    time.sleep(0.1)

    with lock:
        water_value = None # -> clear old value
    client.publish(WATER["req"], "get")

    # wait for value of water level sensor
    start = time.time()
    while time.time() - start < 4:
        with lock:
            if water_value is not None:
                break
        time.sleep(0.1)

    # actuator sensor
    hb_request_time[ACTUATOR["id"]] = time.time()
    client.publish(ACTUATOR["hb_req"], "ping")
    print(f"REQUEST: Actuator request time {hb_request_time[ACTUATOR['id']]}")

    # wait for heatbeat for actuator
    start = time.time()
    while time.time() - start < 4:
        with lock:
            if ACTUATOR["id"] in heartbeats:
                break
        time.sleep(0.1)
    
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
    init_mqtt()  # ← only run once, in main process
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)