from __future__ import annotations

import math
from typing import Optional

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from ...config import AppConfig
from ...core.decoder import TelemetryFrame, TyreWheel, induction_state, gear_ratio_valid, wheel_drive_state, drivetrain_layout, tyre_roles, has_energy_recovery
from ...core.state import RuntimeState


def _panel(*args, **kwargs):
    kwargs.setdefault("box", box.SQUARE)
    return Panel(*args, **kwargs)


def _fmt_lap(ms: int) -> str:
    if ms is None or ms < 0:
        return "--:--.---"
    s = ms / 1000.0
    m = int(s // 60)
    sec = s - m * 60
    return f"{m}:{sec:06.3f}"


def _fmt_lap_s(seconds: float) -> str:
    if seconds <= 0:
        return "--:--.---"
    m = int(seconds // 60)
    sec = seconds - m * 60
    return f"{m}:{sec:06.3f}"


def _gear_text(gear: int) -> str:
    if gear == 0:
        return "R"
    if gear == 15:
        return "N"
    if 1 <= gear <= 8:
        return str(gear)
    return "?"


def _bar(value: float, max_value: float, width: int, color: str = "green") -> Text:
    max_value = max(1e-6, max_value)
    ratio = max(0.0, min(1.0, value / max_value))
    filled = int(round(ratio * width))
    empty = max(0, width - filled)
    t = Text()
    t.append("█" * filled, style=color)
    t.append("░" * empty, style="grey23")
    return t


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _semi_gauge(
    value: float,
    max_value: float,
    width: int = 27,
    height: int = 7,
    color: str = "cyan",
    warn_ratio: float | None = None,
    limit_ratio: float | None = None,
    warn_color: str = "yellow",
    limit_color: str = "red",
    label: str = "",
) -> Text:
    # Semi-circle gauge: angle 180deg (left) -> 0deg (right)
    max_value = max(1e-6, max_value)
    ratio = _clamp01(value / max_value)
    wr = _clamp01(warn_ratio) if warn_ratio is not None else None
    lr = _clamp01(limit_ratio) if limit_ratio is not None else 1.0

    # Build canvas
    grid = [[" " for _ in range(width)] for _ in range(height)]
    style_grid = [["" for _ in range(width)] for _ in range(height)]

    cx = (width - 1) / 2.0
    cy = height - 1
    rx = (width - 2) / 2.0
    ry = max(1.0, height - 1.0)

    # Draw arc and base
    arc_points = []
    steps = 120
    for i in range(steps + 1):
        a = math.pi * (1.0 - i / steps)  # pi -> 0
        r = i / steps
        x = int(round(cx + rx * math.cos(a)))
        y = int(round(cy - ry * math.sin(a)))
        if 0 <= x < width and 0 <= y < height:
            arc_points.append((x, y, r))
            if grid[y][x] == " ":
                grid[y][x] = "·"
                # zone color on arc
                sc = color
                if wr is not None and r >= wr:
                    sc = warn_color
                if lr is not None and r >= lr - 0.03:
                    sc = limit_color
                style_grid[y][x] = f"dim {sc}"

    # base line
    for x in range(1, width - 1):
        y = cy
        if grid[y][x] == " ":
            grid[y][x] = "─"
            style_grid[y][x] = "grey50"
    # base ends
    if width >= 2:
        lx = int(round(cx - rx))
        rxp = int(round(cx + rx))
        if 0 <= lx < width:
            grid[cy][lx] = "╰"
            style_grid[cy][lx] = "grey50"
        if 0 <= rxp < width:
            grid[cy][rxp] = "╯"
            style_grid[cy][rxp] = "grey50"

    # ticks on arc
    for tr in [0.0, 0.25, 0.5, 0.75, 1.0]:
        a = math.pi * (1.0 - tr)
        x = int(round(cx + rx * math.cos(a)))
        y = int(round(cy - ry * math.sin(a)))
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = "•"
            sc = color
            if wr is not None and tr >= wr:
                sc = warn_color
            if lr is not None and tr >= lr - 0.03:
                sc = limit_color
            style_grid[y][x] = f"bold {sc}"

    # needle
    needle_angle = math.pi * (1.0 - ratio)
    n_steps = max(3, height)
    needle_cells = []
    for s in range(1, n_steps + 1):
        rr = s / n_steps
        x = int(round(cx + (rx - 0.5) * rr * math.cos(needle_angle)))
        y = int(round(cy - (ry - 0.3) * rr * math.sin(needle_angle)))
        if 0 <= x < width and 0 <= y < height:
            needle_cells.append((x, y))
    ncolor = color
    if wr is not None and ratio >= wr:
        ncolor = warn_color
    if lr is not None and ratio >= lr - 0.03:
        ncolor = limit_color
    for (x, y) in needle_cells[:-1]:
        ca = math.cos(needle_angle)
        sa = math.sin(needle_angle)
        if abs(sa) >= abs(ca):
            ch = "┃"
        else:
            ch = "━"
        grid[y][x] = ch
        style_grid[y][x] = f"bold {ncolor}"
    if needle_cells:
        x, y = needle_cells[-1]
        grid[y][x] = "●"
        style_grid[y][x] = f"bold {ncolor}"
    # center hub
    ccx = int(round(cx))
    ccy = int(round(cy))
    if 0 <= ccx < width and 0 <= ccy < height:
        grid[ccy][ccx] = "◉"
        style_grid[ccy][ccx] = f"bold {ncolor}"

    out = Text()
    for j in range(height):
        for i in range(width):
            ch = grid[j][i]
            st = style_grid[j][i] or ""
            out.append(ch, style=st)
        if j < height - 1:
            out.append("\n")
    if label:
        out.append("\n")
        pad = max(0, (width - len(label)) // 2)
        out.append(" " * pad)
        out.append(label, style=f"bold {ncolor}")
    return out


def _linear_gauge(
    value: float,
    max_value: float,
    width: int = 31,
    color: str = "green",
    warn: float | None = None,
    limit: float | None = None,
    warn_color: str = "yellow",
    limit_color: str = "red",
    label: str = "",
) -> Text:
    # Straight-line horizontal gauge. No arcs, no angled needles.
    max_value = max(1e-6, max_value)
    ratio = _clamp01(value / max_value)
    filled = int(round(ratio * width))
    warn_pos = int(round(warn / max_value * width)) if warn and warn > 0 else -1
    limit_pos = int(round(limit / max_value * width)) if limit and limit > 0 else -1

    cells = [" "] * (width + 2)
    def put(text: str, pos: int) -> None:
        for i, ch in enumerate(text):
            if 0 <= pos + i < len(cells):
                cells[pos + i] = ch
    put("0", 1)
    mid_txt = f"{max_value / 2.0:.0f}"
    put(mid_txt, 1 + max(0, (width - len(mid_txt)) // 2))
    hi_txt = f"{max_value:.0f}"
    put(hi_txt, 1 + width - len(hi_txt))

    out = Text()
    out.append("".join(cells).rstrip(), style="grey70")
    out.append("\n")
    out.append("├", style="grey50")
    for i in range(width):
        if i == warn_pos:
            out.append("▲", style=f"bold {warn_color}")
        elif i == limit_pos:
            out.append("▼", style=f"bold {limit_color}")
        elif i < filled:
            out.append("━", style=color)
        else:
            out.append("┄", style="grey23")
    out.append("┤", style="grey50")
    if label:
        out.append(f" {label}", style=f"bold {color}")
    return out


def _analog_bar(value: float, max_value: float, width: int, color: str, ticks: list[float] | None = None) -> Text:
    # Meter-like horizontal bar with pointer
    max_value = max(1e-6, max_value)
    ratio = _clamp01(value / max_value)
    width = max(10, width)
    scale = Text()
    # scale markers line
    pos = int(round(ratio * (width - 1)))
    for i in range(width):
        if i == pos:
            scale.append("▲", style=f"bold {color}")
        elif ticks and any(abs(i - int(round(t * (width - 1)))) <= 0 for t in ticks):
            scale.append("┼", style="grey50")
        else:
            scale.append("─", style="grey35")
    scale.append("\n")
    # filled bar
    filled = int(round(ratio * width))
    for i in range(width):
        if i < filled:
            scale.append("█", style=color)
        else:
            scale.append("░", style="grey23")
    return scale


class RpmBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig):
        thr = cfg.thresholds.get("rpm", {})
        colors = cfg.colors.get("rpm", {})
        c_norm = colors.get("normal", "green")
        c_warn = colors.get("warn", "yellow")
        c_lim = colors.get("limit", "red")

        if not frame:
            gauge = _linear_gauge(0, 8000, width=24, color=c_norm, label="0 rpm")
            info = Text(" shift ----   dial ----   scale 0-8000", style="grey70")
            return _panel(Group(gauge, info), title="Tachometer", border_style="cyan")

        shift = float(frame.rev_warning or 0)   # engine max rev / shift point
        dial = float(frame.rev_limiter or 0)    # number engraved on GT7 tachometer (scale marking only)
        if "warn_rpm" in thr:
            shift = float(thr.get("warn_rpm", shift))
        elif "warn_offset" in thr and frame.rev_limiter:
            shift = max(0.0, float(frame.rev_limiter) - float(thr.get("warn_offset", 500)))

        scale_max = dial if dial > 0 else float(thr.get("display_max", 8000.0))
        if scale_max <= 0:
            scale_max = 8000.0
        # RPM can exceed the dial number; widen scale so actual rpm stays visible.
        if frame.rpm > scale_max:
            scale_max = math.ceil(frame.rpm / 500.0) * 500.0

        gauge = _linear_gauge(
            frame.rpm, scale_max, width=24,
            color=c_norm, warn=shift if shift > 0 else None,
            limit=dial if dial > 0 and dial < scale_max else None,
            warn_color=c_warn, limit_color=c_lim,
            label=f"{frame.rpm:5.0f} rpm"
        )
        shift_txt = f"{shift:4.0f}" if shift > 0 else "----"
        dial_txt = f"{dial:4.0f}" if dial > 0 else "----"
        info = Text(f" shift {shift_txt}   dial {dial_txt}   scale 0-{int(scale_max)}", style="grey70")
        return _panel(Group(gauge, info), title="Tachometer", border_style="cyan")


class SpeedBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, cfg: AppConfig):
        speed = frame.speed_kph if frame else 0.0
        top = 320.0
        if frame and frame.est_top_speed and frame.est_top_speed > 0:
            top = max(200.0, min(450.0, float(frame.est_top_speed) * 1.1))
        gauge = _linear_gauge(speed, top, width=20, color="bright_cyan", label=f"{speed:5.1f} km/h")
        lines = [gauge]
        if frame and frame.est_top_speed and frame.est_top_speed > 0:
            # bar showing speed vs estimated top speed
            topv = float(frame.est_top_speed)
            topg = _linear_gauge(speed, topv, width=20, color="bright_blue", label=f"{speed / topv * 100.0:3.0f}%")
            lines.append(Text(f" of est.max {topv} km/h", style="grey70"))
            lines.append(topg)
        return _panel(Group(*lines), title="Speedometer", border_style="bright_cyan")


class PedalsBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, cfg: AppConfig):
        height = 10
        c = cfg.colors.get("pedal", {})
        if not frame:
            thr = brk = clu = 0.0
        else:
            thr = frame.throttle
            brk = frame.brake
            clu = frame.clutch * 100.0 if frame.clutch <= 1.5 else frame.clutch
        cols = [
            ("THR", thr, c.get("throttle", "green")),
            ("BRK", brk, c.get("brake", "red")),
            ("CLU", min(100.0, max(0.0, clu)), c.get("clutch", "blue")),
        ]
        # vertical gauge with tick marks
        lines = []
        for i in range(height):
            level = height - 1 - i
            pct_mark = int(round(level / max(1, height - 1) * 100))
            tick = f"{pct_mark:3d}" if level in (0, height // 2, height - 1) else "   "
            row = [tick]
            for label, val, color in cols:
                filled = int(round(max(0.0, min(1.0, val / 100.0)) * height))
                if level < filled:
                    if level == filled - 1:
                        row.append(f"[bold {color}]▄▄▄▄[/bold {color}]")
                    else:
                        row.append(f"[{color}]████[/{color}]")
                elif level == filled:
                    row.append(f"[{color}]────[/{color}]")
                else:
                    row.append("[grey23]░░░░[/grey23]")
            lines.append(" ".join(row))
        labels = "    " + "  ".join([f"{name:^4}" for name, _, _ in cols])
        vals = "    " + "  ".join([f"{val:3.0f}%" for _, val, _ in cols])
        info = []
        if frame and frame.throttle_filtered is not None:
            raw = frame.throttle_filtered / 255.0 * 100.0
            if raw - frame.throttle > 2.0:
                info.append(Text.assemble(("TCS ", "bold yellow"), (f"in {raw:3.0f}% out {frame.throttle:3.0f}%", "yellow")))
        if frame and frame.brake_filtered is not None:
            raw = frame.brake_filtered / 255.0 * 100.0
            if raw - frame.brake > 2.0:
                info.append(Text.assemble(("ABS ", "bold yellow"), (f"in {raw:3.0f}% out {frame.brake:3.0f}%", "yellow")))
        content = "\n".join(lines + [labels, vals])
        if info:
            content = Group(content, *info)
        return _panel(content, title="Pedals", border_style="magenta")


class LapBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig):
        table = Table.grid(padding=(0, 1))
        if not frame:
            table.add_row("Lap: -/-  Pos: -/-")
            table.add_row("Current: --:--.---")
            table.add_row("Best:    --:--.---")
            table.add_row("Last:    --:--.---")
            table.add_row("Delta:   --")
            return _panel(table, title="Lap / Timing", border_style="green")
        lap_cur = str(frame.current_lap) if frame.current_lap >= 0 else "--"
        lap_tot = str(frame.total_laps) if frame.total_laps >= 0 else "--"
        pos_cur = str(frame.position) if frame.position >= 0 else "--"
        pos_tot = str(frame.total_positions) if frame.total_positions >= 0 else "--"
        table.add_row(f"Lap: {lap_cur}/{lap_tot}  Pos: {pos_cur}/{pos_tot}")
        cur = snap.current_lap_time_s if frame.current_lap > 0 else 0.0
        table.add_row(f"Current: {_fmt_lap_s(cur) if frame.current_lap > 0 else '--:--.---'}")
        table.add_row(f"Best:    {_fmt_lap(frame.best_lap_ms)}")
        table.add_row(f"Last:    {_fmt_lap(frame.last_lap_ms)}")
        delta_text = Text("Delta:   --")
        # Only meaningful once the driver has completed at least one full lap this session.
        if frame.best_lap_ms > 0 and cur > 0 and frame.current_lap > 1:
            delta = cur - (frame.best_lap_ms / 1000.0)
            colors = cfg.colors.get("delta", {})
            style = colors.get("neutral", "white")
            if delta < cfg.thresholds.get("delta", {}).get("improve", -0.001):
                style = colors.get("improve", "green")
            elif delta > cfg.thresholds.get("delta", {}).get("worsen", 0.001):
                style = colors.get("worsen", "red")
            sign = "+" if delta >= 0 else ""
            delta_text = Text(f"Delta:   {sign}{delta:0.3f}s", style=style)
            # delta bar vs best (centered analog indicator)
            max_d = 3.0
            ratio = max(-1.0, min(1.0, delta / max_d))
            width = 21
            mid = width // 2
            bar = Text("         ")
            for i in range(width):
                if i == mid:
                    bar.append("┃", style="white")
                elif (ratio < 0 and i >= mid + int(ratio * mid) and i < mid) or (ratio > 0 and i <= mid + int(ratio * mid) and i > mid):
                    bar.append("█", style=style)
                else:
                    bar.append("·", style="grey35")
            table.add_row(delta_text)
            table.add_row(bar)
        else:
            table.add_row(delta_text)
        return _panel(table, title="Lap / Timing", border_style="green")


def _mini_gauge(label: str, value: float, max_value: float, unit: str, color: str, width: int = 18) -> Text:
    max_value = max(1e-6, max_value)
    ratio = _clamp01(value / max_value)
    filled = int(round(ratio * width))
    pos = min(width - 1, filled)
    t = Text()
    t.append(f"{label:<6}")
    t.append("[", style="grey50")
    for i in range(width):
        if i == pos:
            t.append("▮", style=f"bold {color}")
        elif i < filled:
            t.append("━", style=color)
        else:
            t.append("─", style="grey23")
    t.append("]", style="grey50")
    t.append(f" {value:6.1f}{unit}")
    return t


class VehicleBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig, compact: bool = False):
        if not frame:
            return _panel("No data", title="Vehicle", border_style="yellow")
        g = Table.grid(padding=(0, 0))
        # fuel/charge gauge
        cap = frame.fuel_capacity
        cur = frame.fuel_or_charge
        pct = (cur / cap * 100.0) if cap > 0 else 0.0
        low_pct = float(cfg.thresholds.get("fuel", {}).get("low_percent", 15.0))
        fuel_color = cfg.colors.get("fuel", {}).get("low" if pct <= low_pct else "normal", "green")
        label = "BAT" if frame.is_ev else "FUEL"
        unit = "kWh" if frame.is_ev else "L"
        g.add_row(_mini_gauge(label, pct, 100.0, "%", fuel_color, width=14 if compact else 18))
        g.add_row(Text(f"       {cur:5.1f}/{cap:5.1f} {unit}", style="grey70"))
        if frame.is_ev:
            peak = snap.ev_peak_charge
            soc = (cur / peak * 100.0) if peak > 0 else 0.0
            g.add_row(Text(f"       EV SOC {soc:5.1f}%  peak {peak:5.1f} kWh", style="cyan"))
        # temps & pressure as analog bars
        g.add_row(_mini_gauge("OIL P", frame.oil_pressure_bar, 10.0, "b", "yellow3", width=14 if compact else 18))
        g.add_row(Text(f"RH {frame.ride_height_mm:5.0f} mm", style="grey70"))
        if frame.packet_expansion != "none":
            g.add_row(Text(f"EXT {frame.packet_expansion}  carType {frame.car_type}  ERec {frame.energy_recovery or 0:.2f}", style="grey50"))
            if has_energy_recovery(frame):
                g.add_row(Text(f"  Energy recovery  {frame.energy_recovery or 0:.2f}", style="bright_green"))
        return _panel(g, title="Vehicle", border_style="yellow")


class SessionBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig):
        g = Table.grid(padding=(0, 1))
        if not frame:
            g.add_row(Text("No telemetry", style="dim"))
            return _panel(g, title="Session", border_style="blue")
        g.add_row(Text.assemble(("Car ", "grey70"), (str(frame.car_id), "bold white"), ("  Pkt ", "grey70"), (str(frame.packet_id), "cyan")))
        g.add_row(Text.assemble(("Lap ", "grey70"), (f"{max(0, frame.current_lap)}/{max(0, frame.total_laps)}", "white"), ("  Pos ", "grey70"), (f"{max(0, frame.position)}/{max(0, frame.total_positions)}", "white")))
        g.add_row(Text.assemble(("Time ", "grey70"), (f"{frame.time_on_track_ms/1000.0:,.1f}s", "white")))
        g.add_row(Text.assemble(("Best ", "grey70"), (_fmt_lap(frame.best_lap_ms), "green"), ("  Last ", "grey70"), (_fmt_lap(frame.last_lap_ms), "yellow")))
        return _panel(g, title="Session", border_style="blue")


