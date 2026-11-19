from __future__ import annotations

import threading
import time
from typing import Optional

from .capture import CaptureReader, DIR_RECV
from .decoder import decode_packet
from .protocol import decrypt_packet
from .state import StateStore


class ReplaySource:
    def __init__(self, path: str, store: StateStore, speed: float = 1.0, loop: bool = False) -> None:
        self.path = path
        self.store = store
        self.speed = speed if speed > 0 else 1.0
        self.loop = loop
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gt7tui-replay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        self.store.set_source("replay")
        last_pkt_id = -1
        try:
            while not self._stop.is_set():
                reader = CaptureReader(self.path)
                prev_ts: float | None = None
                any_record = False
                for rec in reader.records():
                    if self._stop.is_set():
                        return
                    any_record = True
                    ts = rec.ts
                    if prev_ts is not None:
                        delay = (ts - prev_ts) / self.speed
                        if delay > 0:
                            # sleep in chunks for responsiveness
                            end = time.monotonic() + delay
                            while not self._stop.is_set():
                                remaining = end - time.monotonic()
                                if remaining <= 0:
                                    break
                                time.sleep(min(0.05, remaining))
                    prev_ts = ts
                    # Only received telemetry packets are fed into the decoder/state.
                    # Sent packets (e.g. heartbeats) are kept in the capture for completeness.
                    if rec.direction != DIR_RECV:
                        continue
                    self.store.mark_packet()
                    ddata = decrypt_packet(rec.payload)
                    if not ddata:
                        self.store.mark_dropped()
                        continue
                    frame = decode_packet(ddata)
                    if frame.packet_id <= last_pkt_id and last_pkt_id >= 0:
                        # allow reset if capture loops naturally
                        if frame.packet_id < last_pkt_id - 1000:
                            last_pkt_id = -1
                        else:
                            self.store.mark_dropped()
                            continue
                    last_pkt_id = frame.packet_id
                    self.store.update_frame(frame)
                if not any_record:
                    self.store.mark_waiting("replay: empty capture")
                    return
                if not self.loop:
                    self.store.set_error("replay: finished")
                    self.store.mark_waiting("replay finished")
                    return
                last_pkt_id = -1
        except Exception as e:
            self.store.mark_waiting(f"replay error: {e}")
