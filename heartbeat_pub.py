import time
import random
import paho.mqtt.client as mqtt

BROKER = "192.168.1.100"
PORT = 1883
REQUEST_TOPIC = "esp32/heartbeat/request"
RESPONSE_TOPIC = "esp32/heartbeat/response"

# Global to hold reply
reply_received = None

def on_message(client, userdata, msg):
    global reply_received
    if msg.topic == RESPONSE_TOPIC:
        reply_received = msg.payload.decode()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, PORT)
client.subscribe(RESPONSE_TOPIC)
client.loop_start()  # Start background network loop

print("Publisher heartbeat with reply check...")

try:
    while True:
        reply_received = None
        payload = f"alive:{int(time.time())}:{random.randint(1000, 9999)}"
        client.publish(REQUEST_TOPIC, payload)
        print(f"Sent: {payload}")

        # Wait up to 2 seconds for reply
        start = time.time()
        while reply_received is None and (time.time() - start) < 2:
            time.sleep(0.1)

        if reply_received:
            print(f"Reply: {reply_received}")
        else:
            print("No reply received.")

        time.sleep(5)

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    client.loop_stop()
    client.disconnect()