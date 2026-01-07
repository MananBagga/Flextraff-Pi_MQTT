# FlexTraff RFID Edge Microservice

**Production IoT Edge Microservice** | Adaptive Traffic Control System  
Runs on Raspberry Pi | RFID Reader | MQTT Integration | systemd Auto-Start

---

## 1. Project Overview

### What This Service Does

This microservice runs on a Raspberry Pi at the edge of the network and performs three core functions:

1. **Reads RFID Tags** – Continuously monitors an RFID reader over TCP, detecting vehicle tags
2. **Aggregates Vehicle Counts** – Groups detections into traffic cycles and deduplicates readings
3. **Publishes & Receives Traffic Control Signals** – Sends vehicle counts to a backend via MQTT and receives optimized green-light timings back

### Why It Exists

**Problem Solved:**

Modern traffic control systems require real-time data from the edge to make intelligent decisions. Centralizing all traffic detection in the cloud introduces network latency, creates single points of failure, and wastes bandwidth. This service acts as a **local intelligence hub** that:

- Processes RFID data at the source (no backhaul overhead)
- Handles vehicle deduplication locally (RFID readers see the same tag multiple times)
- Provides cycle-level aggregation before publishing to the cloud
- Responds immediately to backend-computed green-light timings
- Continues operating gracefully even if network connectivity is temporarily lost

### Role in FlexTraff System

This service is one **junction node** in the FlexTraff Adaptive Traffic Control System:

```
┌─────────────────────────────────────────┐
│     FlexTraff Backend (Cloud/VM)        │
│  - Processes data from all junctions    │
│  - Runs optimization algorithms         │
│  - Computes adaptive signal timings     │
└─────────────────────────────────────────┘
            ↑ (MQTT)            ↓ (MQTT)
    (car_counts)         (green_times)
            │                    │
            │                    │
┌─────────────────────────────────────────┐
│  This Service (Raspberry Pi Edge)       │
│  - Aggregates RFID tags                 │
│  - Publishes counts per traffic cycle   │
│  - Receives optimized signal timings    │
│  - Executes traffic light control       │
└─────────────────────────────────────────┘
            ↓ (TCP)
    ┌─────────────────┐
    │  RFID Reader    │
    │  (on network)   │
    └─────────────────┘
```

## 2. High-Level Architecture

### Data Flow

1. **RFID Reader**: Continuously scans for vehicle tags and sends data over TCP.
2. **Edge Microservice**:
   - Processes RFID data to deduplicate tags.
   - Aggregates vehicle counts for each traffic cycle.
   - Publishes counts to the backend via MQTT.
   - Receives green-light timings from the backend via MQTT.
3. **FlexTraff Backend**: Optimizes traffic signal timings based on aggregated data from all junctions.
4. **Traffic Light Controller**: Executes the green-light timings received from the backend.

### Threads and Logic

- **RFID Worker Thread**: Handles TCP communication with the RFID reader, processes tag data, and updates the current cycle's tag set.
- **MQTT Callbacks**: Manages MQTT communication, including publishing vehicle counts and receiving green-light timings.
- **Cycle Logic**: Implements the traffic signal cycle, including automatic green-light timing and backend response handling.

---

## 3. Hardware and Software Requirements

### Hardware
- Raspberry Pi (any model with network connectivity)
- RFID Reader (TCP-enabled)
- Traffic Light Controller (optional, for integration)

### Software
- Python 3.8+
- MQTT Broker (e.g., HiveMQ, Eclipse Mosquitto)
- Required Python packages (see `requirements.txt`):
  - `paho-mqtt`

---

## 4. End-to-End Runtime Workflow

1. **Boot**: The Raspberry Pi starts, and the microservice is launched automatically via `systemd`.
2. **RFID Reader**: The RFID worker thread connects to the reader and begins processing tag data.
3. **MQTT Publish**: Vehicle counts are published to the backend at the end of each traffic cycle.
4. **MQTT Subscribe**: The backend sends optimized green-light timings, which are applied immediately.
5. **Cycle Reset**: The system resets for the next traffic cycle.

---

## 5. MQTT Design

### Topics
- **Publish**: `flextraff/car_counts`
- **Subscribe**: `flextraff/green_times`

### Payloads
- **Publish Payload**:
  ```json
  {
    "junction_id": 1,
    "lane_counts": [30, 60, 100, 25],
    "cycle_id": 1234567890
  }
  ```
- **Subscribe Payload**:
  ```json
  {
    "cycle_id": 1234567890,
    "green_time": [36, 52, 86, 20]
  }
  ```

### Design Notes
- **Cycle ID**: Ensures that responses correspond to the correct traffic cycle.
- **Retain Flag**: Set to `false` to avoid stale messages.

---

## 6. Deployment on Raspberry Pi

1. **Install Dependencies**:
   ```bash
   sudo apt update && sudo apt install python3 python3-pip
   pip3 install -r requirements.txt
   ```
2. **Configure Systemd**:
   - Create a service file `/etc/systemd/system/flextraff.service`:
     ```ini
     [Unit]
     Description=FlexTraff Edge Microservice
     After=network.target

     [Service]
     ExecStart=/usr/bin/python3 /path/to/main.py
     Restart=always
     User=pi

     [Install]
     WantedBy=multi-user.target
     ```
   - Enable and start the service:
     ```bash
     sudo systemctl enable flextraff.service
     sudo systemctl start flextraff.service
     ```

---

## 7. Common Commands

- **Start Service**: `sudo systemctl start flextraff.service`
- **Stop Service**: `sudo systemctl stop flextraff.service`
- **Restart Service**: `sudo systemctl restart flextraff.service`
- **View Logs**: `journalctl -u flextraff.service`

---

## 8. Logging, Debugging, and Common Issues

### Logging
- Logs are printed to the console and can be viewed using `journalctl`.

### Debugging
- Check MQTT connectivity using `mosquitto_sub` or similar tools.
- Verify RFID reader connection using `telnet`.

### Common Issues
- **RFID Connection Fails**: Ensure the reader's IP and port are correct.
- **MQTT Publish Fails**: Check broker availability and credentials.

---

## 9. Key Design Decisions and Limitations

### Design Decisions
- **Edge Processing**: Reduces latency and bandwidth usage.
- **MQTT Protocol**: Lightweight and reliable for IoT communication.

### Limitations
- **RFID Range**: Limited by the hardware capabilities.
- **Network Dependency**: Requires stable network connectivity for MQTT.

---

## 10. Future Improvements

- Add support for multiple RFID readers.
- Implement fallback mechanisms for network outages.
- Enhance security with TLS for MQTT communication.

---

## 11. Getting Started for New Engineers

1. **Understand the Code**:
   - Review `main.py` to understand the threading model and MQTT logic.
   - Check `test_pub.py` for MQTT testing examples.
2. **Set Up the Environment**:
   - Install dependencies and configure the Raspberry Pi.
3. **Test the System**:
   - Use an MQTT client to simulate backend responses.
4. **Deploy and Debug**:
   - Deploy the service using `systemd` and monitor logs for issues.

---

For further assistance, refer to the comments in the code or contact the project maintainer.
