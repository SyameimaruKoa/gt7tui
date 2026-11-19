from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional


def _f(data: bytes, off: int) -> float:
    return struct.unpack("f", data[off : off + 4])[0]


def _i(data: bytes, off: int) -> int:
    return struct.unpack("i", data[off : off + 4])[0]


def _h(data: bytes, off: int) -> int:
    return struct.unpack("h", data[off : off + 2])[0]


def _H(data: bytes, off: int) -> int:
    return struct.unpack("H", data[off : off + 2])[0]


def _B(data: bytes, off: int) -> int:
    return struct.unpack("B", data[off : off + 1])[0]


@dataclass
class TyreWheel:
    temp_c: float = 0.0
    diameter_m: float = 0.0
    speed_kph: float = 0.0
    slip_ratio: Optional[float] = None
    suspension: float = 0.0
    surface_temp_c: Optional[float] = None


@dataclass
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class TelemetryFrame:
    packet_id: int = 0
    time_on_track_ms: int = 0
    current_lap: int = 0
    total_laps: int = 0
    best_lap_ms: int = -1
    last_lap_ms: int = -1
    position: int = 0
    total_positions: int = 0
    car_id: int = 0

    throttle: float = 0.0
    brake: float = 0.0
    clutch: float = 0.0
    clutch_engaged: float = 0.0
    rpm: float = 0.0
    rpm_after_clutch: float = 0.0
    speed_kph: float = 0.0
    gear: int = 0
    suggested_gear: int = 0
    boost_kpa: float = 0.0
    has_turbo: bool = False
    rev_warning: int = 0
    rev_limiter: int = 0
    est_top_speed: int = 0

    fuel_capacity: float = 0.0
    fuel_or_charge: float = 0.0
    is_ev: bool = False

    oil_temp_c: float = 0.0
    water_temp_c: float = 0.0
    oil_pressure_bar: float = 0.0
    ride_height_mm: float = 0.0

    tyres: dict[str, TyreWheel] = field(default_factory=dict)

    gear_ratios: list[float] = field(default_factory=list)
    gear_ratio_unknown: float = 0.0

    position_xyz: Vector3 = field(default_factory=Vector3)
    velocity_xyz: Vector3 = field(default_factory=Vector3)
    rotation_pyr: Vector3 = field(default_factory=Vector3)
    angular_velocity_xyz: Vector3 = field(default_factory=Vector3)
    north_south: float = 0.0

    flags_8e: int = 0
    flags_8f: int = 0
    flags_93: int = 0
    unknown_floats: dict[str, float] = field(default_factory=dict)
    raw_len: int = 0


def decode_packet(d: bytes) -> TelemetryFrame:
    frame = TelemetryFrame()
    frame.raw_len = len(d)
    if len(d) < 0x128:
        return frame

    frame.packet_id = _i(d, 0x70)
    frame.best_lap_ms = _i(d, 0x78)
    frame.last_lap_ms = _i(d, 0x7C)
    frame.current_lap = _h(d, 0x74)
    frame.total_laps = _h(d, 0x76)
    frame.time_on_track_ms = _i(d, 0x80)
    frame.position = _h(d, 0x84)
    frame.total_positions = _h(d, 0x86)
    frame.car_id = _i(d, 0x124)

    gear_byte = _B(d, 0x90)
    frame.gear = gear_byte & 0b00001111
    frame.suggested_gear = gear_byte >> 4

    frame.throttle = _B(d, 0x91) / 2.55
    frame.brake = _B(d, 0x92) / 2.55
    frame.rpm = _f(d, 0x3C)
    frame.speed_kph = 3.6 * _f(d, 0x4C)
    frame.rev_warning = _H(d, 0x88)
    frame.rev_limiter = _H(d, 0x8A)
    frame.est_top_speed = _h(d, 0x8C)

    frame.fuel_or_charge = _f(d, 0x44)
    frame.fuel_capacity = _f(d, 0x48)
    frame.is_ev = frame.fuel_capacity <= 0

    boost_raw = _f(d, 0x50)
    frame.boost_kpa = boost_raw - 1.0
    frame.has_turbo = frame.boost_kpa > -1.0

    frame.clutch = _f(d, 0xF4)
    frame.clutch_engaged = _f(d, 0xF8)
    frame.rpm_after_clutch = _f(d, 0xFC)

    frame.oil_temp_c = _f(d, 0x5C)
    frame.water_temp_c = _f(d, 0x58)
    frame.oil_pressure_bar = _f(d, 0x54)
    frame.ride_height_mm = 1000.0 * _f(d, 0x38)

    # Tyres: FL FR RL RR
    diam = {
        "FL": _f(d, 0xB4),
        "FR": _f(d, 0xB8),
        "RL": _f(d, 0xBC),
        "RR": _f(d, 0xC0),
    }
    ang = {
        "FL": _f(d, 0xA4),
        "FR": _f(d, 0xA8),
        "RL": _f(d, 0xAC),
        "RR": _f(d, 0xB0),
    }
    temp = {
        "FL": _f(d, 0x60),
        "FR": _f(d, 0x64),
        "RL": _f(d, 0x68),
        "RR": _f(d, 0x6C),
    }
    susp = {
        "FL": _f(d, 0xC4),
        "FR": _f(d, 0xC8),
        "RL": _f(d, 0xCC),
        "RR": _f(d, 0xD0),
    }
    for key in ("FL", "FR", "RL", "RR"):
        tyre_speed = abs(3.6 * diam[key] * ang[key])
        slip = None
        if frame.speed_kph > 0:
            slip = tyre_speed / frame.speed_kph
        frame.tyres[key] = TyreWheel(
            temp_c=temp[key],
            diameter_m=diam[key],
            speed_kph=tyre_speed,
            slip_ratio=slip,
            suspension=susp[key],
        )

    frame.gear_ratios = [
        _f(d, 0x104),
        _f(d, 0x108),
        _f(d, 0x10C),
        _f(d, 0x110),
        _f(d, 0x114),
        _f(d, 0x118),
        _f(d, 0x11C),
        _f(d, 0x120),
    ]
    frame.gear_ratio_unknown = _f(d, 0x100)

    frame.position_xyz = Vector3(_f(d, 0x04), _f(d, 0x08), _f(d, 0x0C))
    frame.velocity_xyz = Vector3(_f(d, 0x10), _f(d, 0x14), _f(d, 0x18))
    frame.rotation_pyr = Vector3(_f(d, 0x1C), _f(d, 0x20), _f(d, 0x24))
    frame.north_south = _f(d, 0x28)
    frame.angular_velocity_xyz = Vector3(_f(d, 0x2C), _f(d, 0x30), _f(d, 0x34))

    frame.flags_8e = _B(d, 0x8E)
    frame.flags_8f = _B(d, 0x8F)
    frame.flags_93 = _B(d, 0x93)
    for off in (0x94, 0x98, 0x9C, 0xA0, 0xD4, 0xD8, 0xDC, 0xE0, 0xE4, 0xE8, 0xEC, 0xF0):
        frame.unknown_floats[f"0x{off:02X}"] = _f(d, off)

    return frame
