import socket
import time
import binascii
import json
import threading
import paho.mqtt.client as mqtt
from collections import defaultdict

# ------------------ Configuration ------------------
READER_IP = "192.168.1.116"   # RFID reader's IP
READER_PORT = 6000            # RFID reader's TCP port
IGNORE_INTERVAL = 60          # seconds to ignore repeated RFID
# ---------------------------------------------------

# --- MQTT Config ---
BROKER = "broker.hivemq.com"   # MQTT Broker
PORT = 1883
TOPIC_PUB = "flextraff/car_counts"
TOPIC_SUB = "flextraff/green_times"

# --- Temporary GREEN TRIGGER interval ---
GREEN_INTERVAL = 25  # seconds (temporary green light trigger)
# ---------------------------------------------------

# --- MQTT Setup ---
client = mqtt.Client(client_id="pi_reader", protocol=mqtt.MQTTv311)

signal_phase = "RED"
current_cycle_tags = set()
last_seen = defaultdict(float)
lock = threading.Lock()  # thread safety

backend_response = None  # Store response from backend


# ---------------- MQTT Callbacks ----------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(TOPIC_SUB, qos=1)
        print(f"📡 Subscribed to: {TOPIC_SUB}")
    else:
        print(f"❌ MQTT connection failed (rc={rc})")


def on_message(client, userdata, msg):
    """Triggered when backend sends updated green times."""
    global signal_phase, current_cycle_tags, backend_response
    try:
        data = json.loads(msg.payload.decode())
        print(f"🟢 Received green times from backend: {data}")
        
        # Store response for logging
        backend_response = data
        
        with lock:
            signal_phase = "GREEN"
            # Green phase is now active with timing from backend
            green_times = data.get("green_times", [0, 0, 0, 0])
            cycle_time = data.get("cycle_time", 0)
            print(f"🚦 Green times applied: {green_times} (Cycle: {cycle_time}s)")
            
            # After green phase, reset
            time.sleep(max(green_times) if green_times else 5)
            signal_phase = "RED"
            current_cycle_tags.clear()
            print("🔴 Back to RED phase — waiting for new cars...\n")
            
    except json.JSONDecodeError as e:
        print(f"❌ Failed to decode JSON: {e}")
    except Exception as e:
        print(f"❌ Error in on_message: {e}")


def on_publish(client, userdata, mid):
    """Confirm message successfully sent to broker."""
    print(f"✅ Message published successfully (mid={mid})")


def on_disconnect(client, userdata, rc):
    """Handle disconnection"""
    if rc != 0:
        print(f"⚠️ Unexpected disconnection (rc={rc}). Reconnecting...")


# Assign callbacks
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish
client.on_disconnect = on_disconnect


# ---------------- Helper Functions ----------------
def publish_current_count():
    """Publish total unique tags detected in this cycle."""
    with lock:
        if not client.is_connected():
            print("⚠️ MQTT not connected — skipping publish.")
            return

        car_count = len(current_cycle_tags)
        lane_counts = [30, 60, 100, car_count]
        payload = {"junction_id": 1, "lane_counts": lane_counts}
        
        print("\n" + "=" * 60)
        print("📤 PUBLISHING CAR COUNT TO BACKEND")
        print("=" * 60)
        print(f"🚗 Total cars detected: {car_count}")
        print(f"📊 Lane counts: {lane_counts}")
        print(f"📡 Publishing to topic: {TOPIC_PUB}")
        print(f"📦 Payload: {json.dumps(payload)}")
        
        result = client.publish(TOPIC_PUB, json.dumps(payload), qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"📨 Publish initiated (mid={result.mid})")
            print(f"⏳ Waiting for backend response on topic: {TOPIC_SUB}...")
        else:
            print(f"❌ Publish failed (rc={result.rc})")
        
        print("=" * 60)


def auto_green_timer():
    """Simulate GREEN every GREEN_INTERVAL seconds."""
    global signal_phase, current_cycle_tags, backend_response
    
    while True:
        time.sleep(GREEN_INTERVAL)
        
        with lock:
            print("\n" + "="*60)
            print("🟩 Auto GREEN PHASE TRIGGERED (timer thread)")
            print("="*60)
            
            signal_phase = "GREEN"
        
        # Publish outside the lock to avoid blocking
        publish_current_count()
        
        # Wait for backend response
        print("⏳ Waiting for backend response...")
        time.sleep(3)  # Give backend time to respond
        
        with lock:
            if backend_response:
                print(f"✅ Backend responded with timing")
            else:
                print(f"⚠️ No response from backend yet")
            
            signal_phase = "RED"
            current_cycle_tags.clear()
            backend_response = None
            print("🔴 Back to RED phase — counting restarted.\n")


# ---------------- Start Connections ----------------
print(f"🔗 Connecting to MQTT broker at {BROKER}:{PORT}...")
client.connect(BROKER, PORT, keepalive=60)
client.loop_start()
time.sleep(2)  # wait for MQTT connection to establish
print("✅ MQTT connection established\n")

# Start background green timer
print(f"⏰ Starting auto-green timer (every {GREEN_INTERVAL} seconds)\n")
threading.Thread(target=auto_green_timer, daemon=True).start()

# Connect to RFID reader
print(f"🔗 Connecting to RFID reader at {READER_IP}:{READER_PORT} ...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect((READER_IP, READER_PORT))
    print("✅ Connected successfully! Waiting for tag data...\n")
except Exception as e:
    print(f"❌ Failed to connect to RFID reader: {e}")
    print("⚠️ Continuing without RFID data for MQTT testing...\n")
    s = None

# ---------------- RFID Main Loop ----------------
while True:
    try:
        if s is None:
            # If no RFID reader, just keep the program running
            time.sleep(1)
            continue
            
        data = s.recv(1024)
        if not data:
            continue

        # Decode incoming RFID data
        hex_data = binascii.hexlify(data).decode().upper()
        epcs = []

        # Detect possible EPCs
        for prefix in ["30", "E2"]:
            idx = 0
            while True:
                idx = hex_data.find(prefix, idx)
                if idx == -1:
                    break
                epc = hex_data[idx:idx+24]
                epcs.append(epc)
                idx += 24

        # Add unique tags safely
        with lock:
            current_time = time.time()
            for epc in epcs:
                if current_time - last_seen[epc] > IGNORE_INTERVAL:
                    current_cycle_tags.add(epc)
                    last_seen[epc] = current_time
                    print(f"🆕 New tag detected: {epc} | Total this cycle: {len(current_cycle_tags)}")

        time.sleep(0.1)

    except socket.timeout:
        continue
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(1)

# ---------------- Cleanup ----------------
if s:
    s.close()
client.loop_stop()
client.disconnect()
print("🔌 Disconnected.")