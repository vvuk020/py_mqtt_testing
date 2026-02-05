import cv2
import numpy as np
import paho.mqtt.client as mqtt
import time

BROKER = "192.168.1.100"
PORT = 1883
REQ_TOPIC = "esp32/picture/request"
RESP_TOPIC = "esp32/picture/response"

exit_flag = 0
request_time = None

def on_message(client, userdata, msg):
    global exit_flag, request_time
    if msg.topic == RESP_TOPIC:
        receive_time = time.time()
        # print(f"Response came at {time.strftime('%H:%M:%S', time.localtime(receive_time))}")
        if request_time:
            print(f"Latency: {(receive_time - request_time)*1000:.1f} ms")


        # Convert bytes to numpy array
        nparr = np.frombuffer(msg.payload, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is not None:
            cv2.imshow("ESP32 Camera", img)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                exit_flag = 1
                cv2.destroyAllWindows()
                client.loop_stop()
                client.disconnect()
                exit()
        else:
            print("❌ Failed to decode image")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, PORT)
client.subscribe(RESP_TOPIC)
client.loop_start()

while True:
    request_time = time.time()
    client.publish(REQ_TOPIC, "get")
    # print(f"Request sent at {time.strftime('%H:%M:%S')}")
    
    if exit_flag:
        break
    time.sleep(0.5)