# gt7tui

Visual TUI frontend for Gran Turismo 7 telemetry (PS4).
Receives GT7 UDP telemetry, decodes packets (Salsa20 + struct offsets), and displays gauges/meters in a terminal UI using Textual.

> Target: **GT7 on PS4** (same LAN). Packet decode logic is based on [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) and community research (PDTools issue #14).

## Features
- Modes: `--live <PS4_IP>`, `--replay <file>`, `--demo` (no PS4 needed)
- `--record <file>` saves all UDP communication (telemetry + heartbeats, timestamps + direction) as `*.gt7cap` v2
- Heartbeat types selectable: `A` (0x128), `B` (0x13C), `~` (0x158, default) — each has a different XOR key and packet size
- Dashboard: tachometer (rev-limiter scale), speedometer, pedals with TCS/ABS intervention, lap/timing, drive-layout statistics, tyres, HV battery, 2D G map + steering
- Detail: session, gearing (9/10-speed aware), dynamics, flags with names, identified vs unknown fields
- Responsive layout: wide (2 columns 1:2), compact (2 columns 1:1), tiny (<80 cols, single column)
- Config: `gt7tui.json` for thresholds, colors, heartbeat, and per-car drive layouts
- Keyboard: `q` quit, `r` reconnect, `1/2/3` tabs, `?` help

## Requirements
- Python **3.11+**
- PS4 and this device on the same LAN (UDP receive `33740`, heartbeat to `33739`)
- Dependencies: `pycryptodome`, `textual`

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

## Usage
```bash
python -m gt7tui -h                      # help (also with no args)
python -m gt7tui --live 192.168.55.253
python -m gt7tui --live 192.168.55.253 --record captures/race.gt7cap
python -m gt7tui --replay captures/race.gt7cap
python -m gt7tui --replay captures/race.gt7cap --speed 4.0
python -m gt7tui --demo
```

Options:
- `--heartbeat {A,B,~}` heartbeat type (default `~`; `~` = 0x158 extended packet)
- `--record FILE` record raw UDP (live only)
- `--speed FACTOR` replay speed multiplier
- `--bind`, `--recv-port`, `--send-port`, `--timeout`, `--refresh-hz`, `--version`

Helper scripts:
- `./scripts/run_gt7tui.sh --live <PS4_IP>` (or `--demo`, `-h`)
- `.\scripts\run_gt7tui.ps1 -Live <PS4_IP>` (or `-Demo`, `-h` / `Get-Help`)

## Captures
`*.gt7cap` v2 format: `GT7TCAP\0` + version 2 header, then records of
`timestamp(float64)`, `length(uint32)`, `direction(uint8)`, `port(uint16)`, `reserved(uint8)` + raw payload.
Direction 0 = received telemetry, 1 = sent heartbeat. Replay auto-detects the heartbeat decryption key.

## Telemetry fields
Base packet (0x128): speed, RPM, pedals, gear, tyres (temp/radius/angular velocity/suspension), road plane, lap times, position, flags.
Extended packet (`~`, 0x158) adds:
- 0x128 steering angle (rad), 0x12C steering rate (rad/s)
- 0x130/134/138 sway/heave/surge (vehicle motion)
- 0x13C/13D physical throttle/brake outputs, 0x13E car type, 0x13F energy-recovery flag
- 0x140-14C individual motor outputs (some cars)
- 0x150 motor assist (1 = MAX), 0x154 engine output

Flags:
- `0x8E`: Night/Day (0x80), Handbrake (0x40), RevLimit (0x20), ClutchOff (0x10), Loading (0x04), Paused (0x02), Racing (0x01)
- `0x8F`: TCS (0x08), ASM (0x04), LowBeam (0x02), HighBeam (0x01)

Notes:
- The tachometer ceiling is the rev-limiter number engraved on GT7's tachometer. Shift point uses `rev_warning`.
- HEV battery SOC itself is not broadcast; the `HV Battery` panel shows motor-assist/regen flow (0x150) and individual motor outputs.
- Drive layout is stored per car (see config) and overrides slip-based detection; some AWD cars only drive the second axle at low speed.

## Configuration
Optional fixed-path `./gt7tui.json`; priority `defaults < file < CLI`.
```json
{
  "network": {
    "heartbeat": "~",
    "drive_layouts": {
      "3572": "AWD",
      "1537": "FWD",
      "3568": "FWD",
      "3561": "FWD",
      "3219": "RWD",
      "2120": "AWD"
    }
  },
  "ui": {
    "refresh_hz": 20.0,
    "show": { "dashboard": true, "tyres": true, "detail": true }
  },
  "thresholds": {
    "tyre_temp": { "cold": 60.0, "optimal_min": 80.0, "optimal_max": 100.0, "hot": 110.0 },
    "fuel": { "low_percent": 15.0 },
    "slip": { "warn_ratio": 1.10 }
  },
  "colors": { }
}
```

## Troubleshooting
- **WAIT / no data**: check PS4 IP, same LAN, GT7 on track, UDP 33740/33739 reachability.
- **Extended fields empty**: use `--heartbeat ~` (default) when recording/live; `A` packets lack extensions.
- **Small terminal**: layout switches automatically; below 80 columns panels stack in one scrollable column.

## License
GPL-3.0-or-later. See `LICENSE`.
