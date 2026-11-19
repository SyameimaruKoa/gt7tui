from __future__ import annotations

import time

from rich.text import Text
from textual.widgets import Static

from ...config import AppConfig
from ...core.state import RuntimeState


class StatusBar(Static):
    def update_view(self, snap: RuntimeState, cfg: AppConfig) -> None:
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

        parts = []
        t = Text()
        t.append(f" {status} ", style=f"bold white on {style}")
        t.append(f" mode={snap.source} ")
        if cfg.ps_ip:
            t.append(f"ps={cfg.ps_ip} ")
        t.append(f"bind={cfg.bind}:{cfg.recv_port} ")
        t.append(f"pkt={snap.last_packet_id if snap.last_packet_id >= 0 else '-'} ")
        t.append(f"rx={snap.packets_received} dec={snap.packets_decoded} drop={snap.packets_dropped} ")
        if age is not None:
            t.append(f"age={age:0.1f}s ")
        if snap.last_error:
            err = snap.last_error.replace("\n", " ")[:60]
            t.append(f"err={err}", style="red")
        self.update(t)
