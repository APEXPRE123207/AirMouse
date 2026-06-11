import json
import os
import time
from udp_receiver_windows import UDPReceiver


class AirMouseReceiver:
    """Adapter that wraps UDPReceiver and exposes pitch/roll/yaw attributes.

    It provides a blocking `run()` method so it can be started with
    `threading.Thread(target=receiver.run, daemon=True).start()` like before.
    """

    def __init__(self, host="0.0.0.0", port=5005, json_path="Assets\\mobile_data.json"):
        self.host = host
        self.port = port
        self.json_path = json_path

        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.connected = False

        # Create UDPReceiver with callbacks into this adapter
        self._udp = UDPReceiver(
            host=self.host,
            port=self.port,
            on_data=self._on_data,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

    @property
    def pin(self):
        return self._udp.pin

    def regenerate_pin(self):
        self._udp.regenerate_pin()

    def _on_data(self, data):
        # OrientationData has yaw, pitch, roll
        self.yaw = float(data.yaw)
        self.pitch = float(data.pitch)
        self.roll = float(data.roll)
        self.connected = True

        # write latest snapshot to file (overwrite)
        output_dir = os.path.dirname(self.json_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(self.json_path, "w") as f:
            json.dump({"yaw": self.yaw, "pitch": self.pitch, "roll": self.roll}, f, indent=2)

    def _on_connect(self):
        self.connected = True

    def _on_disconnect(self):
        self.connected = False

    def poll_calibrate(self):
        """Return True once if a remote calibrate command was received."""
        if self._udp._pending_calibrate:
            self._udp._pending_calibrate = False
            return True
        return False

    def poll_home(self):
        """Return True once if a remote home command was received."""
        if self._udp._pending_home:
            self._udp._pending_home = False
            return True
        return False

    def run(self):
        """Start the UDPReceiver and block until the process is stopped.

        This mirrors the previous `run()` semantics (blocking) so the GUI
        can still start the receiver on a daemon thread.
        """
        self._udp.start()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._udp.stop()


if __name__ == "__main__":
    AirMouseReceiver().run()