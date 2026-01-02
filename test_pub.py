# clear_retained.py
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"  # or mqtt.eclipseprojects.io, whichever you used
TOPIC = "flextraff/car_counts"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to broker, clearing retained message...")
        client.publish(TOPIC, payload=None, retain=True)
        print("🧹 Retained message cleared.")
        client.disconnect()
    else:
        print(f"❌ Failed to connect: {rc}")

client = mqtt.Client()
client.on_connect = on_connect
client.connect(BROKER, 1883, 60)
client.loop_forever()
