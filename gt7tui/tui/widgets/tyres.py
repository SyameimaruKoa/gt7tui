from __future__ import annotations

import math

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from ...config import AppConfig
from ...core.decoder import TyreWheel
from ...core.state import RuntimeState


def _temp_style(temp: float, cfg: AppConfig) -> str:
    th = cfg.thresholds.get("tyre_temp", {})
    colors = cfg.colors.get("tyre_temp", {})
    cold = float(th.get("cold", 60.0))
    opt_min = float(th.get("optimal_min", 80.0))
    opt_max = float(th.get("optimal_max", 100.0))
    hot = float(th.get("hot", 110.0))
    if temp < cold:
        return colors.get("cold", "cyan")
    if opt_min <= temp <= opt_max:
        return colors.get("optimal", "green")
    if temp >= hot:
        return colors.get("hot", "red")
    return colors.get("warm", "yellow")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _temp_gauge(temp: float, cfg: AppConfig, width: int = 18) -> Text:
    # Analog thermometer strip: 40..120 C
    lo, hi = 40.0, 120.0
    ratio = _clamp01((temp - lo) / (hi - lo))
    th = cfg.thresholds.get("tyre_temp", {})
    cold = float(th.get("cold", 60.0))
    opt_min = float(th.get("optimal_min", 80.0))
    opt_max = float(th.get("optimal_max", 100.0))
    hot = float(th.get("hot", 110.0))

    def zone_style(v: float) -> str:
        return _temp_style(v, cfg)

    t = Text()
    t.append("40° ", style="grey50")
    for i in range(width):
        v = lo + (i + 0.5) / width * (hi - lo)
        pos = ratio * width
        st = zone_style(v)
        if abs(i + 0.5 - pos) < 0.6:
            t.append("▮", style=f"bold white on {st}")
        elif i < pos:
            t.append("━", style=st)
        else:
            t.append("─", style="grey23")
    t.append(" 120°", style="grey50")
    return t


def _slip_meter(slip: float | None, cfg: AppConfig, width: int = 17) -> Text:
    # Centered meter around 1.00 (grip). Left = low ratio, Right = high slip.
    t = Text()
    if slip is None:
        t.append("Slip  ")
        t.append("[" + "·" * width + "]  --  ", style="grey50")
        return t
    warn = float(cfg.thresholds.get("slip", {}).get("warn_ratio", 1.10))
    colors = cfg.colors.get("slip", {})
    if slip >= warn + 0.1:
        style = colors.get("high", "red")
    elif slip >= warn:
        style = colors.get("warn", "yellow")
    else:
        style = colors.get("normal", "green")

    # map 0.80 .. 1.40 to width
    lo, hi = 0.80, 1.40
    ratio = _clamp01((slip - lo) / (hi - lo))
    center = _clamp01((1.00 - lo) / (hi - lo))
    pos = int(round(ratio * (width - 1)))
    cpos = int(round(center * (width - 1)))
    t.append("Slip  ")
    t.append("[", style="grey50")
    for i in range(width):
        if i == pos:
            t.append("▲", style=f"bold {style}")
        elif i == cpos:
            t.append("│", style="white")
        elif (cpos < i <= pos) or (pos <= i < cpos):
            t.append("━", style=style)
        else:
            t.append("·", style="grey30")
    t.append("]", style="grey50")
    t.append(f" {slip:4.2f}", style=style)
    return t


def _h_meter(label: str, value: float, vmax: float, unit: str, color: str, width: int = 14) -> Text:
    vmax = max(1e-6, vmax)
    ratio = _clamp01(value / vmax)
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
    t.append(f" {value:6.1f}{unit}")
    return t


def _suspension_gauge(value: float, width: int = 18) -> Text:
    # Suspension travel shown as centered indicator (can be +/- around nominal)
    # Value range roughly -0.15..0.15 in typical data; normalize around 0.
    lim = 0.12
    ratio = max(-1.0, min(1.0, value / lim))
    mid = width // 2
    pos = mid + int(round(ratio * (mid - 1)))
    pos = max(0, min(width - 1, pos))
    t = Text()
    t.append("Susp  ")
    t.append("[", style="grey50")
    for i in range(width):
        if i == pos:
            t.append("◆", style="bold bright_magenta")
        elif i == mid:
            t.append("┼", style="white")
        elif (mid < i <= pos) or (pos <= i < mid):
            t.append("━", style="magenta")
        else:
            t.append("·", style="grey30")
    t.append("]", style="grey50")
    t.append(f" {value:+.3f}", style="bright_magenta")
    return t


