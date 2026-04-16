# Telemetry Collection and Aggregation System
**Team 6 - Socket Programming Mini Project**

---

## Overview

A distributed telemetry system where multiple clients continuously stream sensor data to a central server over UDP, with an SSL/TLS-secured TCP control plane for authentication. The server tracks sequence numbers, calculates packet loss, measures latency and throughput, and prints a live aggregation report every 5 seconds.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SERVER                               │
│                                                             │
│  ┌───────────────────┐      ┌────────────────────────────┐  │
│  │  Control Plane    │      │       Data Plane           │  │
│  │  TCP :8888        │      │       UDP :8888            │  │
│  │  SSL/TLS          │      │  Seq Tracking | Latency    │  │
│  │  Authentication   │      │  Throughput   | Loss Stats │  │
│  └───────────────────┘      └────────────────────────────┘  │
│           ▲                             ▲                   │
└───────────┼─────────────────────────────┼───────────────────┘
            │ TCP (SSL)                   │ UDP (Binary)
            │                             │
   ┌────────┴───────────────────────────────────────────┐
   │   CLIENT (client.py)                               │
   │   Step 1: SSL/TLS Handshake  →  AUTH_OK            │
   │   Step 2: UDP Telemetry Stream (10 pps)            │
   └────────────────────────────────────────────────────┘

Multiple clients run simultaneously (Client 101, 202, 303 ...)
```

### Communication Flow
1. Client opens TCP connection → SSL/TLS handshake → sends `HELLO:<id>` → receives `AUTH_OK`
2. Client starts UDP stream: binary packets at ~10 per second
3. Server detects sequence gaps → calculates loss %, latency, throughput
4. Aggregation report printed to console every 5 seconds

---

## Packet Protocol

Defined in `protocol.py`. Every UDP packet has a fixed 20-byte binary header followed by a JSON payload.

```
┌──────────┬──────────┬──────────┬───────────────┬──────────┬─────────────┐
│  Magic   │ ClientID │  SeqNum  │   Timestamp   │ DataLen  │   Payload   │
│  2 bytes │  4 bytes │  4 bytes │    8 bytes    │  2 bytes │  N bytes    │
│ 0xAA 0xBB│  uint32  │  uint32  │  float64(UTC) │ uint16   │  UTF-8 JSON │
└──────────┴──────────┴──────────┴───────────────┴──────────┴─────────────┘
Total header: 20 bytes  |  Format string: !2sIIdH
```

Payload example:
```json
{"cpu": 57, "temp": 63}
```

---

## File Structure

```
project/
├── server.py       # Multi-threaded server (Control Plane + Data Plane + Reporter)
├── client.py       # Client (SSL handshake → UDP telemetry stream)
├── protocol.py     # Packet encode/decode (struct + JSON)
├── server.crt      # SSL certificate (generated)
├── server.key      # SSL private key  (generated)
└── README.md
```

---

## Requirements

- Python 3.8 or higher
- OpenSSL (for certificate generation)

---

## Setup and Run

### Step 1 — Generate SSL Certificate (one-time, on the **Server** machine)

```bash
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
  -keyout server.key -out server.crt \
  -subj "/C=IN/ST=Demo/L=Lab/O=Project/CN=telemetry-server"
```

This creates `server.crt` and `server.key`. Copy **both files along with `server.py` and `protocol.py`** to the Server machine.
Copy **`client.py` and `protocol.py`** to the Client machine (the cert files are NOT needed on the client — `CERT_NONE` is used).

---

### Step 2 — Connect both computers to the **same hotspot**

Both the Server machine and the Client machine must be connected to the same Wi-Fi / mobile hotspot.

#### Find the Server machine's LAN IP address

**macOS / Linux:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
# or
ip -4 addr show | grep inet
```

**Windows:**
```cmd
ipconfig
# Look for the "IPv4 Address" under your Wi-Fi adapter
```

The IP will look like `192.168.x.x` or `10.x.x.x`. Note it — you'll need it on the Client.

---

### Step 3 — (macOS / Linux) Allow port 8888 through the firewall

**macOS** — if the macOS firewall is on, either temporarily disable it or add an exception:
```bash
# Allow python3 through the firewall (run once, requires sudo)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add $(which python3)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblock $(which python3)
```

**Linux (ufw):**
```bash
sudo ufw allow 8888/tcp
sudo ufw allow 8888/udp
```

