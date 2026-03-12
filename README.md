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
├── server.crt      # SSL certificate (generated — not committed to Git)
├── server.key      # SSL private key  (generated — not committed to Git)
└── README.md
```

---

## Requirements

- Python 3.8 or higher
- OpenSSL (for certificate generation)

---

## Setup and Run

### Step 1 - Generate SSL Certificate (one time only)

```bash
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
  -keyout server.key -out server.crt \
  -subj "/C=US/ST=Demo/L=Lab/O=Project/CN=localhost"
```

This creates `server.crt` and `server.key` in the current directory.

### Step 2 — Start the Server

Open **Terminal 1**:
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

### Step 3 — Run a Client

Open **Terminal 2**:
```bash
python3 client.py 101
```

Expected output:
```
[*] Client 101: SSL/TLS handshake attempt 1/3...
[+] Client 101: SSL/TLS Handshake Successful. Authorised.
[*] Client 101: Starting UDP telemetry (rate ~10 pps, simulated loss 0%)
```

---

## Demo Guide (Evaluator Walkthrough)

### Demo 1 — SSL/TLS Authentication
**Terminal 2:**
```bash
python3 client.py 101
```
- Client performs SSL/TLS handshake over TCP.
- Server prints: `[+] Client 101 authenticated via SSL/TLS`
- Client prints: `SSL/TLS Handshake Successful. Authorised.`
- **Demonstrates:** Security deliverable (SSL/TLS).

---

### Demo 2 — Packet Loss Detection
**Terminal 3:**
```bash
python3 client.py 202 --loss 0.2
```
- Client randomly drops ~20% of packets before sending.
- Client prints: `[~] Client 202: Simulated drop — seq <N>`
- Server detects sequence gaps and increments loss counter.
- After 5 seconds the aggregation report shows ~20% loss for Client 202.
- **Demonstrates:** Sequence tracking and loss statistics deliverable.

---

### Demo 3 — Scalability / Multiple Concurrent Clients
**Terminal 4:**
```bash
python3 client.py 303
```
- Server now aggregates data for 3 simultaneous clients.
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