class DynamicsBlock(Static):
    def render_block(self, frame: TelemetryFrame | None):
        g = Table.grid(padding=(0, 1))
        if not frame:
            g.add_row(Text("No data", style="dim"))
            return _panel(g, title="Dynamics", border_style="green")
        vmax = 120.0
        def cm(label, v, lim, color):
            lim = max(1e-6, lim)
            ratio = max(-1.0, min(1.0, v / lim))
            w = 15
            mid = w // 2
            pos = mid + int(round(ratio * (mid - 1)))
            pos = max(0, min(w - 1, pos))
            t = Text()
            t.append(f"{label:<2}")
            t.append("[", style="grey50")
            for i in range(w):
                if i == pos:
                    t.append("◆", style=f"bold {color}")
                elif i == mid:
                    t.append("┼", style="white")
                elif (mid < i <= pos) or (pos <= i < mid):
                    t.append("━", style=color)
                else:
                    t.append("·", style="grey30")
            t.append("]", style="grey50")
            t.append(f"{v:+7.1f}")
            return t
        g.add_row(Text("Velocity m/s", style="bold grey70"))
        g.add_row(cm("X", frame.velocity_xyz.x, vmax, "cyan"))
        g.add_row(cm("Y", frame.velocity_xyz.y, 40.0, "cyan"))
        g.add_row(cm("Z", frame.velocity_xyz.z, vmax, "cyan"))
        g.add_row(Text("Angular r/s", style="bold grey70"))
        g.add_row(cm("P", frame.angular_velocity_xyz.x, 5.0, "orange3"))
        g.add_row(cm("Y", frame.angular_velocity_xyz.y, 5.0, "orange3"))
        g.add_row(cm("R", frame.angular_velocity_xyz.z, 5.0, "orange3"))
        g.add_row(Text.assemble(("N/S ", "grey70"), (f"{frame.north_south:+.3f}", "white")))
        return _panel(g, title="Dynamics", border_style="green")


