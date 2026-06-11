"""
AirMouse – Cursor + Click + Drag + Scroll Controller (Windows)

Uses ctypes for all mouse actions — no pip dependencies.

CursorController — relative / mouse-style movement (yaw/pitch → cursor)
ClickController  — roll-based gestures:
    • Quick tilt past click zone + return → CLICK
    • Hold tilt in click zone for 0.4s   → DRAG (mouse button held)
    • Tilt further into scroll zone      → SCROLL continuously
"""

import ctypes
import ctypes.wintypes
import time

# ── Win32 ────────────────────────────────────────────────────────────────────
_user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_WHEEL     = 0x0800
WHEEL_DELTA           = 120


def _get_cursor_pos():
    pt = ctypes.wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _set_cursor_pos(x, y):
    _user32.SetCursorPos(int(x), int(y))


def _get_screen_size():
    w = _user32.GetSystemMetrics(0)
    h = _user32.GetSystemMetrics(1)
    return w, h


def _left_click():
    _user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    _user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _right_click():
    _user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    _user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


def _mouse_down(direction):
    if direction == 'left':
        _user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    else:
        _user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)


def _mouse_up(direction):
    if direction == 'left':
        _user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    else:
        _user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


def _scroll(amount):
    """Positive = scroll up, negative = scroll down."""
    _user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount, 0)


# ── Cursor Controller ───────────────────────────────────────────────────────

class CursorController:
    """Relative / mouse-style cursor movement from yaw/pitch changes."""

    def __init__(self, sensitivity=10.0, dead_zone=0.05, smoothing=1.0):
        self.sensitivity = sensitivity
        self.dead_zone   = dead_zone
        self.smoothing   = smoothing

        self._prev_yaw   = None
        self._prev_pitch = None
        self._smooth_dx  = 0.0
        self._smooth_dy  = 0.0
        self._active     = False
        
        # Click error offsets
        self.err_l_y = 0.0
        self.err_l_p = 0.0
        self.err_r_y = 0.0
        self.err_r_p = 0.0
        
        self._applied_err_x = 0.0
        self._applied_err_y = 0.0

        self._screen_w, self._screen_h = _get_screen_size()

    @property
    def active(self):
        return self._active

    def start(self):
        self._prev_yaw = self._prev_pitch = None
        self._smooth_dx = self._smooth_dy = 0.0
        self._applied_err_x = self._applied_err_y = 0.0
        self._active = True

    def stop(self):
        self._active = False
        self._prev_yaw = self._prev_pitch = None
        self._smooth_dx = self._smooth_dy = 0.0
        self._applied_err_x = self._applied_err_y = 0.0

    def set_sensitivity(self, v):
        self.sensitivity = max(1.0, min(30.0, v))

    def set_dead_zone(self, v):
        self.dead_zone = max(0.0, min(1.0, v))

    def set_smoothing(self, v):
        self.smoothing = max(0.05, min(1.0, v))
        
    def set_calibration_errors(self, l_y, l_p, r_y, r_p):
        self.err_l_y = l_y
        self.err_l_p = l_p
        self.err_r_y = r_y
        self.err_r_p = r_p

    def update(self, yaw, pitch, roll=0.0):
        if not self._active:
            return
        if self._prev_yaw is None:
            self._prev_yaw, self._prev_pitch = yaw, pitch
            return

        raw_dx = yaw - self._prev_yaw
        raw_dy = pitch - self._prev_pitch
        
        # Inverse kinematics error correction
        # We calculate the absolute target error to apply at this roll angle,
        # and only subtract the *delta* of that error from the movement this frame.
        target_err_x = 0.0
        target_err_y = 0.0
        
        if roll < -5.0: # Left roll
            prop = min(1.0, (abs(roll) - 5.0) / 20.0)
            target_err_x = self.err_l_y * prop
            target_err_y = self.err_l_p * prop
        elif roll > 5.0: # Right roll
            prop = min(1.0, (abs(roll) - 5.0) / 20.0)
            target_err_x = self.err_r_y * prop
            target_err_y = self.err_r_p * prop
            
        # Subtract the delta error from the raw movement
        raw_dx -= (target_err_x - self._applied_err_x)
        raw_dy -= (target_err_y - self._applied_err_y)
        
        # Save for next frame
        self._applied_err_x = target_err_x
        self._applied_err_y = target_err_y

        self._prev_yaw, self._prev_pitch = yaw, pitch

        if raw_dx > 180.0:   raw_dx -= 360.0
        elif raw_dx < -180.0: raw_dx += 360.0

        if abs(raw_dx) > 30.0 or abs(raw_dy) > 30.0:
            return

        a = self.smoothing
        self._smooth_dx = a * raw_dx + (1.0 - a) * self._smooth_dx
        self._smooth_dy = a * raw_dy + (1.0 - a) * self._smooth_dy

        dx, dy = self._smooth_dx, self._smooth_dy
        if abs(dx) < self.dead_zone: dx = 0.0
        if abs(dy) < self.dead_zone: dy = 0.0
        if dx == 0.0 and dy == 0.0:
            return

        cx, cy = _get_cursor_pos()
        nx = max(0, min(self._screen_w - 1, cx + dx * self.sensitivity))
        ny = max(0, min(self._screen_h - 1, cy - dy * self.sensitivity))

        if int(nx) != cx or int(ny) != cy:
            _set_cursor_pos(nx, ny)


# ── Click / Drag / Scroll Controller ────────────────────────────────────────

