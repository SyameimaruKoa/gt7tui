from __future__ import annotations

import math
import threading
import time
from typing import Optional

from .decoder import TelemetryFrame, TyreWheel, Vector3
from .state import StateStore


class DemoSource:
    def __init__(self, store: StateStore, refresh_hz: float = 20.0) -> None:
        self.store = store
        self.refresh_hz = max(1.0, refresh_hz)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gt7tui-demo", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        self.store.set_source("demo")
        t0 = time.monotonic()
        pkt = 0
        interval = 1.0 / self.refresh_hz
        best_ms = 92345
        last_ms = 93120
        total_laps = 5
        while not self._stop.is_set():
            now = time.monotonic() - t0
            pkt += 1
            # cyclic scenario ~90s lap
            lap_len = 90.0
            lap_pos = (now % lap_len) / lap_len
            current_lap = int(now // lap_len) + 1
            if current_lap > total_laps:
                # loop scenario
                t0 = time.monotonic()
                now = 0.0
                lap_pos = 0.0
                current_lap = 1
            phase = lap_pos * 2.0 * math.pi
            accel = max(0.0, math.sin(phase))
            brake = max(0.0, math.sin(phase + math.pi)) * (0.7 if lap_pos > 0.1 else 0.2)
            throttle = min(100.0, max(0.0, accel * 100.0 - brake * 20.0))
            brake_pct = min(100.0, max(0.0, brake * 100.0))
            rpm = 1500 + (6500 - 1500) * (0.5 + 0.5 * math.sin(phase * 2.0 - 0.5))
            if throttle < 5 and brake_pct > 20:
                rpm = 1500 + 800 * (0.5 + 0.5 * math.sin(now * 3))
            speed = max(0.0, (rpm - 1200) / 6500 * 260.0)
            gear = 1
            for g, lim in enumerate([40, 70, 110, 150, 190, 220, 245, 999], start=1):
                if speed <= lim:
                    gear = g
                    break
            suggested = min(8, gear + (1 if rpm > 6200 else 0))
            rev_limiter = 7200
            rev_warning = 6800
            boost = 80.0 * max(0.0, math.sin(phase)) if gear >= 3 else 30.0 * max(0.0, math.sin(phase))

            def tyre(temp_base: float, slip_bias: float) -> TyreWheel:
                temp = temp_base + 12.0 * math.sin(phase + slip_bias) + 4.0 * (throttle / 100.0)
                slip = 1.0 + 0.03 * abs(math.sin(phase + slip_bias)) + (0.12 if brake_pct > 60 else 0.0)
                diam = 0.64
                ang = speed / 3.6 / max(diam, 0.1)
                susp = 0.05 + 0.02 * math.sin(phase * 1.7 + slip_bias)
                return TyreWheel(
                    temp_c=temp,
                    diameter_m=diam,
                    speed_kph=abs(3.6 * diam * ang),
                    slip_ratio=slip,
                    suspension=susp,
                )

            frame = TelemetryFrame(
                packet_id=pkt,
                time_on_track_ms=int(now * 1000),
                current_lap=current_lap,
                total_laps=total_laps,
                best_lap_ms=best_ms,
                last_lap_ms=last_ms if current_lap > 1 else -1,
                position=3,
                total_positions=16,
                car_id=1234,
                throttle=throttle,
                brake=brake_pct,
                clutch=0.0 if gear > 0 else 1.0,
                clutch_engaged=1.0,
                rpm=rpm,
                rpm_after_clutch=rpm,
                speed_kph=speed,
                gear=gear,
                suggested_gear=suggested,
                boost_kpa=boost,
                has_turbo=True,
                rev_warning=rev_warning,
                rev_limiter=rev_limiter,
                est_top_speed=265,
                fuel_capacity=60.0,
                fuel_or_charge=max(0.0, 60.0 - now * 0.05),
                is_ev=False,
                oil_temp_c=95.0 + 8.0 * math.sin(phase * 0.5),
                water_temp_c=88.0 + 6.0 * math.sin(phase * 0.5),
                oil_pressure_bar=4.5 + 0.5 * (rpm / 7000.0),
                ride_height_mm=110.0,
                tyres={
                    "FL": tyre(86.0, 0.1),
                    "FR": tyre(87.0, 0.2),
                    "RL": tyre(84.0, 0.3),
                    "RR": tyre(85.0, 0.4),
                },
                gear_ratios=[3.2, 2.1, 1.6, 1.3, 1.1, 0.95, 0.85, 0.78],
                gear_ratio_unknown=4.1,
                position_xyz=Vector3(100.0 * math.cos(phase), 5.0, 100.0 * math.sin(phase)),
                velocity_xyz=Vector3(speed / 3.6 * math.cos(phase), 0.0, speed / 3.6 * math.sin(phase)),
                rotation_pyr=Vector3(0.01, phase, 0.02 * math.sin(phase)),
                angular_velocity_xyz=Vector3(0.0, 0.1, 0.0),
                north_south=0.0,
                flags_8e=0,
                flags_8f=0,
                flags_93=0,
                unknown_floats={},
                raw_len=296,
            )
            self.store.mark_packet()
            self.store.update_frame(frame)
            time.sleep(interval)
