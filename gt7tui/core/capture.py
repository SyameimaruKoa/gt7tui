from __future__ import annotations

import struct
import time
from pathlib import Path
from typing import BinaryIO, Iterator

MAGIC = b"GT7TCAP\0"
VERSION = 1
HEADER_STRUCT = struct.Struct("<8sH")
RECORD_STRUCT = struct.Struct("<dI")


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

    def write(self, payload: bytes, ts: float | None = None) -> None:
        if self._fp is None:
            return
        if ts is None:
            ts = time.time()
        if self._start is None:
            self._start = ts
        rel = max(0.0, ts - self._start)
        self._fp.write(RECORD_STRUCT.pack(rel, len(payload)))
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

    def records(self) -> Iterator[tuple[float, bytes]]:
        with self.path.open("rb") as fp:
            header = fp.read(HEADER_STRUCT.size)
            if len(header) != HEADER_STRUCT.size:
                raise ValueError("invalid capture file: short header")
            magic, version = HEADER_STRUCT.unpack(header)
            if magic != MAGIC:
                raise ValueError("invalid capture file: bad magic")
            if version != VERSION:
                raise ValueError(f"unsupported capture version: {version}")
            self.version = version
            while True:
                rec = fp.read(RECORD_STRUCT.size)
                if not rec:
                    break
                if len(rec) != RECORD_STRUCT.size:
                    raise ValueError("invalid capture file: truncated record header")
                ts, length = RECORD_STRUCT.unpack(rec)
                payload = fp.read(length)
                if len(payload) != length:
                    raise ValueError("invalid capture file: truncated payload")
                yield float(ts), payload