class ClickController:
    """
    Maps phone roll (tilt sideways) to clicks, drags, and scrolls.

    Roll zones (from centre outward):
    ┌─────────────────────────────────────────────────────────┐
    │  0°           reset    click_thresh      scroll_thresh  │
    │  ├── neutral ──┤── buffer ──┤── click/drag ──┤── scroll │
    └─────────────────────────────────────────────────────────┘

    Gestures:
      • Quick tilt past click_thresh + return to centre  →  CLICK
      • Hold past click_thresh for hold_time seconds     →  DRAG (button held)
      • Tilt past scroll_thresh                          →  SCROLL continuously
      • Return to centre                                 →  release everything

    Parameters
    ----------
    click_threshold  : degrees to trigger click/drag zone (default 20°)
    scroll_threshold : degrees to trigger scroll zone (default 35°)
    reset_zone       : degrees from centre to reset state (default 10°)
    hold_time        : seconds before click becomes drag (default 1.5s)
    scroll_interval  : frames between scroll ticks (default 8 ≈ 7.5/sec)
    """

    IDLE      = 0
    PENDING   = 1    # tilted past click threshold, deciding click vs drag
    DRAGGING  = 2    # mouse button held down
    SCROLLING = 3    # continuously scrolling

    def __init__(self, click_threshold=20.0, scroll_threshold=35.0,
                 reset_zone=10.0, hold_time=1.5, scroll_interval=8):
        self.click_threshold  = click_threshold
        self.scroll_threshold = scroll_threshold
        self.reset_zone       = reset_zone
        self.hold_time        = hold_time
        self.scroll_interval  = scroll_interval

        self._state           = self.IDLE
        self._direction       = None    # 'left' or 'right'
        self._pending_since   = 0.0
        self._scroll_counter  = 0
        self._active          = False
        self.last_action      = None

    @property
    def active(self):
        return self._active

    @property
    def state(self):
        return self._state

    @property
    def direction(self):
        return self._direction

    def start(self):
        self._state = self.IDLE
        self._direction = None
        self._pending_since = 0.0
        self._scroll_counter = 0
        self._active = True
        self.last_action = None

    def stop(self):
        """Release any held button before stopping."""
        if self._state == self.DRAGGING and self._direction:
            _mouse_up(self._direction)
        self._active = False
        self._state = self.IDLE
        self._direction = None
        self.last_action = None

    def set_click_threshold(self, v):
        self.click_threshold = max(5.0, min(45.0, v))

    def set_scroll_threshold(self, v):
        self.scroll_threshold = max(self.click_threshold + 5.0, min(60.0, v))

    def set_reset_zone(self, v):
        self.reset_zone = max(2.0, min(self.click_threshold - 1.0, v))

    def update(self, roll):
        """
        Call each frame with calibrated roll (degrees from neutral).
        Negative = tilted left, positive = tilted right.

        Returns an action string or None:
          'left_click', 'right_click',
          'left_drag_start', 'right_drag_start',
          'left_drag_end', 'right_drag_end',
          'scroll_up', 'scroll_down',
          None
        """
        if not self._active:
            return None

        abs_roll  = abs(roll)
        direction = 'left' if roll < 0 else 'right'
        now       = time.time()
        result    = None

        # ── IDLE ─────────────────────────────────────────────────────────
        if self._state == self.IDLE:
            if abs_roll >= self.scroll_threshold:
                self._enter_scrolling(direction)
            elif abs_roll >= self.click_threshold:
                self._state = self.PENDING
                self._direction = direction
                self._pending_since = now

        # ── PENDING (deciding: click vs drag vs scroll) ──────────────────
        elif self._state == self.PENDING:
            if abs_roll < self.reset_zone:
                # Quick tilt + return → CLICK
                if self._direction == 'left':
                    _left_click()
                    result = 'left_click'
                else:
                    _right_click()
                    result = 'right_click'
                self._reset()

            elif abs_roll >= self.scroll_threshold:
                # Tilted further → SCROLL
                self._enter_scrolling(self._direction)

            elif (now - self._pending_since) >= self.hold_time:
                # Held long enough → DRAG
                _mouse_down(self._direction)
                self._state = self.DRAGGING
                result = self._direction + '_drag_start'

        # ── DRAGGING (button held down) ──────────────────────────────────
        elif self._state == self.DRAGGING:
            if abs_roll < self.reset_zone:
                # Return to centre → release
                _mouse_up(self._direction)
                result = self._direction + '_drag_end'
                self._reset()

            elif abs_roll >= self.scroll_threshold:
                # Tilted into scroll → release drag, start scroll
                _mouse_up(self._direction)
                self._enter_scrolling(self._direction)

        # ── SCROLLING (continuous) ───────────────────────────────────────
        elif self._state == self.SCROLLING:
            if abs_roll < self.reset_zone:
                self._reset()
            elif abs_roll < self.scroll_threshold:
                # Came back from scroll zone but not to centre → stop
                self._reset()
            else:
                # Still in scroll zone → tick
                self._scroll_counter += 1
                if self._scroll_counter >= self.scroll_interval:
                    self._scroll_counter = 0
                    if self._direction == 'left':
                        _scroll(WHEEL_DELTA)
                        result = 'scroll_up'
                    else:
                        _scroll(-WHEEL_DELTA)
                        result = 'scroll_down'

        if result:
            self.last_action = result
        return result

    # ── Internal helpers ─────────────────────────────────────────────────

    def _enter_scrolling(self, direction):
        self._state = self.SCROLLING
        self._direction = direction
        self._scroll_counter = 0

    def _reset(self):
        self._state = self.IDLE
        self._direction = None
        self._scroll_counter = 0