class BoostBlock(Static):
    """Dedicated boost / supercharger pressure gauge."""

    def render_block(self, frame: TelemetryFrame | None, cfg: AppConfig):
        if not frame or not frame.has_turbo:
            return _panel(Text("N/A (no turbo)", style="grey50"), title="Boost", border_style="cyan")
        max_kpa = float(cfg.thresholds.get("boost", {}).get("max_kpa", 200.0))
        if max_kpa <= 0:
            max_kpa = 200.0
        val = max(0.0, frame.boost_kpa)
        gauge = _linear_gauge(
            val, max_kpa, width=31, color="cyan",
            label=f"{frame.boost_kpa:+7.1f} kPa"
        )
        info = Text(
            f" scale 0-{int(max_kpa)} kPa   {frame.boost_kpa / 100.0:+.2f} bar",
            style="grey70",
        )
        return _panel(Group(gauge, info), title="Boost", border_style="cyan")


class TyreSummaryBlock(Static):
    """Compact 4-wheel tyre overview for the dashboard (wide layout only)."""

    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig):
        g = Table.grid(padding=(0, 1))
        if not frame or not frame.tyres:
            g.add_row(Text("No tyre data", style="dim"))
            return _panel(g, title="Tyres", border_style="blue")
        th = cfg.thresholds.get("tyre_temp", {})
        colors = cfg.colors.get("tyre_temp", {})
        cold = float(th.get("cold", 60.0))
        opt_min = float(th.get("optimal_min", 80.0))
        opt_max = float(th.get("optimal_max", 100.0))
        hot = float(th.get("hot", 110.0))

        def temp_style(t: float) -> str:
            if t < cold:
                return colors.get("cold", "cyan")
            if opt_min <= t <= opt_max:
                return colors.get("optimal", "green")
            if t >= hot:
                return colors.get("hot", "red")
            return colors.get("warm", "yellow")

        order = ("FL", "FR", "RL", "RR")
        roles = tyre_roles(frame, snap.g_lateral, snap.g_longitudinal)
        for key in order:
            w = frame.tyres.get(key)
            if not w:
                g.add_row(Text.assemble((f"{key}  ", "bold grey50"), ("no data", "dim")))
                continue
            tcol = temp_style(w.temp_c)
            role = roles.get(key, "")
            rstyle = "bold green" if "DRV" in role or "GRIP" in role else ("bold red" if "BRK" in role else "grey70")
            g.add_row(Text.assemble(
                (f"{key}  ", "bold white"),
                (f"{w.temp_c:6.1f}°C", f"bold {tcol}"),
                ("  ", "grey50"), (f"{role:>12}", rstyle),
            ))
        g.add_row(Text.assemble(("Layout ", "grey70"), (drivetrain_layout(frame), "bold cyan")))
        return _panel(g, title="Tyres", border_style="blue")


