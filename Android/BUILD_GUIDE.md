# AirMouse Android App — Build Guide

## Project Structure

```
airmouse_android/
├── src/
│   ├── main.py                    ← Kivy app (Phases 1 + 2)
│   ├── udp_sender.py              ← UDP transmission module (Phase 2)
│   └── udp_receiver_windows.py    ← Updated Windows receiver (Phase 3)
├── buildozer.spec                 ← APK build config
└── BUILD_GUIDE.md                 ← This file
```

---

## What's Implemented

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Read TYPE_GAME_ROTATION_VECTOR → Yaw/Pitch/Roll display | ✅ Done |
| 2 | UDP transmission of yaw/pitch/roll JSON | ✅ Done |
| 3 | Windows receiver (yaw/pitch/roll JSON) | ✅ Done |
| 4 | Map Yaw→X, Pitch→Y cursor control | 🔜 Next |
| 5 | Calibration (set zero) | ✅ Done (in app) |
| 6 | Smoothing (low-pass filter) | 🔜 Next |
| 7 | Dead zone | 🔜 Next |
| 8 | Tap/swipe gestures → click/scroll | 🔜 Next |
| 9 | Replace HyperIMU completely | 🔜 After Phase 2 tested |
| 10 | APK + EXE packaging | 🔜 Last |

---

## Desktop Testing (No Android Needed)

Run the Kivy app on your PC to verify the UI:

```bash
pip install kivy
python src/main.py
```

The app will show animated sine-wave values simulating the sensor.
The UDP sender will activate when you tap ▶ STREAM (it will silently
fail to transmit until a valid IP is set — that's expected).

---

## Building the APK

### Prerequisites

Install Buildozer (Linux or WSL required):

```bash
# Ubuntu / WSL
sudo apt update
sudo apt install -y python3-pip python3-venv git \
    openjdk-17-jdk autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev \
    cmake libffi-dev libssl-dev

pip install buildozer cython
```

### First Build

```bash
cd airmouse_android
buildozer android debug
```

First build downloads Android SDK/NDK (~2–4 GB) and takes 20–40 minutes.
Subsequent builds: ~2–5 minutes.

APK output: `airmouse_android/bin/airmouse-0.1.0-arm64-v8a-debug.apk`

### Install on Phone

```bash
# USB debugging must be enabled on the phone
adb install bin/airmouse-*.apk
```

Or transfer the APK file to your phone and install manually
(allow "Install from unknown sources" in Android settings).

---

## Using the App

1. **Open AirMouse** on Android.
2. Tap **⚙ Settings** and enter your Windows PC's IP address.
   - Find your PC IP: open Command Prompt → `ipconfig` → look for IPv4 address.
   - Both devices must be on the same Wi-Fi network.
3. Return to the main screen.
4. Point phone at screen, tap **SET ZERO** to calibrate neutral position.
5. Tap **▶ STREAM** — the app starts sending yaw/pitch/roll to Windows.

### Windows side

Replace your existing HyperIMU receiver with `udp_receiver_windows.py`:

```python
from udp_receiver_windows import UDPReceiver

def on_data(d):
    print(f"Yaw={d.yaw:.1f}  Pitch={d.pitch:.1f}  Roll={d.roll:.1f}")

receiver = UDPReceiver(on_data=on_data)
receiver.start()
```

---

## Data Format

### Android → Windows (UDP, port 5005)

Every ~16 ms (60 Hz):

```json
{"yaw": 15.2, "pitch": -8.4, "roll": 2.1}
```

Every 1 second (keepalive):

```json
{"type": "heartbeat"}
```

### Angle Meanings

| Angle | Axis | Positive direction | Maps to |
|-------|------|--------------------|---------|
| Yaw   | Z    | Phone rotates right | Cursor X |
| Pitch | X    | Phone tilts up      | Cursor Y |
| Roll  | Y    | Phone tilts right   | (unused) |

---

## Next Steps (Phase 4 onwards)

### Phase 4 — Cursor Mapping

In your Windows `on_data` callback:

```python
SENSITIVITY = 15.0   # pixels per degree

def on_data(d):
    dx = int(d.yaw   * SENSITIVITY)
    dy = int(d.pitch * SENSITIVITY)
    mouse.move(dx, dy)
```

### Phase 6 — Smoothing

Exponential moving average:

```python
ALPHA = 0.3   # 0 = no change, 1 = raw

class EMA:
    def __init__(self): self.v = None
    def update(self, x):
        self.v = x if self.v is None else ALPHA * x + (1 - ALPHA) * self.v
        return self.v

yaw_ema = EMA()
smooth_yaw = yaw_ema.update(d.yaw)
```

### Phase 7 — Dead Zone

```python
DEAD_ZONE = 2.0   # degrees

def apply_dead_zone(v, dz):
    if abs(v) < dz:
        return 0.0
    return v - math.copysign(dz, v)
```

### Phase 8 — Gestures

Add to `main.py` MainScreen — bind `on_touch_down`, `on_touch_up`:

```python
# Single tap → left click
# Long press → right click  
# Two-finger swipe → scroll
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App crashes on start | Check `adb logcat` for Java exceptions |
| Sensor not updating | Phone may not have gyroscope; check in Android settings |
| UDP packets not arriving | Check Windows Firewall — allow UDP port 5005 |
| High latency | Switch to `SENSOR_DELAY_FASTEST` in `SensorListener.start()` |
| Build fails (NDK) | Run `buildozer android clean` then rebuild |
