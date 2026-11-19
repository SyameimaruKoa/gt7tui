from __future__ import annotations

import time

from rich.text import Text
from textual.widgets import Static

from ...config import AppConfig
from ...core.state import RuntimeState


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class StatusBar(Static):
    def render_text(self, snap: RuntimeState, cfg: AppConfig) -> Text:
        now = time.time()
        age = (now - snap.last_packet_time) if snap.last_packet_time > 0 else None
        if snap.connected and age is not None and age < max(2.0, cfg.timeout):
            status = "RECV"
            style = cfg.colors.get("status", {}).get("ok", "green")
        elif cfg.mode == "demo" and snap.frame is not None:
            status = "DEMO"
            style = cfg.colors.get("status", {}).get("ok", "green")
        elif snap.last_error:
            status = "ERROR"
            style = cfg.colors.get("status", {}).get("error", "red")
        else:
            status = "WAIT"
            style = cfg.colors.get("status", {}).get("waiting", "yellow")

        t = Text()
        # connection lamp
        lamp = "●" if status in ("RECV", "DEMO") else ("◐" if status == "WAIT" else "◉")
        t.append(f" {lamp} {status} ", style=f"bold white on {style}")

        # mode/source
        t.append(" SRC ", style="grey50")
        t.append(f"{snap.source}", style="bold cyan")
        if cfg.ps_ip:
            t.append(f" {cfg.ps_ip}", style="grey70")

        # bind/ports
        t.append(f"  UDP {cfg.bind}:{cfg.recv_port}", style="grey70")

        # packet id indicator
        t.append("  PKT ", style="grey50")
        pkt = snap.last_packet_id if snap.last_packet_id >= 0 else None
        t.append(f"{pkt if pkt is not None else '----'}", style="bold white")

        # rx/dec/drop as mini meters
        t.append("  RX ", style="grey50")
        t.append(f"{snap.packets_received}", style="green")
        t.append(" DEC ", style="grey50")
        t.append(f"{snap.packets_decoded}", style="bright_green")
        t.append(" DROP ", style="grey50")
        drop_style = "red" if snap.packets_dropped > 0 else "grey70"
        t.append(f"{snap.packets_dropped}", style=drop_style)

        # signal freshness meter (analog age)
        if age is not None:
            # 0s fresh -> full, timeout -> empty
            max_age = max(0.5, float(cfg.timeout))
            freshness = _clamp01(1.0 - age / max_age)
            w = 10
            filled = int(round(freshness * w))
            t.append("  SIG ", style="grey50")
            t.append("[", style="grey50")
            sig_color = "green" if freshness > 0.6 else ("yellow" if freshness > 0.25 else "red")
            for i in range(w):
                if i < filled:
                    t.append("█", style=sig_color)
                else:
                    t.append("░", style="grey23")
            t.append("]", style="grey50")
            t.append(f" {age:0.2f}s", style=sig_color)
        else:
            t.append("  SIG ", style="grey50")
            t.append("[░░░░░░░░░░] --", style="grey35")

        # activity pips based on recent connection
        t.append("  ")
        if status == "RECV":
            t.append("▁▃▅▇", style="bold green")
        elif status == "DEMO":
            t.append("▁▃▅▇", style="bold cyan")
        elif status == "WAIT":
            t.append("▁▁▃▁", style="yellow")
        else:
            t.append("▁▁▁▁", style="red")

        if snap.last_error:
            err = snap.last_error.replace("\n", " ")[:50]
            t.append(f"  err: {err}", style="red")
        return t

    def update_view(self, snap: RuntimeState, cfg: AppConfig) -> None:
        self.update(self.render_text(snap, cfg))