def _tyre_icon(temp: float, cfg: AppConfig) -> Text:
    style = _temp_style(temp, cfg)
    # simple tyre block visual with tread
    t = Text()
    t.append("  ┌───────┐\n", style=style)
    t.append("  │▓▓▓▓▓▓▓│\n", style=style)
    t.append("  │▓█████▓│\n", style=style)
    t.append("  │▓▓▓▓▓▓▓│\n", style=style)
    t.append("  └───────┘", style=style)
    return t


def _wheel_panel(name: str, wheel: TyreWheel | None, cfg: AppConfig) -> Panel:
    if wheel is None:
        return Panel(Text("No data", style="dim"), title=name, border_style="blue")
    tstyle = _temp_style(wheel.temp_c, cfg)
    lines = []
    # top: icon + big temp
    head = Table.grid(padding=(0, 1))
    head.add_row(_tyre_icon(wheel.temp_c, cfg), Text.assemble(("\nTEMP\n", "grey70"), (f"{wheel.temp_c:6.1f}°C", f"bold {tstyle}")))
    lines.append(head)
    lines.append(_temp_gauge(wheel.temp_c, cfg))
    lines.append(_slip_meter(wheel.slip_ratio, cfg))
    lines.append(_h_meter("Spd", wheel.speed_kph, 400.0, "k", "bright_cyan", width=14))
    lines.append(_h_meter("Dia", wheel.diameter_m * 200.0, 100.0, "c", "bright_blue", width=14))
    lines.append(_suspension_gauge(wheel.suspension))
    return Panel(Group(*lines), title=name, border_style="blue")


class TyresPane(Container):
    def __init__(self, config: AppConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.fl = Static()
        self.fr = Static()
        self.rl = Static()
        self.rr = Static()
        self.summary = Static()

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield self.fl
                yield self.fr
            yield self.summary
            with Horizontal():
                yield self.rl
                yield self.rr

    def update_view(self, snap: RuntimeState, cfg: AppConfig) -> None:
        frame = snap.frame
        tyres = frame.tyres if frame else {}
        fl = tyres.get("FL")
        fr = tyres.get("FR")
        rl = tyres.get("RL")
        rr = tyres.get("RR")
        self.fl.update(_wheel_panel("Front Left (FL)", fl, cfg))
        self.fr.update(_wheel_panel("Front Right (FR)", fr, cfg))
        self.rl.update(_wheel_panel("Rear Left (RL)", rl, cfg))
        self.rr.update(_wheel_panel("Rear Right (RR)", rr, cfg))
        if frame and tyres:
            def node(w: TyreWheel | None, name: str) -> Text:
                if not w:
                    return Text(f"[{name}\n --° ]", style="dim")
                st = _temp_style(w.temp_c, cfg)
                return Text.assemble((f"[{name}]", f"bold {st}"), (f"\n{w.temp_c:4.0f}°", st), (f"\n{(w.slip_ratio or 0):.2f} ", st if w.slip_ratio else "dim"))

            top = Table.grid(padding=(0, 2))
            top.add_column(justify="center")
            top.add_column(justify="center")
            top.add_column(justify="center")
            # car body diagram
            body = Text()
            body.append("   ╭───┬───╮\n", style="grey70")
            body.append("   │   │   │\n", style="grey70")
            body.append("   │  ▲CAR │\n", style="bold white")
            body.append("   │   │   │\n", style="grey70")
            body.append("   ╰───┴───╯", style="grey70")
            top.add_row(node(fl, "FL"), body, node(fr, "FR"))
            bottom = Table.grid(padding=(0, 2))
            bottom.add_column(justify="center")
            bottom.add_column(justify="center")
            bottom.add_column(justify="center")
            axle = Text("━━━━━\nfront / rear\n━━━━━", style="grey50", justify="center")
            bottom.add_row(node(rl, "RL"), axle, node(rr, "RR"))
            avg_temp = sum(w.temp_c for w in tyres.values() if w) / max(1, len(tyres))
            info = Text.assemble(("Avg tyre temp: ", "grey70"), (f"{avg_temp:5.1f}°C", f"bold {_temp_style(avg_temp, cfg)}"))
            self.summary.update(Panel(Group(top, Text(""), bottom, Text(""), info), title="Tyre Layout", border_style="grey50"))
        else:
            self.summary.update(Panel("No data", title="Tyre Layout", border_style="grey50"))
