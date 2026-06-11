import json
import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect

BG            = "#111118"
CARD_BG       = "#1a1a24"
TEXT_PRIMARY  = "#e8e8f0"
TEXT_DIM      = "#6a6a7a"
ACCENT_BLUE   = "#3b8beb"
ACCENT_GREEN  = "#2ecc71"
ACCENT_ORANGE = "#f39c12"

class ClickCalibWizard(QWidget):
    """The wizard that measures how badly your hands shake."""
    def __init__(self, parent_widget, on_complete_cb):
        super().__init__(parent_widget, Qt.Window)
        self.setWindowTitle("Click Calibration")
        self.on_complete_cb = on_complete_cb
        self.resize(340, 420)
        
        # Solid background
        self.setStyleSheet(f"background-color: {BG};")
        
        self.state = "INTRO"
        
        # Tracking variables
        self.base_y = 0.0
        self.base_p = 0.0
        self.max_roll = 0.0
        self.err_y = 0.0
        self.err_p = 0.0
        
        self.results = {}
        
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 40, 30, 40)
        lay.setSpacing(16)
        
        self.title = QLabel("Click Calibration")
        self.title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.title.setAlignment(Qt.AlignCenter)
        
        self.msg = QLabel(
            "When you twist your wrist to click, the cursor often drifts.\n\n"
            "Let's measure that drift and cancel it out automatically!"
        )
        self.msg.setFont(QFont("Segoe UI", 11))
        self.msg.setStyleSheet(f"color: {TEXT_DIM};")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        
        self.btn = QPushButton("START")
        self.btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.btn.setFixedHeight(50)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_BLUE}; color: white; border: none; border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_BLUE}cc; }}
        """)
        self.btn.clicked.connect(self._on_btn_clicked)
        
        self.skip_btn = QPushButton("Skip for now")
        self.skip_btn.setFont(QFont("Segoe UI", 10))
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {TEXT_DIM}; border: none; text-decoration: underline;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        self.skip_btn.clicked.connect(self._finish)
        
        lay.addStretch()
        lay.addWidget(self.title)
        lay.addWidget(self.msg)
        lay.addSpacing(20)
        lay.addWidget(self.btn)
        lay.addWidget(self.skip_btn)
        lay.addStretch()

    def _on_btn_clicked(self):
        if self.state == "INTRO":
            self.state = "WAIT_LEFT"
            self.title.setText("Left Click")
            self.title.setStyleSheet(f"color: {ACCENT_BLUE};")
            self.msg.setText("Twist your phone LEFT (like a left click) and twist back to neutral.")
            self.btn.hide()
            self.skip_btn.hide()
            self.max_roll = 0.0
            
        elif self.state == "DONE":
            self._finish()

    def update_sensor(self, yaw, pitch, roll):
        if self.state not in ["WAIT_LEFT", "WAIT_RIGHT"]:
            return
            
        # Constantly update baseline while hand is neutral
        if abs(roll) < 5.0:
            self.base_y = yaw
            self.base_p = pitch
            
            # Did we just return from a deep roll?
            if abs(self.max_roll) > 15.0:
                if self.state == "WAIT_LEFT" and self.max_roll < -15.0:
                    self.results['err_left_yaw'] = self.err_y
                    self.results['err_left_pitch'] = self.err_p
                    self._next_state()
                elif self.state == "WAIT_RIGHT" and self.max_roll > 15.0:
                    self.results['err_right_yaw'] = self.err_y
                    self.results['err_right_pitch'] = self.err_p
                    self._next_state()
                    
            # Reset tracking for the next attempt
            self.max_roll = 0.0
            self.err_y = 0.0
            self.err_p = 0.0
            
        else:
            # We are rolling! Track the max deviation
            if abs(roll) > abs(self.max_roll):
                self.max_roll = roll
                
                # Calculate shortest angular distance for yaw
                dy = yaw - self.base_y
                if dy > 180: dy -= 360
                elif dy < -180: dy += 360
                
                dp = pitch - self.base_p
                
                self.err_y = dy
                self.err_p = dp

    def _next_state(self):
        if self.state == "WAIT_LEFT":
            self.state = "WAIT_RIGHT"
            self.title.setText("Right Click")
            self.title.setStyleSheet(f"color: {ACCENT_ORANGE};")
            self.msg.setText("Great! Now twist your phone RIGHT (like a right click) and twist back.")
            self.max_roll = 0.0
            
        elif self.state == "WAIT_RIGHT":
            self.state = "DONE"
            self.title.setText("All Set!")
            self.title.setStyleSheet(f"color: {ACCENT_GREEN};")
            
            left = f"L: {self.results['err_left_yaw']:+.1f}°, {self.results['err_left_pitch']:+.1f}°"
            right = f"R: {self.results['err_right_yaw']:+.1f}°, {self.results['err_right_pitch']:+.1f}°"
            
            self.msg.setText(f"Calibration successful.\n\n{left}\n{right}")
            self.btn.setText("FINISH")
            self.btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_GREEN}; color: white; border: none; border-radius: 12px;
                }}
                QPushButton:hover {{ background-color: {ACCENT_GREEN}cc; }}
            """)
            self.btn.show()

    def _finish(self):
        self.hide()
        self.on_complete_cb(self.results)
