from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from ..config import AppConfig
from ..core.demo import DemoSource
from ..core.receiver import LiveReceiver
from ..core.replay import ReplaySource
from ..core.state import StateStore
from .widgets.dashboard import DashboardPane
from .widgets.detail import DetailPane
from .widgets.status import StatusBar
from .widgets.tyres import TyresPane


class GT7App(App):
    TITLE = "gt7tui"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status {
        height: 1;
        dock: top;
        background: $panel;
    }
    #main-tabs {
        height: 1fr;
    }
    .panel {
        border: round $primary;
        padding: 0 1;
        height: auto;
    }
    .title {
        text-style: bold;
    }
    #dashboard-root, #tyres-root, #detail-root {
        height: 1fr;
    }
    DashboardPane > Horizontal {
        height: 1fr;
    }
    DashboardPane > Horizontal > Vertical {
        height: auto;
        width: 1fr;
    }
    DashboardPane > Horizontal > Vertical > Horizontal {
        height: auto;
    }
    /* Gear cluster: keep label and digits on one line, never wrap vertically */
    DashboardPane .gear-cluster {
        width: 12;
        height: auto;
    }
    DashboardPane .gear-cluster .title {
        width: 100%;
        text-wrap: nowrap;
    }
    DashboardPane .gear-cluster Digits {
        width: 100%;
        height: 3;
    }
    DashboardPane RpmBlock, DashboardPane SpeedBlock {
        height: auto;
        width: 1fr;
    }
    DashboardPane PedalsBlock, DashboardPane LapBlock, DashboardPane VehicleBlock, DashboardPane BoostBlock, DashboardPane SessionBlock, DashboardPane TyreSummaryBlock, DashboardPane GSensorBlock, DashboardPane LayoutStatsBlock {
        height: auto;
    }
    .compact DashboardPane .wide-only {
        display: none;
    }
    .wide DashboardPane .wide-only {
        display: block;
    }
    DetailPane {
        layout: vertical;
    }
    DetailPane > Vertical {
        height: 1fr;
    }
    DetailPane > Vertical > Horizontal {
        height: 1fr;
    }
    DetailPane Static {
        height: auto;
        width: 1fr;
    }
    DetailPane #flags-panel {
        height: 1fr;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reconnect", "Reconnect"),
        Binding("1", "tab_dashboard", "Dashboard", show=False),
        Binding("2", "tab_tyres", "Tyres", show=False),
        Binding("3", "tab_detail", "Detail", show=False),
        Binding("?", "help_panel", "Help"),
    ]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.store = StateStore()
        self.receiver: LiveReceiver | None = None
        self.demo: DemoSource | None = None
        self.replay: ReplaySource | None = None
        self.status_bar: StatusBar | None = None
        self.dashboard: DashboardPane | None = None
        self.tyres: TyresPane | None = None
        self.detail: DetailPane | None = None
        self._help_visible = False
        self._help_widget: Static | None = None

    def compose(self) -> ComposeResult:
        self.status_bar = StatusBar(id="status")
        yield self.status_bar
        with TabbedContent(id="main-tabs", initial="tab-dashboard"):
            with TabPane("Dashboard", id="tab-dashboard"):
                self.dashboard = DashboardPane(self.config, id="dashboard-root")
                yield self.dashboard
            with TabPane("Tyres", id="tab-tyres"):
                self.tyres = TyresPane(self.config, id="tyres-root")
                yield self.tyres
            with TabPane("Detail", id="tab-detail"):
                self.detail = DetailPane(self.config, id="detail-root")
                yield self.detail
        self._help_widget = Static("", id="help-panel")
        self._help_widget.display = False
        yield self._help_widget
        yield Footer()

    def on_mount(self) -> None:
        self.title = "gt7tui"
        sub = f"mode={self.config.mode}"
        if self.config.record_path:
            sub += f" rec={self.config.record_path}"
        self.sub_title = sub
        self._start_source()
        hz = max(1.0, float(self.config.refresh_hz))
        self.set_interval(1.0 / hz, self._tick)

    def _start_source(self) -> None:
        self._stop_source()
        if self.config.mode == "demo":
            self.demo = DemoSource(self.store, refresh_hz=self.config.refresh_hz)
            self.demo.start()
        elif self.config.mode == "replay":
            if not self.config.replay_path:
                self.store.mark_waiting("missing replay file")
                return
            self.replay = ReplaySource(self.config.replay_path, self.store, speed=self.config.replay_speed)
            self.replay.start()
        else:
            if not self.config.ps_ip:
                self.store.mark_waiting("missing PS4 IP")
                return
            self.receiver = LiveReceiver(
                ps_ip=self.config.ps_ip,
                bind=self.config.bind,
                recv_port=self.config.recv_port,
                send_port=self.config.send_port,
                timeout=self.config.timeout,
                heartbeat_interval_packets=self.config.heartbeat_interval_packets,
                store=self.store,
                record_path=self.config.record_path,
                heartbeat=self.config.heartbeat,
            )
            self.receiver.start()

    def _stop_source(self) -> None:
        if self.receiver:
            self.receiver.stop()
            self.receiver = None
        if self.demo:
            self.demo.stop()
            self.demo = None
        if self.replay:
            self.replay.stop()
            self.replay = None

    def _layout_mode(self) -> str:
        w = self.size.width
        h = self.size.height
        if w < 110 or h < 32:
            return "compact"
        return "wide"

    def _apply_layout_mode(self) -> str:
        mode = self._layout_mode()
        self.screen.set_class(mode == "compact", "compact")
        self.screen.set_class(mode == "wide", "wide")
        return mode

    def on_resize(self, event) -> None:
        self._apply_layout_mode()

    def _tick(self) -> None:
        layout = self._apply_layout_mode()
        snap = self.store.snapshot()
        if self.status_bar:
            self.status_bar.update_view(snap, self.config)
        if self.dashboard:
            self.dashboard.update_view(snap, self.config, layout=layout)
        if self.tyres:
            self.tyres.update_view(snap, self.config)
        if self.detail:
            self.detail.update_view(snap, self.config)

    def on_unmount(self) -> None:
        self._stop_source()

    def action_reconnect(self) -> None:
        if self.config.mode == "live":
            self.store.mark_waiting("reconnecting")
            self._start_source()

    def action_tab_dashboard(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-dashboard"

    def action_tab_tyres(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-tyres"

    def action_tab_detail(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-detail"

    def action_help_panel(self) -> None:
        if not self._help_widget:
            return
        self._help_visible = not self._help_visible
        if self._help_visible:
            self._help_widget.update(
                "[b]Keys[/b]  q: quit  r: reconnect(live)  1/2/3: tabs  ?: help\n"
                "[b]Modes[/b] --live <PS4_IP> [--record file]  --replay <file> [--speed N]  --demo\n"
                "[b]Config[/b] ./gt7tui.json (fixed path, optional)\n"
                "[b]Ports[/b] recv 33740 / send 33739 (defaults)"
            )
            self._help_widget.display = True
        else:
            self._help_widget.display = False


def run_app(config: AppConfig) -> None:
    app = GT7App(config)
    app.run()
