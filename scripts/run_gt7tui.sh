#!/usr/bin/env bash
# Help is available: run with -h or --help

set -euo pipefail

show_help() {
    cat <<'EOF'
run_gt7tui.sh - Launch gt7tui (visual TUI frontend for Gran Turismo 7 telemetry on PS4)

USAGE:
    ./scripts/run_gt7tui.sh --live <PS4_IP> [--record <file>] [options]
    ./scripts/run_gt7tui.sh --replay <file> [--speed <factor>] [options]
    ./scripts/run_gt7tui.sh --demo [options]
    ./scripts/run_gt7tui.sh -h|--help

MODES (exclusive):
    --live <PS4_IP>   Connect to PS4 GT7 telemetry at the specified IP address
    --replay <file>   Replay a recorded capture file
    --demo            Run demo mode with continuously varying mock telemetry

OPTIONS (passed to gt7tui):
    --record <file>       Record raw UDP packets to file (live mode only)
    --speed <factor>      Replay speed multiplier (default: 1.0)
    --bind <addr>         UDP bind address (default: 0.0.0.0)
    --recv-port <port>    UDP receive port (default: 33740)
    --send-port <port>    UDP heartbeat destination port (default: 33739)
    --timeout <sec>       UDP receive timeout seconds (default: 10.0)
    --refresh-hz <hz>     UI refresh rate upper bound (default: 20.0)
    --version             Show gt7tui version

NOTES:
    - Run inside a Python virtual environment with dependencies installed.
    - PS4 and this device must be on the same reachable network (UDP 33739/33740).
    - Optional config: ./gt7tui.json (fixed path). Priority: defaults < file < CLI.
    - In-app keys: q quit, r reconnect (live), 1/2/3 tabs, ? help.
EOF
}

if [ "$#" -eq 0 ]; then
    show_help
    exit 0
fi

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            exit 0
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -x "${ROOT_DIR}/.venv/bin/python" ]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" -m gt7tui "$@"
