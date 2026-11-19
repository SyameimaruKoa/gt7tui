from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

MAGIC = b"GT7TCAP\0"
VERSION = 2
HEADER_STRUCT = struct.Struct("<8sH")
# v2: timestamp(float64), payload_len(uint32), direction(uint8), port(uint16), reserved(uint8)
RECORD_STRUCT_V2 = struct.Struct("<dIBHB")
# v1 legacy: timestamp(float64), payload_len(uint32)
RECORD_STRUCT_V1 = struct.Struct("<dI")

DIR_RECV = 0
DIR_SEND = 1


@dataclass
class CaptureRecord:
    ts: float
    payload: bytes
    direction: int = DIR_RECV
    port: int = 0


class CaptureWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp: BinaryIO | None = None
        self._start: float | None = None

    def open(self) -> "CaptureWriter":
        self._fp = self.path.open("wb")
        self._fp.write(HEADER_STRUCT.pack(MAGIC, VERSION))
        self._fp.flush()
        self._start = None
        return self

    def write(self, payload: bytes, ts: float | None = None, direction: int = DIR_RECV, port: int = 0) -> None:
        if self._fp is None:
            return
        if ts is None:
            ts = time.time()
        if self._start is None:
            self._start = ts
        rel = max(0.0, ts - self._start)
        self._fp.write(RECORD_STRUCT_V2.pack(rel, len(payload), int(direction) & 0xFF, int(port) & 0xFFFF, 0))
        self._fp.write(payload)

    def close(self) -> None:
        if self._fp:
            try:
                self._fp.flush()
                self._fp.close()
            except Exception:
                pass
            self._fp = None

    def __enter__(self) -> "CaptureWriter":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class CaptureReader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.version = 0

    def records(self) -> Iterator[CaptureRecord]:
        with self.path.open("rb") as fp:
            header = fp.read(HEADER_STRUCT.size)
            if len(header) != HEADER_STRUCT.size:
                raise ValueError("invalid capture file: short header")
            magic, version = HEADER_STRUCT.unpack(header)
            if magic != MAGIC:
                raise ValueError("invalid capture file: bad magic")
            if version not in (1, 2):
                raise ValueError(f"unsupported capture version: {version}")
            self.version = version
            if version == 1:
                rec_struct = RECORD_STRUCT_V1
            else:
                rec_struct = RECORD_STRUCT_V2
            while True:
                rec = fp.read(rec_struct.size)
                if not rec:
                    break
                if len(rec) != rec_struct.size:
                    raise ValueError("invalid capture file: truncated record header")
                if version == 1:
                    ts, length = rec_struct.unpack(rec)
                    direction = DIR_RECV
                    port = 0
                else:
                    ts, length, direction, port, _reserved = rec_struct.unpack(rec)
                payload = fp.read(length)
                if len(payload) != length:
                    raise ValueError("invalid capture file: truncated payload")
                yield CaptureRecord(ts=float(ts), payload=payload, direction=int(direction), port=int(port))
