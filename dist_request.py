import base64
import io
import time
import paho.mqtt.client as mqtt
from PIL import Image
import struct

BROKER = "192.168.1.100"
PORT = 1883
REQ_TOPIC = "esp32/ultrasonic/request"
RESP_TOPIC = "esp32/ultrasonic/response"



def on_message(client, userdata, msg):

    if msg.topic == RESP_TOPIC:
        dist = struct.unpack('f', msg.payload)[0]
        print(f"Received distance value: {dist:.2f} cm.")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, PORT)
client.subscribe(RESP_TOPIC)
client.loop_start()

# Send request
print("Requesting value...")
client.publish(REQ_TOPIC, "get")

# Wait up to 5 seconds for response
timeout = 5

start = time.time()

# while (time.time() - start) < timeout:
while (1):
    # print("Requesting value...")
    client.publish(REQ_TOPIC, "get")
    time.sleep(0.1)


client.loop_stop()
client.disconnect()