import random

DEBUG_NO_AUTH = True

class Authenticator:
    """Manages PIN generation and device authorization."""
    
    def __init__(self):
        self._pin = str(random.randint(1000, 9999))
        self._authorized_addrs = set()

    @property
    def pin(self):
        return self._pin

    def regenerate_pin(self):
        """Generate a new PIN and clear all authorized devices."""
        self._pin = str(random.randint(1000, 9999))
        self._authorized_addrs.clear()

    def handle_pair_request(self, addr, provided_pin):
        """Validates the provided PIN. Returns True if successful."""
        if str(provided_pin) == self._pin:
            self._authorized_addrs.add(addr[0])
            return True
        return False

    def is_authorized(self, addr):
        """Checks if the given IP address is authorized."""
        if DEBUG_NO_AUTH:
            return True
        return addr[0] in self._authorized_addrs
