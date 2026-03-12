import struct
import json
import time

# Packet Header Layout (Big-Endian / Network Byte Order):
#   Magic     : 2 bytes  (0xAA 0xBB) - Packet identifier
#   ClientID  : 4 bytes  (unsigned int)
#   SeqNum    : 4 bytes  (unsigned int)
#   Timestamp : 8 bytes  (double) - Unix epoch float for latency measurement
#   DataLen   : 2 bytes  (unsigned short)
# Total Header : 20 bytes

HEADER_FORMAT = "!2sIIdH"
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)
MAGIC_BYTES   = b'\xAA\xBB'


def create_packet(client_id, seq_num, data_dict):
    """
    Serialises a telemetry payload into a binary packet.

    Args:
        client_id (int): Unique identifier for the sending client.
        seq_num   (int): Monotonically increasing sequence number.
        data_dict (dict): Arbitrary telemetry key-value pairs.

    Returns:
        bytes: Binary packet ready for transmission.
    """
    payload   = json.dumps(data_dict).encode('utf-8')
    timestamp = time.time()
    header    = struct.pack(
        HEADER_FORMAT,
        MAGIC_BYTES,
        client_id,
        seq_num,
        timestamp,
        len(payload)
    )
    return header + payload


def parse_packet(binary_data):
    """
    Deserialises a binary packet back into a Python dictionary.

    Args:
        binary_data (bytes): Raw bytes received from the socket.

    Returns:
        dict | None: Parsed fields, or None if the packet is malformed.
    """
    if len(binary_data) < HEADER_SIZE:
        return None

    header_bytes = binary_data[:HEADER_SIZE]
    payload      = binary_data[HEADER_SIZE:]

    try:
        magic, cid, seq, ts, length = struct.unpack(HEADER_FORMAT, header_bytes)
    except struct.error:
        return None

    # Validate magic bytes and declared payload length
    if magic != MAGIC_BYTES:
        return None
    if len(payload) != length:
        return None

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    return {
        "client_id" : cid,
        "seq"       : seq,
        "timestamp" : ts,
        "data"      : data
    }
