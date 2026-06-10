# AirMouse 📱➡️🖱️

Turn your Android smartphone into a highly responsive, gesture-based spatial mouse for your PC using Wi-Fi. 

## ✨ Features

### ✅ Currently Implemented

**Core System & Sensors**
- [x] **Low-Latency UDP Streaming**: 60Hz real-time sensor streaming from phone to PC.
- [x] **World-Referenced Tracking**: Uses Android's native `SensorManager` rotation vectors to ensure "up" is always "up", preventing axis-swapping regardless of how you hold the phone.
- [x] **Auto-Discovery**: No manual IP typing. The Android app broadcasts to automatically find the Desktop receiver on your Wi-Fi network.
- [x] **Relative Cursor Movement**: True mouse-like delta tracking (angle changes = displacement) rather than joystick-style movement, preventing drift and zero-crossing issues.

**Controls & Gestures**
- [x] **Roll-to-Click**: Quick tilt left/right to execute left and right mouse clicks.
- [x] **Hold-to-Drag**: Tilt and hold to keep the mouse button pressed (perfect for dragging windows or selecting text).
- [x] **Deep Roll to Scroll**: Tilt past a designated threshold to continuously scroll up or down.
- [x] **Adjustable Sensitivity & Smoothing**: Fine-tune cursor speed, dead zones (to ignore shaky hands), and smoothing via the desktop UI.

**Stability & UI**
- [x] **Auto-Calibration**: The desktop app automatically zeroes its axes the moment the phone connects, ensuring instant synchronization.
- [x] **Safety Cutoff**: The cursor automatically stops moving if the phone disconnects or stops streaming, preventing infinite looping or runaway cursors.
- [x] **Persistent Settings**: All custom sensitivities and thresholds are saved locally (`settings.json`).
- [x] **Premium UI**: Clean, dark-mode interfaces for both the Android app (Kivy + FontAwesome) and Desktop app (PyQt5).

---

### 🚀 Planned & Potential Features (Ideas for the Future)

**Connectivity & Platforms**
- [ ] **Bluetooth (BLE) Fallback**: Support for Bluetooth streaming when a local Wi-Fi network is unavailable.
- [ ] **macOS / Linux Support**: Expand the desktop receiver beyond Windows `ctypes` (e.g., using `pynput` or `pyautogui`).
- [ ] **Security/Pairing PIN**: Add a simple PIN handshake so unauthorized users on the same Wi-Fi cannot control your mouse.

**Advanced Interactions**
- [ ] **Background Service**: Allow the Android app to stream sensor data while the screen is off to save battery life.
- [ ] **Custom Keybinds**: Map specific tilts or gestures to keyboard macros (e.g., media play/pause, volume control, or presentation next-slide).
- [ ] **Multi-Monitor Mapping**: Better handling of absolute vs relative positioning across multiple displays.
- [ ] **Pitch-based Scrolling / Zooming**: Hold a UI button on the phone and pitch up/down to scroll or zoom.
- [ ] **Double Click Detection**: Detect two rapid roll tilts as a native double-click.

---

## 🛠️ Tech Stack
* **Android**: Python, Kivy, Pyjnius, Buildozer
* **Desktop**: Python, PyQt5, `ctypes` (Win32 API)
* **Protocol**: UDP JSON payloads
