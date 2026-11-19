from __future__ import annotations

import math
from typing import Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Digits, Static

from ...config import AppConfig
from ...core.decoder import TelemetryFrame
from ...core.state import RuntimeState


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


def _rpm_bar(rpm: float, warn: float, limit: float, width: int, colors: dict) -> Text:
    limit = max(limit, 1.0)
    ratio = max(0.0, min(1.0, rpm / limit))
    filled = int(round(ratio * width))
    warn_ratio = max(0.0, min(1.0, warn / limit)) if warn > 0 else 0.9
    warn_idx = int(round(warn_ratio * width))
    t = Text()
    c_norm = colors.get("rpm", {}).get("normal", "green")
    c_warn = colors.get("rpm", {}).get("warn", "yellow")
    c_lim = colors.get("rpm", {}).get("limit", "red")
    for i in range(width):
        ch = "█" if i < filled else "░"
        if i < filled:
            if limit > 0 and (i / max(1, width)) >= 0.97:
                style = c_lim
            elif i >= warn_idx:
                style = c_warn
            else:
                style = c_norm
        else:
            style = "grey23"
        t.append(ch, style=style)
    return t


def _vbar(value: float, max_value: float, height: int, color: str) -> list[str]:
    max_value = max(1e-6, max_value)
    ratio = max(0.0, min(1.0, value / max_value))
    filled = int(round(ratio * height))
    lines = []
    for i in range(height):
        level = height - 1 - i
        if level < filled:
            lines.append(f"[{color}]██[/{color}]")
        else:
            lines.append("[grey23]░░[/grey23]")
    return lines


class RpmBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig):
        width = 40
        if not frame:
            t = Text("RPM: --\n")
            t.append(_bar(0, 1, width, "grey23"))
            return Panel(t, title="RPM", border_style="cyan")
        warn = float(frame.rev_warning or 0)
        limit = float(frame.rev_limiter or 0)
        if limit <= 0:
            limit = max(8000.0, frame.rpm * 1.2, 1.0)
        if warn <= 0:
            warn = max(0.0, limit - 500.0)
        thr = cfg.thresholds.get("rpm", {})
        if "warn_rpm" in thr:
            warn = float(thr.get("warn_rpm", warn))
        elif "warn_offset" in thr and frame.rev_limiter:
            warn = max(0.0, float(frame.rev_limiter) - float(thr.get("warn_offset", 500)))
        bar = _rpm_bar(frame.rpm, warn, limit, width, cfg.colors)
        t = Text()
        t.append(f"{frame.rpm:6.0f} rpm", style="bold")
        t.append(f"   warn {warn:4.0f}  lim {limit:4.0f}\n")
        t.append_text(bar)
        return Panel(t, title="RPM / Tachometer", border_style="cyan")


class PedalsBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, cfg: AppConfig):
        height = 8
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
        lines = []
        for i in range(height):
            row = []
            for label, val, color in cols:
                filled = int(round(max(0.0, min(1.0, val / 100.0)) * height))
                level = height - 1 - i
                if level < filled:
                    row.append(f"[{color}]████[/{color}]")
                else:
                    row.append("[grey23]░░░░[/grey23]")
            lines.append("  ".join(row))
        # labels
        labels = "  ".join([f"{name:^4}" for name, _, _ in cols])
        vals = "  ".join([f"{val:3.0f}%" for _, val, _ in cols])
        content = "\n".join(lines + [labels, vals])
        return Panel(content, title="Pedals", border_style="magenta")


class LapBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, snap: RuntimeState, cfg: AppConfig):
        table = Table.grid(padding=(0, 1))
        if not frame:
            table.add_row("Lap: -/-  Pos: -/-")
            table.add_row("Current: --:--.---")
            table.add_row("Best:    --:--.---")
            table.add_row("Last:    --:--.---")
            table.add_row("Delta:   --")
            return Panel(table, title="Lap / Timing", border_style="green")
        table.add_row(f"Lap: {frame.current_lap}/{frame.total_laps}  Pos: {frame.position}/{frame.total_positions}")
        cur = snap.current_lap_time_s
        table.add_row(f"Current: {_fmt_lap_s(cur)}")
        table.add_row(f"Best:    {_fmt_lap(frame.best_lap_ms)}")
        table.add_row(f"Last:    {_fmt_lap(frame.last_lap_ms)}")
        delta_text = Text("Delta:   --")
        if frame.best_lap_ms > 0 and cur > 0:
            delta = cur - (frame.best_lap_ms / 1000.0)
            colors = cfg.colors.get("delta", {})
            style = colors.get("neutral", "white")
            if delta < cfg.thresholds.get("delta", {}).get("improve", -0.001):
                style = colors.get("improve", "green")
            elif delta > cfg.thresholds.get("delta", {}).get("worsen", 0.001):
                style = colors.get("worsen", "red")
            sign = "+" if delta >= 0 else ""
            delta_text = Text(f"Delta:   {sign}{delta:0.3f}s", style=style)
            # delta bar vs best
            max_d = 3.0
            ratio = max(-1.0, min(1.0, delta / max_d))
            width = 20
            mid = width // 2
            bar = ["·"] * width
            idx = mid + int(ratio * (width // 2 - 1))
            idx = max(0, min(width - 1, idx))
            for i in range(min(mid, idx), max(mid, idx) + 1):
                bar[i] = "█"
            bar[mid] = "|"
            table.add_row(delta_text)
            table.add_row(Text("         " + "".join(bar), style=style))
        else:
            table.add_row(delta_text)
        return Panel(table, title="Lap / Timing", border_style="green")


class VehicleBlock(Static):
    def render_block(self, frame: TelemetryFrame | None, cfg: AppConfig):
        if not frame:
            return Panel("No data", title="Vehicle", border_style="yellow")
        g = Table.grid(padding=(0, 1))
        # fuel/charge
        cap = frame.fuel_capacity
        cur = frame.fuel_or_charge
        pct = (cur / cap * 100.0) if cap > 0 else 0.0
        low_pct = float(cfg.thresholds.get("fuel", {}).get("low_percent", 15.0))
        fuel_color = cfg.colors.get("fuel", {}).get("low" if pct <= low_pct else "normal", "green")
        label = "Battery" if frame.is_ev else "Fuel"
        unit = "kWh" if frame.is_ev else "L"
        g.add_row(Text(f"{label}: {cur:5.1f}/{cap:5.1f}{unit} ({pct:4.1f}%)", style=fuel_color))
        g.add_row(_bar(pct, 100.0, 30, fuel_color))
        # boost
        if frame.has_turbo:
            max_boost = float(cfg.thresholds.get("boost", {}).get("max_kpa", 200.0))
            g.add_row(f"Boost: {frame.boost_kpa:6.1f} kPa")
            g.add_row(_bar(max(0.0, frame.boost_kpa), max_boost, 30, "cyan"))
        else:
            g.add_row("Boost: N/A")
            g.add_row(_bar(0, 1, 30, "grey23"))
        g.add_row(f"Oil: {frame.oil_temp_c:5.1f}°C  Water: {frame.water_temp_c:5.1f}°C")
        g.add_row(f"OilP: {frame.oil_pressure_bar:4.2f} bar  RH: {frame.ride_height_mm:5.0f} mm")
        return Panel(g, title="Vehicle", border_style="yellow")


class DashboardPane(Container):
    def __init__(self, config: AppConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.gear_digits = Digits("N")
        self.speed_digits = Digits("0")
        self.gear_info = Static("", classes="title")
        self.rpm_block = RpmBlock()
        self.pedals_block = PedalsBlock()
        self.lap_block = LapBlock()
        self.vehicle_block = VehicleBlock()

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical():
                yield self.rpm_block
                with Horizontal():
                    with Vertical():
                        yield Static("GEAR", classes="title")
                        yield self.gear_digits
                        yield self.gear_info
                    with Vertical():
                        yield Static("SPEED km/h", classes="title")
                        yield self.speed_digits
                yield self.lap_block
            with Vertical():
                yield self.pedals_block
                yield self.vehicle_block

    def update_view(self, snap: RuntimeState, cfg: AppConfig) -> None:
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
            self.speed_digits.update(f"{frame.speed_kph:3.0f}")
        else:
            self.gear_digits.update("N")
            self.speed_digits.update("0")
            self.gear_info.update("Suggested: -")
        self.rpm_block.update(self.rpm_block.render_block(frame, snap, cfg))
        self.pedals_block.update(self.pedals_block.render_block(frame, cfg))
        self.lap_block.update(self.lap_block.render_block(frame, snap, cfg))
        self.vehicle_block.update(self.vehicle_block.render_block(frame, cfg))
