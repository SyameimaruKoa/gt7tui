from __future__ import annotations

import socket
import threading
import time
from typing import Callable, Optional

from .capture import CaptureWriter
from .decoder import TelemetryFrame, decode_packet
from .protocol import decrypt_packet
from .state import StateStore


class LiveReceiver:
    def __init__(
        self,
        ps_ip: str,
        bind: str,
        recv_port: int,
        send_port: int,
        timeout: float,
        heartbeat_interval_packets: int,
        store: StateStore,
        record_path: str | None = None,
    ) -> None:
        self.ps_ip = ps_ip
        self.bind = bind
        self.recv_port = recv_port
        self.send_port = send_port
        self.timeout = timeout
        self.heartbeat_interval_packets = max(1, heartbeat_interval_packets)
        self.store = store
        self.record_path = record_path
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None
        self._recorder: CaptureWriter | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gt7tui-receiver", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=2.0)

    def _send_heartbeat(self, sock: socket.socket) -> None:
        try:
            sock.sendto(b"A", (self.ps_ip, self.send_port))
        except Exception:
            pass

    def _run(self) -> None:
        last_pkt_id = -1
        pkt_count = 0
        if self.record_path:
            try:
                self._recorder = CaptureWriter(self.record_path).open()
            except Exception as e:
                self._recorder = None
                self.store.set_error(f"record open failed: {e}")
        try:
            while not self._stop.is_set():
                sock = None
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.bind((self.bind, self.recv_port))
                    sock.settimeout(self.timeout)
                    self._sock = sock
                    self.store.set_source("live")
                    self.store.mark_waiting("waiting for packets")
                    self._send_heartbeat(sock)
                    pkt_count = 0
                    while not self._stop.is_set():
                        try:
                            data, _ = sock.recvfrom(4096)
                        except socket.timeout:
                            self.store.mark_waiting("timeout")
                            self._send_heartbeat(sock)
                            pkt_count = 0
                            continue
                        except OSError:
                            break
                        self.store.mark_packet()
                        if self._recorder:
                            try:
                                self._recorder.write(data)
                            except Exception:
                                pass
                        pkt_count += 1
                        if pkt_count >= self.heartbeat_interval_packets:
                            self._send_heartbeat(sock)
                            pkt_count = 0
                        ddata = decrypt_packet(data)
                        if not ddata:
                            self.store.mark_dropped()
                            continue
                        frame = decode_packet(ddata)
                        if frame.packet_id <= last_pkt_id and last_pkt_id >= 0:
                            self.store.mark_dropped()
                            continue
                        last_pkt_id = frame.packet_id
                        self.store.update_frame(frame)
                except Exception as e:
                    self.store.mark_waiting(str(e))
                    time.sleep(1.0)
                finally:
                    try:
                        if sock:
                            sock.close()
                    except Exception:
                        pass
                    self._sock = None
        finally:
            if self._recorder:
                try:
                    self._recorder.close()
                except Exception:
                    pass
                self._recorder = None
