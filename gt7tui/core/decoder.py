from __future__ import annotations

import math
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


def _safe_float(v: float, default: float = 0.0) -> float:
    if not math.isfinite(v):
        return default
    return float(v)


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

    # Road plane normal (0x94-0x9C) and distance from road (0xA0)
    road_plane_x: float = 0.0
    road_plane_y: float = 0.0
    road_plane_z: float = 0.0
    road_plane_distance: float = 0.0

    # Extended fields (GT7 >= 1.42, heartbeat "B" / "~")
    wheel_rotation_rad: float | None = None
    sway: float | None = None
    heave: float | None = None
    surge: float | None = None
    throttle_filtered: int | None = None
    brake_filtered: int | None = None
    car_type: int | None = None
    energy_recovery: float | None = None
    energy_recovery_flag: int | None = None
    throttle_actuated: int | None = None
    brake_actuated: int | None = None
    packet_expansion: str = "none"

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
    frame.rpm = _safe_float(_f(d, 0x3C))
    frame.speed_kph = _safe_float(3.6 * _f(d, 0x4C))
    frame.rev_warning = _H(d, 0x88)
    frame.rev_limiter = _H(d, 0x8A)
    frame.est_top_speed = _h(d, 0x8C)

    frame.fuel_or_charge = _safe_float(_f(d, 0x44))
    frame.fuel_capacity = _safe_float(_f(d, 0x48))
    frame.is_ev = frame.fuel_capacity <= 0

    boost_raw = _f(d, 0x50)
    # 0x50 is absolute pressure in bar (1.0 = ambient). Convert gauge pressure to kPa.
    frame.boost_kpa = _safe_float((boost_raw - 1.0) * 100.0)
    frame.has_turbo = frame.boost_kpa > -100.0

    frame.clutch = _safe_float(_f(d, 0xF4))
    frame.clutch_engaged = _safe_float(_f(d, 0xF8))
    frame.rpm_after_clutch = _safe_float(_f(d, 0xFC))

    frame.oil_temp_c = _safe_float(_f(d, 0x5C))
    frame.water_temp_c = _safe_float(_f(d, 0x58))
    frame.oil_pressure_bar = _safe_float(_f(d, 0x54))
    frame.ride_height_mm = _safe_float(1000.0 * _f(d, 0x38))

    # Tyres: FL FR RL RR
    diam = {
        "FL": _safe_float(_f(d, 0xB4)),
        "FR": _safe_float(_f(d, 0xB8)),
        "RL": _safe_float(_f(d, 0xBC)),
        "RR": _safe_float(_f(d, 0xC0)),
    }
    ang = {
        "FL": _safe_float(_f(d, 0xA4)),
        "FR": _safe_float(_f(d, 0xA8)),
        "RL": _safe_float(_f(d, 0xAC)),
        "RR": _safe_float(_f(d, 0xB0)),
    }
    temp = {
        "FL": _safe_float(_f(d, 0x60)),
        "FR": _safe_float(_f(d, 0x64)),
        "RL": _safe_float(_f(d, 0x68)),
        "RR": _safe_float(_f(d, 0x6C)),
    }
    susp = {
        "FL": _safe_float(_f(d, 0xC4)),
        "FR": _safe_float(_f(d, 0xC8)),
        "RL": _safe_float(_f(d, 0xCC)),
        "RR": _safe_float(_f(d, 0xD0)),
    }
    for key in ("FL", "FR", "RL", "RR"):
        tyre_speed = abs(3.6 * diam[key] * ang[key])
        if not math.isfinite(tyre_speed):
            tyre_speed = 0.0
        slip = None
        # Avoid division blow-up at standstill / very low speed and during stops/pit/spin transitions.
        if frame.speed_kph >= 2.0 and math.isfinite(frame.speed_kph):
            denom = max(frame.speed_kph, 1e-3)
            slip_val = tyre_speed / denom
            if math.isfinite(slip_val):
                # Cap extreme values (burnout/spin/telemetry noise) for stable display.
                slip = max(0.0, min(20.0, slip_val))
        frame.tyres[key] = TyreWheel(
            temp_c=temp[key],
            diameter_m=diam[key],
            speed_kph=tyre_speed,
            slip_ratio=slip,
            suspension=susp[key],
        )

    frame.gear_ratios = [
        _safe_float(_f(d, 0x104)),
        _safe_float(_f(d, 0x108)),
        _safe_float(_f(d, 0x10C)),
        _safe_float(_f(d, 0x110)),
        _safe_float(_f(d, 0x114)),
        _safe_float(_f(d, 0x118)),
        _safe_float(_f(d, 0x11C)),
        _safe_float(_f(d, 0x120)),
    ]
    frame.gear_ratio_unknown = _safe_float(_f(d, 0x100))

    frame.position_xyz = Vector3(_safe_float(_f(d, 0x04)), _safe_float(_f(d, 0x08)), _safe_float(_f(d, 0x0C)))
    frame.velocity_xyz = Vector3(_safe_float(_f(d, 0x10)), _safe_float(_f(d, 0x14)), _safe_float(_f(d, 0x18)))
    frame.rotation_pyr = Vector3(_safe_float(_f(d, 0x1C)), _safe_float(_f(d, 0x20)), _safe_float(_f(d, 0x24)))
    frame.north_south = _safe_float(_f(d, 0x28))
    frame.road_plane_x = _safe_float(_f(d, 0x94))
    frame.road_plane_y = _safe_float(_f(d, 0x98))
    frame.road_plane_z = _safe_float(_f(d, 0x9C))
    frame.road_plane_distance = _safe_float(_f(d, 0xA0))
    frame.angular_velocity_xyz = Vector3(_safe_float(_f(d, 0x2C)), _safe_float(_f(d, 0x30)), _safe_float(_f(d, 0x34)))

    frame.flags_8e = _B(d, 0x8E)
    frame.flags_8f = _B(d, 0x8F)
    frame.flags_93 = _B(d, 0x93)
    for off in (0x94, 0x98, 0x9C, 0xA0, 0xD4, 0xD8, 0xDC, 0xE0, 0xE4, 0xE8, 0xEC, 0xF0):
        frame.unknown_floats[f"0x{off:02X}"] = _safe_float(_f(d, off))

    # Extended fields (PDTools SimulatorPacket.Read). 0x13C = +WheelRotation,
    # FillerFloatFB, Sway, Heave, Surge.  0x158 = +Unk bytes, Unk5 vec4,
    # EnergyRecovery, Unk7.
    if len(d) >= 0x13C:
        frame.wheel_rotation_rad = _safe_float(_f(d, 0x128))
        frame.sway = _safe_float(_f(d, 0x130))
        frame.heave = _safe_float(_f(d, 0x134))
        frame.surge = _safe_float(_f(d, 0x138))
        frame.packet_expansion = "0x13C"
    if len(d) >= 0x158:
        frame.throttle_filtered = _B(d, 0x13C)
        frame.brake_filtered = _B(d, 0x13D)
        frame.throttle_actuated = _B(d, 0x13C)
        frame.brake_actuated = _B(d, 0x13D)
        frame.car_type = _B(d, 0x13E)
        frame.energy_recovery_flag = _B(d, 0x13F)
        frame.energy_recovery = _safe_float(_f(d, 0x150))
        frame.packet_expansion = "0x158"

    return frame