class GSensorBlock(Static):
    """G sensor display: live acceleration plus peak-hold lateral/longitudinal G."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._peak_lat = 0.0
        self._peak_long = 0.0

    def render_block(self, snap: RuntimeState, cfg: AppConfig):
        lat = snap.g_lateral
        lng = snap.g_longitudinal
        vert = snap.g_vertical
        self._peak_lat = max(self._peak_lat, abs(lat))
        self._peak_long = max(self._peak_long, abs(lng))

        # 2-axis G meter: center (+), dot shows current G, scaled to +/-2G
        def plane(label: str, value: float, peak: float, pos_label: str, neg_label: str) -> Text:
            lim = 2.0
            ratio = max(-1.0, min(1.0, value / lim))
            w = 17
            mid = w // 2
            pos = mid + int(round(ratio * (mid - 1)))
            pos = max(0, min(w - 1, pos))
            t = Text()
            t.append(f"{label} ")
            t.append("[", style="grey50")
            for i in range(w):
                if i == pos:
                    t.append("●", style="bold bright_yellow")
                elif i == mid:
                    t.append("┼", style="white")
                elif (mid < i <= pos) or (pos <= i < mid):
                    t.append("━", style="bright_yellow")
                else:
                    t.append("·", style="grey30")
            t.append("]", style="grey50")
            t.append(f" {value:+.2f}G", style="bright_yellow")
            t.append(f"  peak {peak:.2f}G", style="grey70")
            return t

        g = Table.grid(padding=(0, 0))
        g.add_row(plane("LAT", lat, self._peak_lat, "R", "L"))
        g.add_row(plane("LNG", lng, self._peak_long, "ACC", "BRK"))
        g.add_row(Text(f"VERT {vert:+.2f}G", style="grey70"))
        return _panel(g, title="G Sensor", border_style="bright_yellow")


class LayoutStatsBlock(Static):
    """Drivetrain layout statistics - reveals on-demand AWD conditions."""

    def render_block(self, snap: RuntimeState, cfg: AppConfig):
        g = Table.grid(padding=(0, 1))
        total = snap.layout_total
        if total <= 0:
            g.add_row(Text("No data", style="dim"))
            return _panel(g, title="Drive Layout", border_style="cyan")
        order = ("AWD", "RWD", "FWD", "--")
        for lay in order:
            cnt = snap.layout_counts.get(lay, 0)
            if cnt == 0:
                continue
            pct = cnt / total * 100.0
            thr = snap.layout_throttle.get(lay, 0.0) / cnt
            spd = snap.layout_speed.get(lay, 0.0) / cnt
            color = {"AWD": "bold bright_cyan", "RWD": "bold yellow", "FWD": "bold magenta"}.get(lay, "grey70")
            bar = _bar(pct, 100.0, 10, color.strip())
            g.add_row(Text.assemble(
                (f"{lay:4s}", color), (" ", ""), bar,
                (f" {pct:5.1f}%", color),
                (f"  thr{thr:4.0f}%", "grey70"),
                (f" {spd:5.0f}kph", "grey70"),
            ))
        g.add_row(Text(f" samples {total}", style="grey50"))
        return _panel(g, title="Drive Layout", border_style="cyan")


class HVBatteryBlock(Static):
    """Hybrid energy flow: + assist (battery discharge), - regeneration (charge)."""

    def render_block(self, frame: TelemetryFrame | None):
        if not frame or frame.energy_recovery is None:
            return _panel(Text("No HV data (needs ~ heartbeat)", style="dim"), title="HV Battery", border_style="green")
        if frame.energy_recovery_flag == 0:
            g = Table.grid(padding=(0, 0))
            g.add_row(Text("No energy recovery data", style="dim"))
            g.add_row(Text("(car does not send ER)", style="grey50"))
            return _panel(g, title="HV Battery", border_style="green")
        er = max(-1.0, min(1.0, frame.energy_recovery))
        # center meter: left=regen(charge), right=assist(discharge)
        w = 21
        mid = w // 2
        pos = mid + int(round(er * (mid - 1)))
        pos = max(0, min(w - 1, pos))
        t = Text()
        t.append("[", style="grey50")
        for i in range(w):
            if i == pos:
                t.append("●", style="bold bright_green" if er > 0 else "bold bright_cyan")
            elif i == mid:
                t.append("┼", style="white")
            elif (mid < i <= pos) or (pos <= i < mid):
                t.append("━", style="bright_green" if er > 0 else "bright_cyan")
            else:
                t.append("·", style="grey30")
        t.append("]", style="grey50")
        label = "ASSIST" if er > 0.05 else ("REGEN" if er < -0.05 else "idle")
        style = "bold bright_green" if er > 0.05 else ("bold bright_cyan" if er < -0.05 else "grey70")
        t.append(f" {label} {er:+.2f}", style=style)
        g = Table.grid(padding=(0, 0))
        g.add_row(t)
        g.add_row(Text("  REGEN <--|--> ASSIST (battery discharge)", style="grey50"))
        return _panel(g, title="HV Battery", border_style="green")


class DashboardPane(Container):
    def __init__(self, config: AppConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.gear_digits = Static("N")
        self.gear_info = Static("", classes="title")
        self.rpm_block = RpmBlock()
        self.speed_block = SpeedBlock()
        self.pedals_block = PedalsBlock()
        self.lap_block = LapBlock()
        self.vehicle_block = VehicleBlock()
        self.session_block = SessionBlock(classes="wide-only")
        self.tyre_summary = TyreSummaryBlock(classes="wide-only")
        self.boost_block = BoostBlock()
        self.hv_battery = HVBatteryBlock()
        self.gsensor_block = GSensorBlock(classes="wide-only")
        self.layout_stats = LayoutStatsBlock(classes="wide-only")

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical():
                with Horizontal():
                    yield self.rpm_block
                    yield self.speed_block
                with Horizontal():
                    with Vertical(classes="gear-cluster"):
                        yield Static("GEAR", classes="title")
                        yield self.gear_digits
                        yield self.gear_info
                    yield self.lap_block
                yield self.session_block
                yield self.layout_stats
            with Vertical():
                yield self.pedals_block
                yield self.vehicle_block
                yield self.boost_block
                yield self.hv_battery
                yield self.gsensor_block
                yield self.tyre_summary

    def update_view(self, snap: RuntimeState, cfg: AppConfig, layout: str = "wide") -> None:
        compact = layout == "compact"
        frame = snap.frame
        if frame:
            gear = _gear_text(frame.gear)
            self.gear_digits.update(gear)
            sug = frame.suggested_gear
            sug_text = _gear_text(sug) if sug <= 14 else "-"
            info = Text(f"Suggested: {sug_text}")
            if sug_text != "-" and sug_text != gear and sug > 0 and sug != frame.gear:
                info.stylize("bold yellow")
            self.gear_info.update(info)
        else:
            self.gear_digits.update("N")
            self.gear_info.update("Suggested: -")
        self.rpm_block.update(self.rpm_block.render_block(frame, snap, cfg))
        self.speed_block.update(self.speed_block.render_block(frame, cfg))
        self.pedals_block.update(self.pedals_block.render_block(frame, cfg))
        self.lap_block.update(self.lap_block.render_block(frame, snap, cfg))
        self.vehicle_block.update(self.vehicle_block.render_block(frame, snap, cfg, compact=compact))
        self.session_block.update(self.session_block.render_block(frame, snap, cfg))
        self.tyre_summary.update(self.tyre_summary.render_block(frame, snap, cfg))
        self.boost_block.update(self.boost_block.render_block(frame, cfg))
        self.hv_battery.update(self.hv_battery.render_block(frame))
        self.gsensor_block.update(self.gsensor_block.render_block(snap, cfg))
        self.layout_stats.update(self.layout_stats.render_block(snap, cfg))
