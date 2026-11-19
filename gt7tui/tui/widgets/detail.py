from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from ...config import AppConfig
from ...core.state import RuntimeState


def _fmt_vec(v) -> str:
    return f"X={v.x:9.4f}  Y={v.y:9.4f}  Z={v.z:9.4f}"


class DetailPane(Container):
    def __init__(self, config: AppConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.dynamics = Static()
        self.gearing = Static()
        self.flags = Static()
        self.session = Static()

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield self.session
                yield self.gearing
            with Horizontal():
                yield self.dynamics
                yield self.flags

    def update_view(self, snap: RuntimeState, cfg: AppConfig) -> None:
        f = snap.frame
        # Session / general
        st = Table.grid(padding=(0, 1))
        st.add_column(justify="left")
        if f:
            st.add_row(f"Car ID: {f.car_id}")
            st.add_row(f"Packet: {f.packet_id}  Raw: {f.raw_len} bytes")
            st.add_row(f"Time on track: {f.time_on_track_ms/1000.0:,.1f} s")
            st.add_row(f"Est top speed: {f.est_top_speed} km/h")
            st.add_row(f"Ride height: {f.ride_height_mm:.1f} mm")
            st.add_row(f"Oil: {f.oil_temp_c:.1f}°C  {f.oil_pressure_bar:.2f} bar")
            st.add_row(f"Water: {f.water_temp_c:.1f}°C")
            st.add_row(f"Clutch: {f.clutch:.3f}  Engaged: {f.clutch_engaged:.3f}  RPM after: {f.rpm_after_clutch:.0f}")
            st.add_row(f"Throttle: {f.throttle:.1f}%  Brake: {f.brake:.1f}%")
            st.add_row(f"Speed: {f.speed_kph:.1f} km/h  RPM: {f.rpm:.0f}")
            boost = f"{f.boost_kpa:.2f} kPa" if f.has_turbo else "N/A"
            st.add_row(f"Boost: {boost}")
        else:
            st.add_row("No telemetry frame")
        self.session.update(Panel(st, title="Session / Vehicle", border_style="cyan"))

        # Gearing
        gt = Table.grid(padding=(0, 1))
        if f:
            for i, ratio in enumerate(f.gear_ratios, start=1):
                gt.add_row(f"{i}: {ratio:8.3f}")
            gt.add_row(f"Unknown: {f.gear_ratio_unknown:8.3f}")
        else:
            gt.add_row("No data")
        self.gearing.update(Panel(gt, title="Gearing", border_style="magenta"))

        # Dynamics
        dt = Table.grid(padding=(0, 1))
        if f:
            dt.add_row("Position (m):  " + _fmt_vec(f.position_xyz))
            dt.add_row("Velocity (m/s):" + _fmt_vec(f.velocity_xyz))
            dt.add_row(f"Rotation PYR:  P={f.rotation_pyr.x:9.4f}  Y={f.rotation_pyr.y:9.4f}  R={f.rotation_pyr.z:9.4f}")
            dt.add_row("Angular (r/s): " + _fmt_vec(f.angular_velocity_xyz))
            dt.add_row(f"North/South:   {f.north_south:9.4f}")
        else:
            dt.add_row("No data")
        self.dynamics.update(Panel(dt, title="Dynamics", border_style="green"))

        # Flags / unknown
        ft = Table.grid(padding=(0, 1))
        if f:
            ft.add_row(f"0x8E: {f.flags_8e:08b}  0x8F: {f.flags_8f:08b}  0x93: {f.flags_93:08b}")
            keys = list(f.unknown_floats.keys())
            for k in keys:
                ft.add_row(f"{k}: {f.unknown_floats[k]:11.5f}")
        else:
            ft.add_row("No data")
        self.flags.update(Panel(ft, title="Flags / Unknown", border_style="yellow"))