def wheel_drive_state(frame: TelemetryFrame, wheel_key: str) -> str:
    """Derive DRIVE / BRAKE / ROLL from slip ratio + pedal input.

    Under power, driven wheels show slip > 1. Under braking, slip < 1.
    Threshold of 0.5% filters telemetry noise.
    """
    w = frame.tyres.get(wheel_key)
    if w is None or w.slip_ratio is None:
        return "--"
    slip = w.slip_ratio
    if frame.throttle > 5.0 and slip > 1.005:
        return "DRV"
    if frame.brake > 5.0 and slip < 0.995:
        return "BRK"
    return "ROL"


def drivetrain_layout(frame: TelemetryFrame, slip_threshold: float = 1.05) -> str:
    """Detect driven axle from relative wheel slip.

    An absolute slip>threshold test mislabels FWD cars: their undriven rear wheels
    still show small slip (~1.03-1.07) from sensor rounding / inertia at launch.
    Compare front vs rear averages: the axle with clearly greater slip is driven.
    AWD only when both axles have significant AND comparable slip.
    """
    if not frame.tyres:
        return "--"
    def avg(keys):
        vals = [frame.tyres[k].slip_ratio for k in keys
                if k in frame.tyres and frame.tyres[k].slip_ratio is not None]
        return sum(vals) / len(vals) if vals else None
    front = avg(("FL", "FR"))
    rear = avg(("RL", "RR"))
    if front is None or rear is None:
        return "--"
    # excess slip above 1.0
    fe = max(0.0, front - 1.0)
    re = max(0.0, rear - 1.0)
    if fe < 0.01 and re < 0.01:
        return "COAST"
    # relative dominance: driven axle has clearly more excess slip
    if fe >= 0.01 and re >= 0.01:
        if abs(fe - re) <= 0.02 and min(fe, re) >= 0.015:
            return "AWD"
        return "FWD" if fe > re else "RWD"
    return "FWD" if fe > re else "RWD"


def induction_state(frame: TelemetryFrame) -> str:
    """Return induction type. Turbo flag is authoritative; show boost-on state separately."""
    if not frame.has_turbo:
        return "NA"
    if frame.boost_kpa > 5.0:
        return "TURBO+"
    return "TURBO"


def gear_ratio_valid(frame: TelemetryFrame) -> bool:
    """Some cars (CVT / special) send zero gear ratios."""
    return sum(1 for r in frame.gear_ratios if r > 0) >= 2


def tyre_roles(frame: TelemetryFrame, g_lateral: float, g_longitudinal: float) -> dict[str, str]:
    """Describe each wheel's current job.

    - Longitudinal: accelerating -> driven axle wheels DRIVE; braking -> all BRAKE.
    - Lateral: outside wheels (loaded by cornering force) GRIP, inside wheels INNER.
    Rotational direction: left turn -> right side outside.
    """
    layout = drivetrain_layout(frame)
    roles: dict[str, str] = {}
    # outside side from lateral G: negative lateral = turning left -> right wheels outside
    if g_lateral > 0.05:
        outside = "R"
    elif g_lateral < -0.05:
        outside = "L"
    else:
        outside = ""
    # longitudinal state
    state = ""
    if frame.brake > 5.0 or g_longitudinal < -0.08:
        state = "BRAKE"
    elif frame.throttle > 5.0 or g_longitudinal > 0.08:
        state = "DRIVE"
    for key in ("FL", "FR", "RL", "RR"):
        parts = []
        axial = "F" if key.startswith("F") else "R"
        # longitudinal role
        if state == "BRAKE":
            parts.append("BRK")
        elif state == "DRIVE":
            if layout == "AWD" or layout == "--" or axial == layout[0]:
                parts.append("DRV")
        # lateral role
        if outside:
            if key.endswith(outside):
                parts.append("GRIP")
            else:
                parts.append("in")
        roles[key] = "/".join(parts) if parts else "roll"
    return roles


def has_energy_recovery(frame: TelemetryFrame) -> bool:
    """unk4 (0x13F) is 1 on cars with energy recovery per PDTools issue #14."""
    return frame.energy_recovery_flag == 1
