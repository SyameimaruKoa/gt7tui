from __future__ import annotations

import math

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from ...core.decoder import induction_state, gear_ratio_valid, flag_names, FLAG8E_BITS, FLAG8F_BITS
from ...config import AppConfig
from ...core.state import RuntimeState


def _panel(*args, **kwargs):
    kwargs.setdefault("box", box.SQUARE)
    return Panel(*args, **kwargs)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _center_meter(label: str, value: float, lim: float, unit: str = "", width: int = 21, color_pos: str = "cyan", color_neg: str = "magenta") -> Text:
    lim = max(1e-6, lim)
    ratio = max(-1.0, min(1.0, value / lim))
    mid = width // 2
    pos = mid + int(round(ratio * (mid - 1)))
    pos = max(0, min(width - 1, pos))
    active = color_pos if ratio >= 0 else color_neg
    t = Text()
    t.append(f"{label:<5}")
    t.append("[", style="grey50")
    for i in range(width):
        if i == pos:
            t.append("◆", style=f"bold {active}")
        elif i == mid:
            t.append("┼", style="white")
        elif (mid < i <= pos) or (pos <= i < mid):
            t.append("━", style=active)
        else:
            t.append("·", style="grey30")
    t.append("]", style="grey50")
    t.append(f" {value:+8.3f}{unit}")
    return t


def _mag_meter(label: str, mag: float, vmax: float, unit: str = "", color: str = "green", width: int = 16) -> Text:
    vmax = max(1e-6, vmax)
    ratio = _clamp01(abs(mag) / vmax)
    pos = int(round(ratio * (width - 1)))
    t = Text()
    t.append(f"{label:<5}")
    t.append("[", style="grey50")
    for i in range(width):
        if i == pos:
            t.append("▮", style=f"bold {color}")
        elif i < pos:
            t.append("━", style=color)
        else:
            t.append("─", style="grey23")
    t.append("]", style="grey50")
    t.append(f" {abs(mag):7.3f}{unit}")
    return t


def _fmt_vec(v) -> str:
    return f"X={v.x:+9.4f}  Y={v.y:+9.4f}  Z={v.z:+9.4f}"


