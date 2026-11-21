from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .decoder import TelemetryFrame, drivetrain_layout


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
    ev_peak_charge: float = 0.0

    # G sensor (derived from velocity delta): lateral, longitudinal, vertical in G
    g_lateral: float = 0.0
    g_longitudinal: float = 0.0
    g_vertical: float = 0.0

    # drivetrain layout statistics
    layout_counts: dict[str, int] = field(default_factory=dict)
    layout_throttle: dict[str, float] = field(default_factory=dict)
    layout_speed: dict[str, float] = field(default_factory=dict)
    layout_total: int = 0
    _prev_velocity: tuple[float, float, float] | None = None
    _prev_vel_time: float = 0.0


class StateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = RuntimeState()

    def update_frame(self, frame: TelemetryFrame, current_lap_time_s: float | None = None, packet_ts: float | None = None) -> None:
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
            # EV battery: track peak charge this session to derive SOC
            if frame.is_ev and frame.fuel_or_charge > st.ev_peak_charge:
                st.ev_peak_charge = frame.fuel_or_charge
            # Drivetrain layout statistics (on-demand AWD detection)
            lay = drivetrain_layout(frame)
            st.layout_counts[lay] = st.layout_counts.get(lay, 0) + 1
            st.layout_throttle[lay] = st.layout_throttle.get(lay, 0.0) + frame.throttle
            st.layout_speed[lay] = st.layout_speed.get(lay, 0.0) + frame.speed_kph
            st.layout_total += 1
            # G sensor: differentiate velocity. Use packet timestamp when replay provides it,
            # otherwise wall clock. Guard against noise / duplicated packets.
            v = (frame.velocity_xyz.x, frame.velocity_xyz.y, frame.velocity_xyz.z)
            vel_time = packet_ts if packet_ts is not None else now
            if st._prev_velocity is not None:
                dt = vel_time - st._prev_vel_time
                if 0.001 < dt < 0.5:
                    ax = (v[0] - st._prev_velocity[0]) / dt
                    ay = (v[1] - st._prev_velocity[1]) / dt
                    az = (v[2] - st._prev_velocity[2]) / dt
                    # smooth to reduce per-packet jitter; clamp implausible spikes
                    def smooth_g(prev: float, raw: float) -> float:
                        raw = max(-6.0, min(6.0, raw))
                        val = prev * 0.8 + raw * 0.2
                        # rate limit: at most 0.5G change per update
                        delta = max(-0.5, min(0.5, val - prev))
                        return max(-6.0, min(6.0, prev + delta))
                    st.g_longitudinal = smooth_g(st.g_longitudinal, ax / 9.81)
                    st.g_lateral = smooth_g(st.g_lateral, ay / 9.81)
                    st.g_vertical = smooth_g(st.g_vertical, az / 9.81)
            st._prev_velocity = v
            st._prev_vel_time = vel_time
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
                ev_peak_charge=st.ev_peak_charge,
                g_lateral=st.g_lateral,
                g_longitudinal=st.g_longitudinal,
                g_vertical=st.g_vertical,
                layout_counts=dict(st.layout_counts),
                layout_throttle=dict(st.layout_throttle),
                layout_speed=dict(st.layout_speed),
                layout_total=st.layout_total,
                _prev_velocity=st._prev_velocity,
                _prev_vel_time=st._prev_vel_time,
            )
