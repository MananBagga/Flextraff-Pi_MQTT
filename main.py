import socket
import time
import binascii
import json
import threading
import signal
import sys
import paho.mqtt.client as mqtt
from collections import defaultdict

# ------------------ Configuration ------------------
READER_IP = "192.168.1.116"
READER_PORT = 6000
IGNORE_INTERVAL = 60
GREEN_INTERVAL = 25

running = True
rfid_socket = None
# ---------------------------------------------------

# ------------------ MQTT Config --------------------
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_PUB = "flextraff/car_counts"
TOPIC_SUB = "flextraff/green_times"
# ---------------------------------------------------

client = mqtt.Client(client_id="pi_reader", protocol=mqtt.MQTTv311)

signal_phase = "RED"
current_cycle_tags = set()
last_seen = defaultdict(float)
lock = threading.Lock()
backend_response = None

# ---------------- MQTT Callbacks -------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(TOPIC_SUB, qos=1)
    else:
        print(f"❌ MQTT connection failed (rc={rc})")

def on_message(client, userdata, msg):
    global signal_phase, current_cycle_tags, backend_response
    try:
        data = json.loads(msg.payload.decode())
        backend_response = data
        print(f"🟢 Backend response: {data}")

        with lock:
            signal_phase = "GREEN"
            green_times = data.get("green_times", [])
            time.sleep(max(green_times) if green_times else 5)
            signal_phase = "RED"
            current_cycle_tags.clear()

    except Exception as e:
        print(f"❌ MQTT message error: {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"⚠️ MQTT disconnected (rc={rc})")

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# ---------------- Helper Functions -----------------
def publish_current_count():
    with lock:
        if not client.is_connected():
            return

        car_count = len(current_cycle_tags)
        payload = {
            "junction_id": 1,
            "lane_counts": [30, 60, 100, car_count]
        }

        print(f"📤 Publishing count: {payload}")
        client.publish(TOPIC_PUB, json.dumps(payload), qos=1)

def auto_green_timer():
    global signal_phase, backend_response
    while running:
        time.sleep(GREEN_INTERVAL)
        with lock:
            signal_phase = "GREEN"
        publish_current_count()
        time.sleep(3)
        with lock:
            signal_phase = "RED"
            current_cycle_tags.clear()
            backend_response = None

# ---------------- RFID Worker ----------------------
def rfid_worker():
    global rfid_socket, running

    retry_delay = 1

    while running:
        try:
            print(f"🔗 Connecting to RFID reader {READER_IP}:{READER_PORT}")

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)

            # 🔑 KEEPALIVE — VERY IMPORTANT
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

            s.connect((READER_IP, READER_PORT))
            s.settimeout(1)

            rfid_socket = s
            retry_delay = 1
            print("✅ RFID connected")

            while running:
                try:
                    data = s.recv(1024)
                    if not data:
                        continue

                    hex_data = binascii.hexlify(data).decode().upper()
                    epcs = []

                    for prefix in ("30", "E2"):
                        idx = 0
                        while True:
                            idx = hex_data.find(prefix, idx)
                            if idx == -1:
                                break
                            epcs.append(hex_data[idx:idx+24])
                            idx += 24

                    with lock:
                        now = time.time()
                        for epc in epcs:
                            if now - last_seen[epc] > IGNORE_INTERVAL:
                                last_seen[epc] = now
                                current_cycle_tags.add(epc)
                                print(f"🆕 RFID: {epc}")

                except socket.timeout:
                    continue

        except Exception as e:
            print(f"⚠️ RFID error: {e}")

        finally:
            try:
                if rfid_socket:
                    rfid_socket.close()
            except:
                pass

            rfid_socket = None
            print(f"🔁 Reconnecting RFID in {retry_delay}s")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

# ---------------- Clean Shutdown -------------------
def shutdown_handler(sig, frame):
    global running
    print("\n🛑 Shutting down cleanly")
    running = False

    try:
        if rfid_socket:
            rfid_socket.shutdown(socket.SHUT_RDWR)
            rfid_socket.close()
    except:
        pass

    client.loop_stop()
    client.disconnect()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# ---------------- Start Everything -----------------
print(f"🔗 Connecting to MQTT broker {BROKER}:{PORT}")
client.connect(BROKER, PORT, keepalive=60)
client.loop_start()

threading.Thread(target=auto_green_timer, daemon=True).start()
threading.Thread(target=rfid_worker, daemon=True).start()

while True:
    time.sleep(1)
