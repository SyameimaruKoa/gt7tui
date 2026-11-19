from __future__ import annotations

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


def _temp_bar(temp: float, cfg: AppConfig, width: int = 12) -> Text:
    # scale 40..120
    lo, hi = 40.0, 120.0
    ratio = max(0.0, min(1.0, (temp - lo) / (hi - lo)))
    filled = int(round(ratio * width))
    t = Text()
    style = _temp_style(temp, cfg)
    t.append("█" * filled, style=style)
    t.append("░" * (width - filled), style="grey23")
    return t


def _slip_text(slip: float | None, cfg: AppConfig) -> Text:
    if slip is None:
        return Text(" slip:   --  ", style="grey50")
    warn = float(cfg.thresholds.get("slip", {}).get("warn_ratio", 1.10))
    colors = cfg.colors.get("slip", {})
    if slip >= warn + 0.1:
        style = colors.get("high", "red")
    elif slip >= warn:
        style = colors.get("warn", "yellow")
    else:
        style = colors.get("normal", "green")
    return Text(f" slip:{slip:6.2f} ", style=style)


def _wheel_panel(name: str, wheel: TyreWheel | None, cfg: AppConfig) -> Panel:
    if wheel is None:
        return Panel("No data", title=name, border_style="blue")
    g = Table.grid(padding=(0, 1))
    tstyle = _temp_style(wheel.temp_c, cfg)
    g.add_row(Text(f"Temp {wheel.temp_c:6.1f}°C", style=tstyle))
    g.add_row(_temp_bar(wheel.temp_c, cfg))
    g.add_row(_slip_text(wheel.slip_ratio, cfg))
    g.add_row(f"Speed {wheel.speed_kph:6.1f} km/h")
    g.add_row(f"Diam  {wheel.diameter_m * 200.0:6.1f} cm")
    g.add_row(f"Susp  {wheel.suspension:6.3f}")
    return Panel(g, title=name, border_style="blue")


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
        self.fl.update(_wheel_panel("Front Left (FL)", tyres.get("FL"), cfg))
        self.fr.update(_wheel_panel("Front Right (FR)", tyres.get("FR"), cfg))
        self.rl.update(_wheel_panel("Rear Left (RL)", tyres.get("RL"), cfg))
        self.rr.update(_wheel_panel("Rear Right (RR)", tyres.get("RR"), cfg))
        if frame:
            # simple car layout indicator
            txt = Text()
            txt.append("        [front]\n", style="bold")
            txt.append("      FL     FR\n")
            txt.append("       \\   /\n")
            txt.append("        [=]\n")
            txt.append("       /   \\\n")
            txt.append("      RL     RR\n")
            txt.append("        [rear]\n", style="bold")
            self.summary.update(Panel(txt, title="Tyre Layout", border_style="grey50"))
        else:
            self.summary.update(Panel("No data", title="Tyre Layout", border_style="grey50"))
