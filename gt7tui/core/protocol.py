from __future__ import annotations

from Crypto.Cipher import Salsa20

MAGIC = 0x47375330
KEY = b"Simulator Interface Packet GT7 ver 0.0"


def decrypt_packet(data: bytes | bytearray) -> bytes:
    if len(data) < 0x44:
        return b""
    oiv = data[0x40:0x44]
    iv1 = int.from_bytes(oiv, byteorder="little")
    iv2 = iv1 ^ 0xDEADBEAF
    iv = bytearray()
    iv.extend(iv2.to_bytes(4, "little"))
    iv.extend(iv1.to_bytes(4, "little"))
    cipher = Salsa20.new(key=KEY[0:32], nonce=bytes(iv))
    ddata = cipher.decrypt(bytes(data))
    magic = int.from_bytes(ddata[0:4], byteorder="little")
    if magic != MAGIC:
        return b""
    return ddata
