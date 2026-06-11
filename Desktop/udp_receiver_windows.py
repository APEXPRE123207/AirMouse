"""
AirMouse - Windows Receiver (Phase 3 update)
Receives yaw/pitch/roll JSON from the custom Android app.

Replaces the old HyperIMU quaternion receiver.

Packet format:
  {"yaw": 15.2, "pitch": -8.4, "roll": 2.1}
"""

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from auth import Authenticator

DEFAULT_HOST    = '0.0.0.0'
DEFAULT_PORT    = 5005
TIMEOUT_SECONDS = 3.0        # declare connection lost after this many seconds


@dataclass
class OrientationData:
    yaw:   float = 0.0
    pitch: float = 0.0
    roll:  float = 0.0
    timestamp: float = field(default_factory=time.time)


class UDPReceiver:
    """
    Listens for AirMouse orientation packets on a UDP port.

    Callbacks
    ---------
    on_data(data: OrientationData)   — fired on every valid packet
    on_connect()                      — fired when first packet arrives
    on_disconnect()                   — fired after TIMEOUT_SECONDS silence
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        on_data:       Optional[Callable] = None,
        on_connect:    Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
    ):
        self.host = host
        self.port = port
        self.on_data       = on_data       or (lambda d: None)
        self.on_connect    = on_connect    or (lambda: None)
        self.on_disconnect = on_disconnect or (lambda: None)

        self._sock:    Optional[socket.socket] = None
        self._thread:  Optional[threading.Thread] = None
        self._watchdog: Optional[threading.Thread] = None
        self._running  = False
        self._connected = False
        self._last_seen = 0.0
        self._pending_calibrate = False
        self._pending_home = False

        # PIN-based pairing
        self._auth = Authenticator()

        # Latest values (thread-safe reads are fine for floats in CPython)
        self.latest = OrientationData()

    @property
    def pin(self):
        return self._auth.pin

    def regenerate_pin(self):
        """Generate a new PIN and clear all authorized devices."""
        self._auth.regenerate_pin()

    # ── Public API ──────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._open_socket()
        self._thread   = threading.Thread(target=self._recv_loop, daemon=True)
        self._watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._thread.start()
        self._watchdog.start()

    def stop(self):
        self._running = False
        self._close_socket()

    # ── Internal ────────────────────────────────────────────────────────

    def _open_socket(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)
        self._sock.bind((self.host, self.port))

    def _close_socket(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _recv_loop(self):
        while self._running:
            if self._sock is None:
                break
            try:
                raw, addr = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                payload = json.loads(raw.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            ptype = payload.get('type')

            # ── Always allowed (no auth) ──────────────────────────────

            # Respond to discovery broadcasts from Android app
            if ptype == 'discover':
                try:
                    response = json.dumps({"type": "discover_response"}).encode()
                    self._sock.sendto(response, addr)
                except OSError:
                    pass
                continue

            # Handle pairing requests
            if ptype == 'pair':
                pin = str(payload.get('pin', ''))
                if self._auth.handle_pair_request(addr, pin):
                    resp = {"type": "pair_response", "status": "ok"}
                else:
                    resp = {"type": "pair_response", "status": "denied"}
                try:
                    self._sock.sendto(json.dumps(resp).encode(), addr)
                except OSError:
                    pass
                continue

            # ── Auth required below this point ────────────────────────
            if not self._auth.is_authorized(addr):
                continue

            # Heartbeat pings
            if ptype == 'heartbeat':
                self._mark_seen()
                continue

            # Remote calibrate command from phone
            if ptype == 'calibrate':
                self._mark_seen()
                self._pending_calibrate = True
                continue

            # Remote home (center cursor) command from phone
            if ptype == 'home':
                self._mark_seen()
                self._pending_home = True
                continue

            # Validate orientation fields
            try:
                data = OrientationData(
                    yaw   = float(payload['yaw']),
                    pitch = float(payload['pitch']),
                    roll  = float(payload['roll']),
                )
            except (KeyError, ValueError, TypeError):
                continue

            self.latest = data
            self._mark_seen()
            try:
                self.on_data(data)
            except Exception as e:
                print(f'[UDPReceiver] on_data callback error: {e}')

    def _mark_seen(self):
        self._last_seen = time.time()
        if not self._connected:
            self._connected = True
            try:
                self.on_connect()
            except Exception as e:
                print(f'[UDPReceiver] on_connect callback error: {e}')

    def _watchdog_loop(self):
        """Fires on_disconnect if no packet received for TIMEOUT_SECONDS."""
        while self._running:
            time.sleep(0.5)
            if self._connected and (time.time() - self._last_seen) > TIMEOUT_SECONDS:
                self._connected = False
                try:
                    self.on_disconnect()
                except Exception as e:
                    print(f'[UDPReceiver] on_disconnect callback error: {e}')