class DetailPane(Container):
    def __init__(self, config: AppConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.dynamics = Static(id="dynamics-panel", classes="detail-dynamics")
        self.gearing = Static(classes="detail-gearing")
        self.flags = Static(id="flags-panel")
        self.session = Static(classes="detail-session")

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="top-row"):
                yield self.session
                yield self.gearing
            with Horizontal(classes="bottom-row"):
                yield self.dynamics
                yield self.flags

    def update_view(self, snap: RuntimeState, cfg: AppConfig) -> None:
        f = snap.frame
        # Session / general as instrument readouts
        st = Table.grid(padding=(0, 1))
        if f:
            st.add_row(Text.assemble(("Car ID: ", "grey70"), (str(f.car_id), "bold white"), ("   Packet: ", "grey70"), (str(f.packet_id), "cyan"), ("   Raw: ", "grey70"), (f"{f.raw_len} B", "white")))
            st.add_row(Text.assemble(("Time: ", "grey70"), (f"{f.time_on_track_ms/1000.0:,.1f} s", "bold white"), ("   Est Vmax: ", "grey70"), (f"{f.est_top_speed} km/h", "bright_cyan")))
            st.add_row(Text.assemble(("RideH: ", "grey70"), (f"{f.ride_height_mm:5.1f} mm", "yellow")))
            # analog mini meters
            st.add_row(_mag_meter("OilP", f.oil_pressure_bar, 10.0, "b", "yellow3"))
            st.add_row(_mag_meter("Thro", f.throttle, 100.0, "%", "green"))
            st.add_row(_mag_meter("Brak", f.brake, 100.0, "%", "red"))
            st.add_row(_mag_meter("Clut", min(1.5, max(0.0, f.clutch)) * 100.0 / 150.0 if f.clutch > 1.5 else f.clutch * 100.0, 100.0, "%", "blue"))
            st.add_row(Text.assemble(("Clutch engage: ", "grey70"), (f"{f.clutch_engaged:.3f}", "white"), ("  RPM after: ", "grey70"), (f"{f.rpm_after_clutch:.0f}", "white")))
            boost = f"{f.boost_kpa:.2f} kPa" if f.has_turbo else "N/A"
            st.add_row(Text.assemble(("Boost: ", "grey70"), (boost, "cyan" if f.has_turbo else "grey50"), ("   Speed: ", "grey70"), (f"{f.speed_kph:.1f} km/h", "bold bright_cyan"), ("   RPM: ", "grey70"), (f"{f.rpm:.0f}", "bold green")))
            st.add_row(Text.assemble(("Induction: ", "grey70"), (induction_state(f), "bright_yellow"), ("  Gear ratios: ", "grey70"), ("N/A (special/CVT)" if not gear_ratio_valid(f) else "available", "cyan")))
        else:
            st.add_row(Text("No telemetry frame", style="dim"))
        self.session.update(_panel(st, title="Session / Vehicle", border_style="cyan"))

        # Gearing as horizontal bars
        gt = Table.grid(padding=(0, 1))
        if f and f.gear_ratios:
            vals = [v for v in f.gear_ratios if v > 0]
            vmax = max(vals) if vals else 1.0
            cur = f.gear
            for i, ratio in enumerate(f.gear_ratios, start=1):
                active = (i == cur)
                color = "bold bright_yellow" if active else "grey70"
                bar_w = 18
                r = _clamp01(ratio / vmax) if vmax > 0 else 0
                filled = int(round(r * bar_w))
                bar = Text()
                bar.append(f"{i}: ", style=color)
                bar.append("[", style="grey50")
                for j in range(bar_w):
                    if j < filled:
                        bar.append("█", style="bright_yellow" if active else "cyan")
                    else:
                        bar.append("░", style="grey23")
                bar.append("]", style="grey50")
                bar.append(f" {ratio:7.3f}", style=color)
                if active:
                    bar.append(" ◀", style="bold bright_yellow")
                gt.add_row(bar)
            # GT7 broadcasts only 8 gear ratios (0x104-0x120) plus a final/unknown
            # ratio at 0x100. Cars with 9/10 gears report the gear correctly but
            # never send those ratios, so show them explicitly as N/A.
            for g in (9, 10):
                active = (f.gear == g)
                mark = " ◀" if active else ""
                style = "bold bright_yellow" if active else "grey50"
                gt.add_row(Text(f"{g}: N/A (not broadcast){mark}", style=style))
            gt.add_row(Text(f"final: {f.gear_ratio_unknown:7.3f}", style="grey50"))
        else:
            gt.add_row(Text("No data", style="dim"))
        self.gearing.update(_panel(gt, title="Gearing", border_style="magenta"))

        # Dynamics as meters
        dt = Table.grid(padding=(0, 0))
        if f:
            # Position
            dt.add_row(Text("Position (m)", style="bold grey70"))
            dt.add_row(_center_meter("X", f.position_xyz.x, 1000.0, "m", color_pos="green", color_neg="red"))
            dt.add_row(_center_meter("Y", f.position_xyz.y, 200.0, "m", color_pos="green", color_neg="red"))
            dt.add_row(_center_meter("Z", f.position_xyz.z, 1000.0, "m", color_pos="green", color_neg="red"))
            pm = math.sqrt(f.position_xyz.x**2 + f.position_xyz.y**2 + f.position_xyz.z**2)
            dt.add_row(_mag_meter("|P|", pm, 1500.0, "m", "bright_green"))
            # Velocity
            dt.add_row(Text("Velocity (m/s)", style="bold grey70"))
            vlim = 120.0
            dt.add_row(_center_meter("X", f.velocity_xyz.x, vlim, "", color_pos="cyan", color_neg="magenta"))
            dt.add_row(_center_meter("Y", f.velocity_xyz.y, 40.0, "", color_pos="cyan", color_neg="magenta"))
            dt.add_row(_center_meter("Z", f.velocity_xyz.z, vlim, "", color_pos="cyan", color_neg="magenta"))
            vm = math.sqrt(f.velocity_xyz.x**2 + f.velocity_xyz.y**2 + f.velocity_xyz.z**2)
            dt.add_row(_mag_meter("|V|", vm, 130.0, "", "bright_cyan"))
            # Rotation / angular
            dt.add_row(Text("Rotation PYR (rad)", style="bold grey70"))
            dt.add_row(_center_meter("P", f.rotation_pyr.x, math.pi, "", color_pos="yellow", color_neg="blue"))
            dt.add_row(_center_meter("Y", f.rotation_pyr.y, math.pi, "", color_pos="yellow", color_neg="blue"))
            dt.add_row(_center_meter("R", f.rotation_pyr.z, math.pi, "", color_pos="yellow", color_neg="blue"))
            dt.add_row(Text("Angular vel (r/s)", style="bold grey70"))
            dt.add_row(_center_meter("X", f.angular_velocity_xyz.x, 5.0, "", color_pos="orange3", color_neg="purple"))
            dt.add_row(_center_meter("Y", f.angular_velocity_xyz.y, 5.0, "", color_pos="orange3", color_neg="purple"))
            dt.add_row(_center_meter("Z", f.angular_velocity_xyz.z, 5.0, "", color_pos="orange3", color_neg="purple"))
            dt.add_row(_center_meter("N/S", f.north_south, 1.0, "", color_pos="white", color_neg="grey50"))
            dt.add_row(Text("Road plane normal", style="bold grey70"))
            dt.add_row(_center_meter("X", f.road_plane_x, 1.0, "", color_pos="green", color_neg="red"))
            dt.add_row(_center_meter("Y", f.road_plane_y, 1.0, "", color_pos="green", color_neg="red"))
            dt.add_row(_center_meter("Z", f.road_plane_z, 1.0, "", color_pos="green", color_neg="red"))
            dt.add_row(_mag_meter("Dist", f.road_plane_distance, 20.0, "m", "yellow3"))
        else:
            dt.add_row(Text("No data", style="dim"))
        self.dynamics.update(_panel(dt, title="Dynamics", border_style="green"))

        # Flags as lamps + all unknown / extended fields
        ft = Table.grid(padding=(0, 0))
        if not f:
            ft.add_row(Text("No data", style="dim"))
        else:
            def lamps(label: str, val: int) -> Text:
                t = Text()
                t.append(f"{label} ", style="grey70")
                for b in range(7, -1, -1):
                    on = (val >> b) & 1
                    if on:
                        t.append("●", style="bold bright_green")
                    else:
                        t.append("○", style="grey35")
                t.append(f"  {val:02X}", style="cyan")
                return t

            def meter(label: str, v: float, lim: float = 2.0) -> Text:
                ratio = max(-1.0, min(1.0, v / lim)) if lim else 0.0
                w = 13
                mid = w // 2
                pos = mid + int(round(ratio * (mid - 1)))
                pos = max(0, min(w - 1, pos))
                t = Text()
                t.append(f"{label:<7}", style="grey70")
                t.append("[", style="grey50")
                for i in range(w):
                    if i == pos:
                        t.append("◆", style="bold yellow")
                    elif i == mid:
                        t.append("┼", style="white")
                    elif (mid < i <= pos) or (pos <= i < mid):
                        t.append("━", style="yellow")
                    else:
                        t.append("·", style="grey30")
                t.append("]", style="grey50")
                t.append(f" {v:+9.3f}", style="white")
                return t

            ft.add_row(Text("Flags", style="bold grey70"))
            ft.add_row(lamps("0x8E", f.flags_8e))
            ft.add_row(Text.assemble(("      ", ""), (flag_names(f.flags_8e, FLAG8E_BITS), "yellow")))
            ft.add_row(lamps("0x8F", f.flags_8f))
            ft.add_row(Text.assemble(("      ", ""), (flag_names(f.flags_8f, FLAG8F_BITS), "yellow")))
            ft.add_row(Text(""))

            ft.add_row(Text("Identified fields (heartbeat ~)", style="bold green"))
            ft.add_row(Text.assemble(("pkt      ", "grey70"), (f.packet_expansion, "cyan")))
            if f.energy_recovery_flag is not None:
                ft.add_row(Text.assemble(("car type ", "grey70"), (f"{f.car_type}", "cyan"),
                                         ("  ER flag ", "grey70"), (f"{f.energy_recovery_flag}", "cyan")))
            if f.throttle_filtered is not None:
                ft.add_row(Text.assemble(("thr/brk  ", "grey70"),
                                         (f"{f.throttle_filtered:3d} / {f.brake_filtered:3d}", "cyan"),
                                         ("  (physical)", "grey50")))
            if f.wheel_rotation_rad is not None:
                ft.add_row(meter("steer rad", f.wheel_rotation_rad, 3.2))
            if f.steering_rate is not None:
                ft.add_row(meter("steer r/s", f.steering_rate, 12.0))
            if f.energy_recovery is not None:
                ft.add_row(meter("ER 0x150", f.energy_recovery, 1.0))
            if f.engine_output is not None:
                ft.add_row(meter("eng 0x154", f.engine_output, 1.5))
            if f.motor_outputs is not None:
                for i, v in enumerate(f.motor_outputs):
                    ft.add_row(meter(f"mot[{i}]", v, 1.0))
            ft.add_row(Text(""))

            ft.add_row(Text("UNKNOWN (undocumented)", style="bold yellow"))
            if f.sway is not None:
                ft.add_row(meter("sway", f.sway, 30.0))
                ft.add_row(meter("heave", f.heave or 0, 15.0))
                ft.add_row(meter("surge", f.surge or 0, 25.0))
            if not f.unknown_floats:
                ft.add_row(Text("none in this packet", style="dim"))
            for k, v in f.unknown_floats.items():
                ft.add_row(meter(k, v, max(1.0, abs(v) * 1.5)))
        self.flags.update(_panel(ft, title="Flags / Unknown", border_style="yellow"))
