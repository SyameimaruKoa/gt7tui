from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("gt7tui.json")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def default_config() -> dict[str, Any]:
    return {
        "network": {
            "bind": "0.0.0.0",
            "recv_port": 33740,
            "send_port": 33739,
            "timeout": 10.0,
            "heartbeat_interval_packets": 100,
            "heartbeat": "~",
            "drive_layouts": {
                "3572": "AWD",
                "1537": "FWD",
                "3568": "FWD",
                "3561": "FWD",
                "3219": "RWD",
                "2120": "AWD",
            },
        },
        "ui": {
            "refresh_hz": 20.0,
            "layout": "default",
            "curves_path": "gt7tui_curves.json",
            "show": {
                "dashboard": True,
                "tyres": True,
                "detail": True,
                "curve": True,
            },
        },
        "thresholds": {
            "rpm": {
                "warn_offset": 500,
            },
            "tyre_temp": {
                "cold": 60.0,
                "optimal_min": 80.0,
                "optimal_max": 100.0,
                "hot": 110.0,
            },
            "fuel": {
                "low_percent": 15.0,
            },
            "slip": {
                "warn_ratio": 1.10,
            },
            "delta": {
                "improve": -0.001,
                "worsen": 0.001,
            },
            "boost": {
                "max_kpa": 200.0,
            },
        },
        "colors": {
            "rpm": {
                "normal": "green",
                "warn": "yellow",
                "limit": "red",
            },
            "tyre_temp": {
                "cold": "cyan",
                "optimal": "green",
                "warm": "yellow",
                "hot": "red",
            },
            "fuel": {
                "normal": "green",
                "low": "red",
            },
            "slip": {
                "normal": "green",
                "warn": "yellow",
                "high": "red",
            },
            "delta": {
                "improve": "green",
                "worsen": "red",
                "neutral": "white",
            },
            "pedal": {
                "throttle": "green",
                "brake": "red",
                "clutch": "blue",
            },
            "status": {
                "ok": "green",
                "waiting": "yellow",
                "error": "red",
            },
        },
    }


@dataclass
class AppConfig:
    mode: str = "help"
    ps_ip: str | None = None
    bind: str = "0.0.0.0"
    recv_port: int = 33740
    send_port: int = 33739
    timeout: float = 10.0
    refresh_hz: float = 20.0
    heartbeat_interval_packets: int = 100
    heartbeat: str = "~"
    drive_layouts: dict[str, str] = field(default_factory=dict)
    layout: str = "default"
    curves_path: str = "gt7tui_curves.json"
    show: dict[str, bool] = field(default_factory=lambda: {"dashboard": True, "tyres": True, "detail": True, "curve": True})
    thresholds: dict[str, Any] = field(default_factory=dict)
    colors: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    record_path: str | None = None
    replay_path: str | None = None
    replay_speed: float = 1.0


def load_file_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def build_config(file_cfg: dict[str, Any] | None = None, cli: dict[str, Any] | None = None) -> AppConfig:
    merged = default_config()
    if file_cfg:
        merged = _deep_merge(merged, file_cfg)
    if cli:
        # Map CLI flat keys into config structure where applicable
        cli_net = {}
        cli_ui = {}
        for k, v in cli.items():
            if v is None:
                continue
            if k in ("bind", "recv_port", "send_port", "timeout", "heartbeat_interval_packets", "heartbeat"):
                cli_net[k] = v
            elif k in ("refresh_hz", "layout"):
                cli_ui[k] = v
            elif k in ("mode", "ps_ip", "record_path", "replay_path", "replay_speed"):
                merged[k] = v
        if cli_net:
            merged = _deep_merge(merged, {"network": cli_net})
        if cli_ui:
            merged = _deep_merge(merged, {"ui": cli_ui})
        for k in ("mode", "ps_ip", "record_path", "replay_path", "replay_speed"):
            if k in cli and cli[k] is not None:
                merged[k] = cli[k]

    net = merged.get("network", {})
    ui = merged.get("ui", {})
    return AppConfig(
        mode=merged.get("mode", "help"),
        ps_ip=merged.get("ps_ip"),
        bind=net.get("bind", "0.0.0.0"),
        recv_port=int(net.get("recv_port", 33740)),
        send_port=int(net.get("send_port", 33739)),
        timeout=float(net.get("timeout", 10.0)),
        refresh_hz=float(ui.get("refresh_hz", 20.0)),
        heartbeat_interval_packets=int(net.get("heartbeat_interval_packets", 100)),
        heartbeat=str(net.get("heartbeat", "~")),
        drive_layouts=dict(net.get("drive_layouts", {})),
        layout=str(ui.get("layout", "default")),
        curves_path=str(ui.get("curves_path", "gt7tui_curves.json")),
        show=dict(ui.get("show", {"dashboard": True, "tyres": True, "detail": True, "curve": True})),
        thresholds=dict(merged.get("thresholds", {})),
        colors=dict(merged.get("colors", {})),
        raw=merged,
        record_path=merged.get("record_path"),
        replay_path=merged.get("replay_path"),
        replay_speed=float(merged.get("replay_speed", 1.0)),
    )
