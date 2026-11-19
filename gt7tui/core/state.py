from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .decoder import TelemetryFrame


@dataclass
class RuntimeState:
    frame: Optional[TelemetryFrame] = None
    connected: bool = False
    waiting: bool = True
    last_packet_time: float = 0.0
    last_packet_id: int = -1
    packets_received: int = 0
    packets_decoded: int = 0
    packets_dropped: int = 0
    last_error: str = ""
    source: str = "live"
    started_at: float = field(default_factory=time.time)

    # lap timing helpers
    current_lap_start_mono: float = 0.0
    current_lap_seen: int = -1
    current_lap_time_s: float = 0.0


class StateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = RuntimeState()

    def update_frame(self, frame: TelemetryFrame, current_lap_time_s: float | None = None) -> None:
        now = time.time()
        mono = time.monotonic()
        with self._lock:
            st = self._state
            st.frame = frame
            st.connected = True
            st.waiting = False
            st.last_packet_time = now
            st.last_packet_id = frame.packet_id
            st.packets_decoded += 1
            st.last_error = ""
            # lap timing
            if frame.current_lap > 0:
                if frame.current_lap != st.current_lap_seen:
                    st.current_lap_seen = frame.current_lap
                    st.current_lap_start_mono = mono
                    st.current_lap_time_s = max(0.0, float(current_lap_time_s or 0.0))
                else:
                    if current_lap_time_s is not None:
                        st.current_lap_time_s = max(0.0, float(current_lap_time_s))
                    else:
                        st.current_lap_time_s = max(0.0, mono - st.current_lap_start_mono)
            else:
                st.current_lap_seen = frame.current_lap
                st.current_lap_start_mono = 0.0
                st.current_lap_time_s = 0.0

    def mark_packet(self) -> None:
        with self._lock:
            self._state.packets_received += 1

    def mark_dropped(self) -> None:
        with self._lock:
            self._state.packets_dropped += 1

    def mark_waiting(self, error: str = "") -> None:
        with self._lock:
            self._state.waiting = True
            self._state.connected = False
            if error:
                self._state.last_error = error

    def set_error(self, error: str) -> None:
        with self._lock:
            self._state.last_error = error

    def set_source(self, source: str) -> None:
        with self._lock:
            self._state.source = source

    def snapshot(self) -> RuntimeState:
        with self._lock:
            st = self._state
            return RuntimeState(
                frame=st.frame,
                connected=st.connected,
                waiting=st.waiting,
                last_packet_time=st.last_packet_time,
                last_packet_id=st.last_packet_id,
                packets_received=st.packets_received,
                packets_decoded=st.packets_decoded,
                packets_dropped=st.packets_dropped,
                last_error=st.last_error,
                source=st.source,
                started_at=st.started_at,
                current_lap_start_mono=st.current_lap_start_mono,
                current_lap_seen=st.current_lap_seen,
                current_lap_time_s=st.current_lap_time_s,
            )
