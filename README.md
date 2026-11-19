# gt7tui

Visual TUI frontend for Gran Turismo 7 telemetry (PS4).  
Receives GT7 UDP telemetry, decodes packets (Salsa20 + struct offsets), and displays gauges/meters in a terminal UI using Textual.

> Target: **GT7 on PS4** (same LAN). Packet decode logic is based on [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry).

## Features
- Live mode (`--live <PS4_IP>`), replay mode (`--replay <file>`), and demo mode (`--demo`)
- Record all UDP communication during live mode (`--record <file>`) for offline verification (received telemetry and sent heartbeats, with timestamps and direction)
- Visual dashboard: RPM bar gauge with rev warning/limiter zones, large gear/speed, throttle/brake/clutch bars
- Tyre view: 4-wheel layout, temperature heat indication, slip indicator, suspension/speed/diameter
- Lap/timing: current/best/last and delta (bar/color when comparable)
- Detail view: position/velocity/rotation/angular velocity, gearing, flags/unknown fields
- 3-tab UI for small terminals (Termux): Dashboard / Tyres / Detail
- Optional JSON config (`gt7tui.json`) for colors, thresholds (category-level), layout/refresh, and item visibility

## Requirements
- Python **3.11+**
- Network: PS4 and this device on the same reachable network (UDP)
  - Receive: UDP `33740` (default)
  - Heartbeat to PS4: UDP `33739` (default)
- Dependencies: `pycryptodome`, `textual` (install in a virtual environment)

## Setup
```bash
# Linux / macOS / Termux
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

```powershell
# Windows (PowerShell)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
```

Termux notes:
- Install Python and build tools as needed for `pycryptodome` (e.g. `pkg install python clang`), then install in venv.
- Terminal size/color support varies; use Dashboard/Tyres/Detail tabs.
- Keep device awake and on the same Wi-Fi network as PS4.

## Usage
```bash
# Show help (also shown with no arguments)
python -m gt7tui -h
python -m gt7tui

# Live telemetry from PS4
python -m gt7tui --live 192.168.1.50

# Live telemetry + record all UDP communication for verification
python -m gt7tui --live 192.168.1.50 --record captures/race.gt7cap

# Replay a recorded capture
python -m gt7tui --replay captures/race.gt7cap
python -m gt7tui --replay captures/race.gt7cap --speed 2.0

# Demo mode (no PS4/network required)
python -m gt7tui --demo
```

Options:
- `--record <file>` record all UDP communication in live mode (received telemetry + sent heartbeats)
- `--speed <factor>` replay speed multiplier (default `1.0`)
- `--bind <addr>` (default `0.0.0.0`)
- `--recv-port <port>` (default `33740`)
- `--send-port <port>` (default `33739`)
- `--timeout <sec>` (default `10.0`)
- `--refresh-hz <hz>` (default `20.0`)
- `--version`

In-app keys:
- `q`: quit
- `r`: reconnect (live)
- `1`/`2`/`3`: switch Dashboard/Tyres/Detail
- `?`: help panel

## Helper scripts
- Linux/Termux: `./scripts/run_gt7tui.sh --live <PS4_IP>` or `./scripts/run_gt7tui.sh --demo` (`-h/--help` supported)
- Windows PowerShell: `.\scripts\run_gt7tui.ps1 -Live <PS4_IP>` or `.\scripts\run_gt7tui.ps1 -Demo` (`-h` / `--help` / `Get-Help` supported)

## Configuration
Optional fixed-path config file: `./gt7tui.json` (if absent, defaults are used).  
Priority: `defaults < gt7tui.json < CLI options` (no `--config` option).

Configurable areas (category-level):
- `colors`: rpm/tyre_temp/fuel/slip/delta/pedal/status
- `thresholds`: rpm, tyre_temp, fuel, slip, delta, boost
- `ui.refresh_hz`, `ui.layout`, `ui.show` (dashboard/tyres/detail)
- `network`: bind/recv_port/send_port/timeout/heartbeat_interval_packets

Example:
```json
{
  "ui": {
    "refresh_hz": 20.0,
    "show": { "dashboard": true, "tyres": true, "detail": true }
  },
  "thresholds": {
    "tyre_temp": { "cold": 60.0, "optimal_min": 80.0, "optimal_max": 100.0, "hot": 110.0 },
    "fuel": { "low_percent": 15.0 },
    "slip": { "warn_ratio": 1.10 }
  }
}
```

Notes:
- Rev warning/limiter are taken from packet values when available.
- Non-packet thresholds (tyre temperature bands, low fuel/charge %, slip warning, etc.) use built-in defaults and can be adjusted in `gt7tui.json`.

## Troubleshooting
- **No data / WAIT**: verify PS4 IP, same network, GT7 running on track, and UDP reachability.
- **Firewall**: allow inbound UDP `33740` and outbound UDP `33739` on the receiving device/OS.
- **Windows**: Windows Terminal recommended for better rendering.
- **Termux/Haven**: environment differences may affect terminal rendering and dependency installation.

## License and attribution
- Licensed under **GPL-3.0-or-later** (see `LICENSE`).
- Telemetry packet structure/decode approach references [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) (GPL-3.0) and related GT7 telemetry research by the community.