**Windows** — allow Python through Windows Defender Firewall when prompted, or run:
```cmd
netsh advfirewall firewall add rule name="Telemetry 8888" protocol=TCP dir=in localport=8888 action=allow
netsh advfirewall firewall add rule name="Telemetry 8888" protocol=UDP dir=in localport=8888 action=allow
```

---

### Step 4 — Start the Server (on the **Server** machine)

```bash
python3 server.py
```

Expected output:
```
[*] Starting Telemetry Collection and Aggregation Server...
[*] Host: 0.0.0.0  |  Port: 8888  |  Protocol: TCP (control) + UDP (data)
[*] Secure Control Plane (SSL/TLS) listening on TCP 8888
[*] Data Plane (UDP Telemetry) listening on UDP 8888
```

The server binds to `0.0.0.0` — it listens on **all** network interfaces, including the hotspot interface.

---

### Step 5 — Run a Client (on the **Client** machine)

Replace `192.168.1.10` with the **actual LAN IP** of the Server machine from Step 2.

```bash
python3 client.py 101 --server 192.168.1.10
```

Expected output:
```
[*] Server target : 192.168.1.10:8888
[*] Client ID     : 101
[*] Simulated loss: 0%
--------------------------------------------------
[*] Client 101: SSL/TLS handshake attempt 1/3 → 192.168.1.10:8888
[+] Client 101: SSL/TLS Handshake Successful. Authorised.
[*] Client 101: Starting UDP telemetry → 192.168.1.10:8888  (rate ~10 pps, simulated loss 0%)
```

On the **Server** terminal you should see:
```
[+] Client 101 authenticated via SSL/TLS from 192.168.x.x
```

---

## Demo Guide (Evaluator Walkthrough)

> **In all demo commands below, replace `192.168.1.10` with the actual LAN IP of the Server machine.**

### Demo 1 — SSL/TLS Authentication
**Client machine — Terminal 1:**
```bash
python3 client.py 101 --server 192.168.1.10
```
- Client performs SSL/TLS handshake over TCP across the two machines.
- **Server** prints: `[+] Client 101 authenticated via SSL/TLS from <client-LAN-IP>`
- **Client** prints: `SSL/TLS Handshake Successful. Authorised.`
- **Demonstrates:** Security deliverable (SSL/TLS) across a real network link.

---

### Demo 2 — Packet Loss Detection
**Client machine — Terminal 2** (or a second terminal on the same client machine):
```bash
python3 client.py 202 --server 192.168.1.10 --loss 0.2
```
- Client randomly drops ~20% of packets before sending.
- Client prints: `[~] Client 202: Simulated drop — seq <N>`
- Server detects sequence gaps and increments loss counter.
- After 5 seconds the aggregation report shows ~20% loss for Client 202.
- **Demonstrates:** Sequence tracking and loss statistics deliverable.

---

### Demo 3 — Scalability / Multiple Concurrent Clients
**Client machine — Terminal 3:**
```bash
python3 client.py 303 --server 192.168.1.10
```
- Server now aggregates data for 3 simultaneous clients originating from different processes.
- Each client independently tracked in the report.
- **Demonstrates:** Multiple distributed clients deliverable.

---

### Demo 4 — Aggregation Report (read from Server Terminal)

After ~5 seconds with all clients running, the server prints:

```
======================================================================
  TELEMETRY AGGREGATION REPORT  —  2025-01-01 10:00:05
======================================================================
Client      Recv     Lost    Loss%   Latency(ms)      PPS    Bad
----------------------------------------------------------------------
101          49        0    0.00%         0.123      10.0      0
202          41        9   18.00%         0.118      10.0      0
303          50        0    0.00%         0.120      10.0      0
======================================================================
```

Columns explained:
| Column | Description |
|---|---|
| Recv | Total valid packets received |
| Lost | Packets inferred lost via sequence gaps |
| Loss% | `Lost / (Recv + Lost) * 100` |
| Latency(ms) | Average one-way packet delay (ms) |
| PPS | Packets per second (throughput) |
| Bad | Malformed/unrecognised packets discarded |

---

## Performance Metrics

| Metric | How Measured |
|---|---|
| Packet Loss | Sequence gap detection in `server.py` → `handle_data_plane()` |
| One-Way Latency | Timestamp embedded in packet header; delta computed on receipt |
| Throughput (PPS) | 1-second sliding window packet counter per client |
| Scalability | Run 3+ clients simultaneously; all tracked independently |
