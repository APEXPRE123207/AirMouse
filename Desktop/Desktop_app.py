"""
AirMouse – Desktop Companion  (Phase 3)

  • Yaw/Pitch → smooth cursor movement (relative mode)
  • Roll tilt → click / hold-drag / scroll
  • Auto-calibrate on connect, auto-stop on disconnect
  • Persisted settings, IP + port display
"""

import json
import os
import socket
import sys
import threading

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QFrame,
)

from receiver import AirMouseReceiver
from mouse_move import CursorController, ClickController


# ── Colours ──────────────────────────────────────────────────────────────────
BG            = "#111118"
CARD_BG       = "#1a1a24"
BORDER        = "#2a2a38"
TEXT_PRIMARY   = "#e8e8f0"
TEXT_DIM       = "#6a6a7a"
ACCENT_BLUE    = "#3b8beb"
ACCENT_GREEN   = "#2ecc71"
ACCENT_RED     = "#e74c3c"
ACCENT_ORANGE  = "#f39c12"
ACCENT_PURPLE  = "#9b59b6"

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
LISTEN_PORT   = 5005


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _card_frame():
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background-color: {CARD_BG};
            border: 1px solid {BORDER};
            border-radius: 12px;
        }}
    """)
    return f


def _heading(text, size=11, color=TEXT_DIM):
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", size, QFont.Bold))
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
    return lbl


def _value_label(text="0.0", size=22, color=TEXT_PRIMARY):
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", size, QFont.Bold))
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def _load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ── Main window ──────────────────────────────────────────────────────────────

class DesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AirMouse")
        self.setWindowIcon(QIcon("logo.jpg"))
        self.setFixedSize(380, 740)
        self.setStyleSheet(f"background-color: {BG};")

        self.current_yaw = self.current_pitch = self.current_roll = 0.0
        self.base_yaw = self.base_pitch = self.base_roll = 0.0
        self._was_connected = False
        self._auto_calibrated = False
        self._click_label_locked = False   # True while showing momentary click text

        self.receiver   = AirMouseReceiver()
        self.cursor_ctl = CursorController()
        self.click_ctl  = ClickController()

        self._settings = _load_settings()
        self._build_ui()
        self._apply_saved_settings()
        self._start_receiver()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(16, 20, 16, 14)
        lay.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("A I R M O U S E")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self._status_dot = QLabel("●")
        self._status_dot.setFont(QFont("Segoe UI", 12))
        self._status_dot.setStyleSheet(f"color: {TEXT_DIM};")
        self._status_label = QLabel("Waiting…")
        self._status_label.setFont(QFont("Segoe UI", 10))
        self._status_label.setStyleSheet(f"color: {TEXT_DIM};")
        hdr.addWidget(title); hdr.addStretch()
        hdr.addWidget(self._status_dot); hdr.addWidget(self._status_label)
        lay.addLayout(hdr)

        # Network info
        net = _card_frame()
        nl = QHBoxLayout(net)
        nl.setContentsMargins(14, 8, 14, 8)
        ip_sec = QVBoxLayout(); ip_sec.setSpacing(1)
        ip_sec.addWidget(_heading("YOUR PC IP", 8))
        ip_val = QLabel(_get_local_ip())
        ip_val.setFont(QFont("Consolas", 13, QFont.Bold))
        ip_val.setStyleSheet(f"color: {ACCENT_BLUE}; background: transparent; border: none;")
        ip_sec.addWidget(ip_val)
        port_sec = QVBoxLayout(); port_sec.setSpacing(1)
        port_sec.addWidget(_heading("PORT", 8))
        port_val = QLabel(str(LISTEN_PORT))
        port_val.setFont(QFont("Consolas", 13, QFont.Bold))
        port_val.setStyleSheet(f"color: {ACCENT_ORANGE}; background: transparent; border: none;")
        port_sec.addWidget(port_val)
        nl.addLayout(ip_sec); nl.addStretch(); nl.addLayout(port_sec)
        lay.addWidget(net)

        # Angles
        ang = _card_frame()
        ag = QGridLayout(ang)
        ag.setContentsMargins(14, 8, 14, 8); ag.setSpacing(2)
        ag.addWidget(_heading("YAW",   9, ACCENT_BLUE),   0, 0, Qt.AlignCenter)
        ag.addWidget(_heading("PITCH", 9, ACCENT_GREEN),  0, 1, Qt.AlignCenter)
        ag.addWidget(_heading("ROLL",  9, ACCENT_ORANGE), 0, 2, Qt.AlignCenter)
        self._yaw_lbl   = _value_label("0.0°", 17, ACCENT_BLUE)
        self._pitch_lbl = _value_label("0.0°", 17, ACCENT_GREEN)
        self._roll_lbl  = _value_label("0.0°", 17, ACCENT_ORANGE)
        ag.addWidget(self._yaw_lbl, 1, 0)
        ag.addWidget(self._pitch_lbl, 1, 1)
        ag.addWidget(self._roll_lbl, 1, 2)
        lay.addWidget(ang)

        # Action indicator
        self._action_lbl = QLabel("")
        self._action_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._action_lbl.setAlignment(Qt.AlignCenter)
        self._action_lbl.setFixedHeight(22)
        self._action_lbl.setStyleSheet(f"color: {TEXT_DIM};")
        lay.addWidget(self._action_lbl)

        # Sliders
        sc = _card_frame()
        sl = QVBoxLayout(sc)
        sl.setContentsMargins(14, 10, 14, 10); sl.setSpacing(6)

        self._sens_slider, _ = self._slider(sl, "SENSITIVITY", 1, 30, 10,
                                            self._on_sensitivity)
        self._dz_slider, _ = self._slider(sl, "DEAD ZONE", 0, 50, 5,
                                          self._on_dead_zone,
                                          fmt=lambda v: f"{v/100:.2f}°")
        self._sm_slider, _ = self._slider(sl, "SMOOTHING", 10, 100, 100,
                                          self._on_smoothing,
                                          fmt=lambda v: f"{v/100:.2f}")
        self._ct_slider, _ = self._slider(sl, "CLICK TILT", 5, 40, 20,
                                          self._on_click_threshold,
                                          fmt=lambda v: f"{v}°")
        self._st_slider, _ = self._slider(sl, "SCROLL TILT", 20, 55, 35,
                                          self._on_scroll_threshold,
                                          fmt=lambda v: f"{v}°")
        lay.addWidget(sc)

        # Buttons
        btns = QHBoxLayout(); btns.setSpacing(10)
        self._cal_btn = self._btn("CALIBRATE", ACCENT_BLUE)
        self._cal_btn.clicked.connect(self._calibrate)
        self._ctrl_btn = self._btn("START", ACCENT_GREEN)
        self._ctrl_btn.clicked.connect(self._toggle_control)
        btns.addWidget(self._cal_btn); btns.addWidget(self._ctrl_btn)
        lay.addLayout(btns)

        lay.addStretch()

        hint = QLabel("Quick tilt = click · Hold tilt = drag · Tilt more = scroll")
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet(f"color: {TEXT_DIM};")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)

    def _slider(self, parent, label, lo, hi, default, cb, fmt=None):
        if fmt is None: fmt = str
        row = QHBoxLayout()
        lbl = _heading(label, 9)
        val = QLabel(fmt(default))
        val.setFont(QFont("Segoe UI", 10, QFont.Bold))
        val.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent; border: none;")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl); row.addStretch(); row.addWidget(val)
        parent.addLayout(row)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi); s.setValue(default)
        s.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background:{BORDER}; height:6px; border-radius:3px; }}
            QSlider::handle:horizontal {{ background:{ACCENT_BLUE}; width:16px; height:16px; margin:-5px 0; border-radius:8px; }}
            QSlider::sub-page:horizontal {{ background:{ACCENT_BLUE}; border-radius:3px; }}
        """)
        s.valueChanged.connect(lambda v: (val.setText(fmt(v)), cb(v)))
        parent.addWidget(s)
        return s, val

    def _btn(self, text, color):
        b = QPushButton(text)
        b.setFont(QFont("Segoe UI", 11, QFont.Bold))
        b.setFixedHeight(44); b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(self._bstyle(color))
        return b

    @staticmethod
    def _bstyle(c):
        return f"""QPushButton{{ background-color:{c}; color:white; border:none;
            border-radius:12px; padding:0 18px; }}
            QPushButton:hover{{ background-color:{c}cc; }}
            QPushButton:pressed{{ background-color:{c}99; }}"""

    # ── Settings persistence ─────────────────────────────────────────────

    def _apply_saved_settings(self):
        s = self._settings
        for key, slider in [("sensitivity", self._sens_slider),
                            ("dead_zone", self._dz_slider),
                            ("smoothing", self._sm_slider),
                            ("click_threshold", self._ct_slider),
                            ("scroll_threshold", self._st_slider)]:
            if key in s:
                slider.setValue(int(s[key]))

    def _persist(self):
        _save_settings({
            "sensitivity":      self._sens_slider.value(),
            "dead_zone":        self._dz_slider.value(),
            "smoothing":        self._sm_slider.value(),
            "click_threshold":  self._ct_slider.value(),
            "scroll_threshold": self._st_slider.value(),
        })

    # ── Slider callbacks ─────────────────────────────────────────────────

    def _on_sensitivity(self, v):
        self.cursor_ctl.set_sensitivity(float(v)); self._persist()

    def _on_dead_zone(self, v):
        self.cursor_ctl.set_dead_zone(v / 100.0); self._persist()

    def _on_smoothing(self, v):
        self.cursor_ctl.set_smoothing(v / 100.0); self._persist()

    def _on_click_threshold(self, v):
        self.click_ctl.set_click_threshold(float(v))
        self.click_ctl.set_reset_zone(max(5.0, float(v) * 0.5))
        # Enforce scroll > click
        if self._st_slider.value() <= v + 5:
            self._st_slider.setValue(v + 10)
        self._persist()

    def _on_scroll_threshold(self, v):
        self.click_ctl.set_scroll_threshold(float(v))
        # Enforce scroll > click
        if v <= self._ct_slider.value() + 5:
            self._ct_slider.setValue(max(5, v - 10))
        self._persist()

    # ── Buttons ──────────────────────────────────────────────────────────

    def _calibrate(self, silent=False):
        self.base_yaw   = self.current_yaw
        self.base_pitch = self.current_pitch
        self.base_roll  = self.current_roll
        if not silent:
            self._cal_btn.setText("ZEROED")
            QTimer.singleShot(1200, lambda: self._cal_btn.setText("CALIBRATE"))

    def _toggle_control(self):
        if self.cursor_ctl.active:
            self._stop_control()
        else:
            self._start_control()

    def _start_control(self):
        self.cursor_ctl.start(); self.click_ctl.start()
        self._ctrl_btn.setText("STOP")
        self._ctrl_btn.setStyleSheet(self._bstyle(ACCENT_RED))

    def _stop_control(self):
        self.cursor_ctl.stop(); self.click_ctl.stop()
        self._ctrl_btn.setText("START")
        self._ctrl_btn.setStyleSheet(self._bstyle(ACCENT_GREEN))
        self._action_lbl.setText("")

    # ── Receiver ─────────────────────────────────────────────────────────

    def _start_receiver(self):
        threading.Thread(target=self.receiver.run, daemon=True).start()

    # ── Main loop ────────────────────────────────────────────────────────

    def _tick(self):
        connected = self.receiver.connected

        # Auto-calibrate on (re)connect
        if not self._was_connected and connected:
            QTimer.singleShot(300, lambda: self._calibrate(silent=True))

        # Auto-stop on disconnect
        if self._was_connected and not connected and self.cursor_ctl.active:
            self._stop_control()

        self._was_connected = connected

        # Read values
        self.current_yaw   = self.receiver.yaw
        self.current_pitch = self.receiver.pitch
        self.current_roll  = self.receiver.roll

        dy = self.current_yaw   - self.base_yaw
        dp = self.current_pitch - self.base_pitch
        dr = self.current_roll  - self.base_roll

        self._yaw_lbl.setText(f"{dy:+.1f}°")
        self._pitch_lbl.setText(f"{dp:+.1f}°")
        self._roll_lbl.setText(f"{dr:+.1f}°")

        if connected:
            self._status_dot.setStyleSheet(f"color: {ACCENT_GREEN};")
            self._status_label.setText("Connected")
            self._status_label.setStyleSheet(f"color: {ACCENT_GREEN};")
        else:
            self._status_dot.setStyleSheet(f"color: {TEXT_DIM};")
            self._status_label.setText("Waiting…")
            self._status_label.setStyleSheet(f"color: {TEXT_DIM};")

        # ── Anti-Jitter Click Stabilization ──────────────────────────────
        # Freeze cursor movement when rolling past 8° to prevent slip before clicking,
        # but ALLOW cursor movement if we are actively dragging so the user can drag!
        is_rolling   = abs(dr) > 8.0
        is_dragging  = self.click_ctl.state == ClickController.DRAGGING
        pause_cursor = is_rolling and not is_dragging

        # Cursor movement
        self.cursor_ctl.update(self.current_yaw, self.current_pitch, paused=pause_cursor)

        # Click / drag / scroll
        action = self.click_ctl.update(dr)

        # ── Update action indicator ──────────────────────────────────────
        state = self.click_ctl.state
        dirn  = self.click_ctl.direction

        if state == ClickController.DRAGGING:
            arrow = "L" if dirn == 'left' else "R"
            self._action_lbl.setText(f"DRAGGING {arrow}")
            self._action_lbl.setStyleSheet(f"color: {ACCENT_RED};")
            self._click_label_locked = False

        elif state == ClickController.SCROLLING:
            if dirn == 'left':
                self._action_lbl.setText("SCROLLING UP")
            else:
                self._action_lbl.setText("SCROLLING DOWN")
            self._action_lbl.setStyleSheet(f"color: {ACCENT_PURPLE};")
            self._click_label_locked = False

        elif action and 'click' in action:
            label = "LEFT CLICK" if 'left' in action else "RIGHT CLICK"
            color = ACCENT_BLUE if 'left' in action else ACCENT_ORANGE
            self._action_lbl.setText(label)
            self._action_lbl.setStyleSheet(f"color: {color};")
            self._click_label_locked = True
            QTimer.singleShot(700, self._unlock_action_label)

        elif not self._click_label_locked and state == ClickController.IDLE:
            self._action_lbl.setText("")

    def _unlock_action_label(self):
        self._click_label_locked = False
        if self.click_ctl.state == ClickController.IDLE:
            self._action_lbl.setText("")

    def closeEvent(self, event):
        self._persist()
        self.cursor_ctl.stop()
        self.click_ctl.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG))
    pal.setColor(QPalette.WindowText,      QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Base,            QColor(CARD_BG))
    pal.setColor(QPalette.AlternateBase,   QColor(CARD_BG))
    pal.setColor(QPalette.Text,            QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Button,          QColor(CARD_BG))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT_BLUE))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)
    w = DesktopApp()
    w.show()
    sys.exit(app.exec_())
