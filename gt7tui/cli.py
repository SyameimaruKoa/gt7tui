from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .config import build_config, load_file_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gt7tui",
        description=(
            "gt7tui: Visual TUI frontend for Gran Turismo 7 telemetry (PS4).\n"
            "Receives GT7 UDP telemetry, decodes packets, and displays gauges/meters in a terminal UI."
        ),
        epilog=(
            "Examples:\n"
            "  python -m gt7tui --live 192.168.1.50\n"
            "  python -m gt7tui --demo\n\n"
            "Modes are exclusive: use either --live <PS4_IP> or --demo.\n"
            "Configuration file (optional): ./gt7tui.json (fixed path, JSON).\n"
            "Priority: defaults < gt7tui.json < CLI options.\n"
            "Keys: q quit, r reconnect (live), 1/2/3 or tab switch views, ? help."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", metavar="PS4_IP", dest="live_ip", help="Live mode: connect to PS4 GT7 telemetry at given IP address")
    mode.add_argument("--demo", action="store_true", help="Demo mode: show continuously varying mock telemetry (no network)")
    parser.add_argument("--bind", default=None, help="UDP bind address (default: 0.0.0.0)")
    parser.add_argument("--recv-port", type=int, default=None, help="UDP receive port (default: 33740)")
    parser.add_argument("--send-port", type=int, default=None, help="UDP heartbeat destination port (default: 33739)")
    parser.add_argument("--timeout", type=float, default=None, help="UDP receive timeout seconds (default: 10.0)")
    parser.add_argument("--refresh-hz", type=float, default=None, help="UI refresh rate upper bound in Hz (default: 20.0)")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__

        print(f"gt7tui {__version__}")
        return 0

    if not args.live_ip and not args.demo:
        parser.print_help(sys.stdout)
        return 0

    mode = "demo" if args.demo else "live"
    cli = {
        "mode": mode,
        "ps_ip": args.live_ip if args.live_ip else None,
        "bind": args.bind,
        "recv_port": args.recv_port,
        "send_port": args.send_port,
        "timeout": args.timeout,
        "refresh_hz": args.refresh_hz,
    }
    file_cfg = load_file_config()
    cfg = build_config(file_cfg=file_cfg, cli=cli)

    if cfg.mode == "live" and not cfg.ps_ip:
        parser.print_help(sys.stdout)
        return 2

    from .tui.app import run_app

    run_app(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
