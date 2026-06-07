import sys
import threading
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
from receiver import AirMouseReceiver

class DesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Desktop App")
        self.setGeometry(100, 100, 400, 300)
        self.resize(350, 300)

        self.connection_status = "Waiting for Phone"
        self.calibration_status = "Not Calibrated"

        # Use pitch/roll/yaw naming (matches UDPReceiver payload)
        self.current_pitch = 0.0
        self.current_roll = 0.0
        self.current_yaw = 0.0

        self.base_pitch = 0.0
        self.base_roll = 0.0
        self.base_yaw = 0.0

        self.delta_pitch = 0.0
        self.delta_roll = 0.0
        self.delta_yaw = 0.0

        self.mouse_dpitch = 0.0
        self.mouse_droll = 0.0
        self.mouse_dyaw = 0.0

        self.active_axis = "pitch"

        self.receiver = AirMouseReceiver()

        self.initUI()
        self.start_receiver()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        self.status_label = QLabel(f"Status: {self.connection_status}")
        self.calibration_label = QLabel(f"Calibration: {self.calibration_status}")


        self.pitch_label = QLabel("Pitch: 0.000")
        self.roll_label = QLabel("Roll: 0.000")
        self.yaw_label = QLabel("Yaw: 0.000")

        self.base_pitch_label = QLabel("Base Pitch: 0.000")
        self.base_roll_label = QLabel("Base Roll: 0.000")
        self.base_yaw_label = QLabel("Base Yaw: 0.000")

        self.delta_pitch_label = QLabel("ΔPitch: 0.000")
        self.delta_roll_label = QLabel("ΔRoll: 0.000")
        self.delta_yaw_label = QLabel("ΔYaw: 0.000")

        self.mouse_dpitch_label = QLabel("Mouse DPitch: 0")
        self.mouse_droll_label = QLabel("Mouse DRoll: 0")
        self.mouse_dyaw_label = QLabel("Mouse DYaw: 0")

        self.active_axis_label = QLabel("Active Axis: X")
        self.axis_note_label = QLabel("Axis test mode: move the phone and watch which delta changes")
        self.lr_title_label = QLabel("Left/Right:")
        self.lr_x_label = QLabel("X score: 0.000")
        self.lr_y_label = QLabel("Y score: 0.000")
        self.lr_z_label = QLabel("Z score: 0.000")

        self.ud_title_label = QLabel("Up/Down:")
        self.ud_x_label = QLabel("X score: 0.000")
        self.ud_y_label = QLabel("Y score: 0.000")
        self.ud_z_label = QLabel("Z score: 0.000")
        self.lr_candidate_label = QLabel("Left/Right candidate: -")
        self.ud_candidate_label = QLabel("Up/Down candidate: -")

        self.axis_pitch_button = QPushButton("Use Pitch")
        self.axis_roll_button = QPushButton("Use Roll")
        self.axis_yaw_button = QPushButton("Use Yaw")

        self.axis_pitch_button.clicked.connect(lambda: self.set_active_axis("pitch"))
        self.axis_roll_button.clicked.connect(lambda: self.set_active_axis("roll"))
        self.axis_yaw_button.clicked.connect(lambda: self.set_active_axis("yaw"))

        self.calibrate_button = QPushButton("Calibrate")
        self.calibrate_button.clicked.connect(self.calibrate)

        layout.addWidget(self.status_label)
        layout.addWidget(self.calibration_label)

        layout.addWidget(self.pitch_label)
        layout.addWidget(self.roll_label)
        layout.addWidget(self.yaw_label)

        layout.addWidget(self.base_pitch_label)
        layout.addWidget(self.base_roll_label)
        layout.addWidget(self.base_yaw_label)

        layout.addWidget(self.delta_pitch_label)
        layout.addWidget(self.delta_roll_label)
        layout.addWidget(self.delta_yaw_label)

        layout.addWidget(self.mouse_dpitch_label)
        layout.addWidget(self.mouse_droll_label)
        layout.addWidget(self.mouse_dyaw_label)

        layout.addWidget(self.active_axis_label)
        layout.addWidget(self.axis_note_label)
        layout.addWidget(self.lr_title_label)
        layout.addWidget(self.lr_x_label)
        layout.addWidget(self.lr_y_label)
        layout.addWidget(self.lr_z_label)
        layout.addWidget(self.ud_title_label)
        layout.addWidget(self.ud_x_label)
        layout.addWidget(self.ud_y_label)
        layout.addWidget(self.ud_z_label)
        layout.addWidget(self.lr_candidate_label)
        layout.addWidget(self.ud_candidate_label)
        layout.addWidget(self.axis_pitch_button)
        layout.addWidget(self.axis_roll_button)
        layout.addWidget(self.axis_yaw_button)

        layout.addWidget(self.calibrate_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.update_labels()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_values)
        self.timer.start(100)

    def start_receiver(self):
        self.receiver_thread = threading.Thread(
            target=self.receiver.run,
            daemon=True
        )
        self.receiver_thread.start()

    
    def update_labels(self):
        self.delta_pitch = self.current_pitch - self.base_pitch
        self.delta_roll = self.current_roll - self.base_roll
        self.delta_yaw = self.current_yaw - self.base_yaw

        self.mouse_dpitch = self.delta_pitch
        self.mouse_droll = self.delta_roll
        self.mouse_dyaw = self.delta_yaw

        self.status_label.setText(f"Status: {self.connection_status}")
        self.calibration_label.setText(f"Calibration: {self.calibration_status}")
        self.pitch_label.setText(f"Pitch: {self.current_pitch:.3f}")
        self.roll_label.setText(f"Roll: {self.current_roll:.3f}")
        self.yaw_label.setText(f"Yaw: {self.current_yaw:.3f}")

        self.base_pitch_label.setText(f"Base Pitch: {self.base_pitch:.3f}")
        self.base_roll_label.setText(f"Base Roll: {self.base_roll:.3f}")
        self.base_yaw_label.setText(f"Base Yaw: {self.base_yaw:.3f}")

        self.delta_pitch_label.setText(f"ΔPitch: {self.delta_pitch:.3f}")
        self.delta_roll_label.setText(f"ΔRoll: {self.delta_roll:.3f}")
        self.delta_yaw_label.setText(f"ΔYaw: {self.delta_yaw:.3f}")

        self.mouse_dpitch_label.setText(f"Mouse DPitch: {self.mouse_dpitch:.3f}")
        self.mouse_droll_label.setText(f"Mouse DRoll: {self.mouse_droll:.3f}")
        self.mouse_dyaw_label.setText(f"Mouse DYaw: {self.mouse_dyaw:.3f}")
        self.active_axis_label.setText(f"Active Axis: {self.active_axis.upper()}")

        # Determine axis candidates by absolute magnitude (Pitch/Roll/Yaw)
        axes = [("Pitch", abs(self.delta_pitch)), ("Roll", abs(self.delta_roll)), ("Yaw", abs(self.delta_yaw))]
        axes_sorted = sorted(axes, key=lambda t: t[1], reverse=True)
        lr_candidate = axes_sorted[0][0] if axes_sorted else "-"
        ud_candidate = axes_sorted[1][0] if len(axes_sorted) > 1 else "-"

        self.lr_candidate_label.setText(f"Left/Right candidate: {lr_candidate} ({axes_sorted[0][1]:.3f})")
        if ud_candidate != "-":
            self.ud_candidate_label.setText(f"Up/Down candidate: {ud_candidate} ({axes_sorted[1][1]:.3f})")
        else:
            self.ud_candidate_label.setText("Up/Down candidate: -")

        # Show raw scores for LR and UD (per-axis, named Pitch/Roll/Yaw)
        p_score = abs(self.delta_pitch)
        r_score = abs(self.delta_roll)
        y_score = abs(self.delta_yaw)

        self.lr_x_label.setText(f"Pitch score: {p_score:.3f}")
        self.lr_y_label.setText(f"Roll score: {r_score:.3f}")
        self.lr_z_label.setText(f"Yaw score: {y_score:.3f}")

        self.ud_x_label.setText(f"Pitch score: {p_score:.3f}")
        self.ud_y_label.setText(f"Roll score: {r_score:.3f}")
        self.ud_z_label.setText(f"Yaw score: {y_score:.3f}")

    def set_active_axis(self, axis):
        self.active_axis = axis
        self.update_labels()

    def calibrate(self):
        self.base_pitch = self.current_pitch
        self.base_roll = self.current_roll
        self.base_yaw = self.current_yaw
        self.calibration_status = "Calibrated"
        self.update_labels()

    def update_sensor_values(self):
        # Pull latest orientation from the receiver (yaw/pitch/roll)
        # UDPReceiver provides .pitch, .roll, .yaw
        self.current_pitch = self.receiver.pitch
        self.current_roll = self.receiver.roll
        self.current_yaw = self.receiver.yaw

        self.connection_status = "Connected" if self.receiver.connected else "Waiting for Phone"
        self.update_labels()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopApp()
    window.show()
    sys.exit(app.exec_())
