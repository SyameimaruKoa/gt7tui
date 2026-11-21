from __future__ import annotations

from Crypto.Cipher import Salsa20

MAGIC = 0x47375330
KEY = b"Simulator Interface Packet GT7 ver 0.0"

# Heartbeat character -> (XOR key for IV, expected decrypted packet size)
# From PDTools SimulatorInterfaceClient / SimulatorInterfaceCryptorGT7
HEARTBEAT_A = "A"   # legacy, 0x128 packet
HEARTBEAT_B = "B"   # GT7 >= 1.42, 0x13C packet
HEARTBEAT_TILDE = "~"  # GT7 >= 1.42, 0x158 packet (max expansion)

HEARTBEAT_CONFIG = {
    HEARTBEAT_A: {"xor": 0xDEADBEAF, "size": 0x128},
    HEARTBEAT_B: {"xor": 0xDEADBEEF, "size": 0x13C},
    HEARTBEAT_TILDE: {"xor": 0x55FABB4F, "size": 0x158},
}


def xor_key_for(heartbeat: str) -> int:
    return HEARTBEAT_CONFIG.get(heartbeat, HEARTBEAT_CONFIG[HEARTBEAT_A])["xor"]


def expected_size(heartbeat: str) -> int:
    return HEARTBEAT_CONFIG.get(heartbeat, HEARTBEAT_CONFIG[HEARTBEAT_A])["size"]


def decrypt_packet(data: bytes | bytearray, heartbeat: str = HEARTBEAT_A) -> bytes:
    if len(data) < 0x44:
        return b""
    oiv = data[0x40:0x44]
    iv1 = int.from_bytes(oiv, byteorder="little")
    iv2 = iv1 ^ xor_key_for(heartbeat)
    iv = bytearray()
    iv.extend(iv2.to_bytes(4, "little"))
    iv.extend(iv1.to_bytes(4, "little"))
    cipher = Salsa20.new(key=KEY[0:32], nonce=bytes(iv))
    ddata = cipher.decrypt(bytes(data))
    magic = int.from_bytes(ddata[0:4], byteorder="little")
    if magic != MAGIC:
        return b""
    return ddata


def decrypt_packet_auto(data: bytes | bytearray) -> tuple[bytes, str]:
    """Try all known heartbeat XOR keys; return (decrypted, heartbeat) or (b'', '')."""
    for hb in (HEARTBEAT_TILDE, HEARTBEAT_B, HEARTBEAT_A):
        d = decrypt_packet(data, hb)
        if d:
            return d, hb
    return b"", ""
