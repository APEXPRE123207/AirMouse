"""
AirMouse - UDP Sender (Phase 2)

Sends yaw/pitch/roll as JSON to the Windows receiver.

Packet format:
  {"yaw": 15.2, "pitch": -8.4, "roll": 2.1}

Usage:
  sender = UDPSender(host='192.168.1.100', port=5005)
  sender.start()
  sender.send(yaw=15.2, pitch=-8.4, roll=2.1)
  sender.stop()
"""

import json
import socket
import threading
import queue
import time

DEFAULT_PORT = 5005
HEARTBEAT_INTERVAL = 1.0       # seconds between keepalive pings
SEND_TIMEOUT       = 2.0       # socket send timeout


class UDPSender:
    """
    Non-blocking UDP sender.

    All sends are queued and dispatched from a background thread so that
    network I/O never blocks the Kivy UI thread.
    """

    def __init__(self, host='', port=DEFAULT_PORT):
        self.host   = host
        self.port   = port
        self._queue = queue.Queue(maxsize=32)
        self._sock   = None   # type: socket.socket | None
        self._thread = None   # type: threading.Thread | None
        self._running = False
        self._connected = False
        self.on_status_change = None   # optional callback(connected: bool)

    # ── Public API ──────────────────────────────────────────────────────

    def start(self):
        """Open socket and start background send thread."""
        if self._running:
            return

        # Drain any leftover sentinel / stale packets from previous session
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._connected = False
        self._running = True
        self._open_socket()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal worker to stop and close socket.

        Does NOT block the calling thread with join() — the daemon thread
        will exit on its own once _running is False and the sentinel is read.
        This prevents ANR (Application Not Responding) on Android.
        """
        if not self._running:
            return
        self._running = False
        # Push sentinel so the worker wakes up from queue.get()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        # Don't join — daemon thread will die on its own
        self._thread = None
        self._close_socket()
        self._connected = False

    def send(self, yaw, pitch, roll):
        """
        Queue an orientation packet.  Drops oldest packet if queue is full
        (keeps latency low — we prefer freshness over completeness).
        """
        if not self._running or not self.host:
            return
        packet = {
            'yaw':   round(yaw,   2),
            'pitch': round(pitch, 2),
            'roll':  round(roll,  2),
        }
        try:
            self._queue.put_nowait(json.dumps(packet).encode())
        except queue.Full:
            try:
                self._queue.get_nowait()          # drop stale packet
                self._queue.put_nowait(json.dumps(packet).encode())
            except queue.Empty:
                pass

    def set_target(self, host, port=DEFAULT_PORT):
        """Update destination while running."""
        self.host = host
        self.port = port

    # ── Discovery ───────────────────────────────────────────────────────

    @staticmethod
    def discover_server(port=DEFAULT_PORT, timeout=3.0):
        """Broadcast a discovery packet and return the IP of the first
        AirMouse Desktop that responds, or None on timeout.

        Safe to call from a background thread.
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(timeout)

            packet = json.dumps({"type": "discover"}).encode()
            sock.sendto(packet, ("255.255.255.255", port))

            # Wait for response
            while True:
                data, addr = sock.recvfrom(1024)
                try:
                    resp = json.loads(data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if resp.get('type') == 'discover_response':
                    return addr[0]   # IP of the Desktop
        except (socket.timeout, OSError):
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    # ── Internal ────────────────────────────────────────────────────────

    def _open_socket(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(SEND_TIMEOUT)
        except OSError as e:
            print('[UDPSender] socket open failed: %s' % e)
            self._sock = None

    def _close_socket(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _worker(self):
        last_heartbeat = time.time()

        while self._running:
            # Heartbeat
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                self._send_raw(b'{"type":"heartbeat"}')
                last_heartbeat = now

            try:
                data = self._queue.get(timeout=HEARTBEAT_INTERVAL)
            except queue.Empty:
                continue

            if data is None:          # sentinel → stop
                break

            self._send_raw(data)

    def _send_raw(self, data):
        if not self._sock or not self.host:
            return
        try:
            self._sock.sendto(data, (self.host, self.port))
            if not self._connected:
                self._connected = True
                self._notify(True)
        except OSError as e:
            print('[UDPSender] send error: %s' % e)
            if self._connected:
                self._connected = False
                self._notify(False)

    def _notify(self, connected):
        if callable(self.on_status_change):
            try:
                self.on_status_change(connected)
            except Exception as e:
                print('[UDPSender] status callback error: %s' % e)
