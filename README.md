# AirMouse 📱➡️🖱️

Why spend $100 on a shiny Bluetooth presentation clicker when you already have a $1,000 glass rectangle in your pocket? 

Welcome to **AirMouse**, the project born out of the absolute refusal to get off the couch to change a YouTube video or skip a presentation slide. It turns your Android phone into a highly responsive, spatial air-mouse for your PC via Wi-Fi. 

*Because clicking physical buttons is a peasant activity.*

---

## ✨ Features (Yes, it actually works)

### ✅ What's Currently Built

**The "Magic" Physics Engine**
*   **Low-Latency UDP Streaming:** It blasts your sensor data to your PC at 60Hz. It's fast, it's reckless, and it works perfectly.
*   **World-Referenced Tracking:** We use Android's native `SensorManager` so "up" is actually "up." Go ahead, hold the phone upside down. It doesn't care. It knows where gravity is better than you do.
*   **Relative Cursor Movement:** Instead of snapping your cursor to absolute coordinates like a bad 90s joystick, it tracks deltas. Think of it like a real mouse, just floating in the air. 

**Wrist-Breaking Gestures**
*   **Roll-to-Click:** Flick your wrist left or right like you're aggressively turning a steering wheel. That's your left and right click.
*   **Hold-to-Drag:** Tilt past the threshold and hold it for 1.5 seconds. Congratulations, you are now dragging a window. Don't drop it.
*   **Deep Roll to Scroll:** Tilt the phone even further (past 35°) to scroll up and down.
*   **Anti-Jitter Cursor Freeze (with IK Sync):** Visually freezes the cursor the millisecond you start twisting to click so you don't miss your target. Meanwhile, the Inverse Kinematics engine tracks your hand in the background so when you unfreeze, the cursor doesn't jump or "walk" away.

**Stability & "Please don't crash" UI**
*   **Auto-Discovery:** Typing IP addresses manually is a crime against humanity. The Android app screams into the local network void, and the Desktop app replies. Auto-connect. Boom.
*   **Auto-Calibration:** Your PC zeroes the axes the exact millisecond the phone connects. No more cursors flying off into the top right corner of your monitor.
*   **Safety Cutoff:** If your phone dies or disconnects, the cursor stops dead in its tracks. No infinite loops, no runaway cursors, no ghost interactions.
*   **Premium Dark UI:** Because staring at white screens is blinding. Custom sliders, saved preferences, and FontAwesome icons.
*   **PIN Authorization:** No rogue cursors. A dynamic 4-digit PIN secures your session.
*   **Real-time Inverse Kinematics:** An interactive "Drift Fix" wizard actively cancels out your physiological wrist twitch when clicking.

---

## 📅 Version History

*   **v1:** The "Proof of Concept". Raw sensor data blasted to the PC resulting in a violently vibrating cursor.
*   **v2:** The "Actually Usable" update. Added basic smoothing and deadzones, making the cursor controllable but lacking clicks or a UI.
*   **v3:** The "Feature Complete" update. Added relative cursor mapping, auto-discovery, roll-to-click gestures, and the base PyQt5 UI.
*   **-> v4:** The "Clean & Secure" update. Modular UI architecture, 4-digit PIN authorization pairing, and the interactive Inverse Kinematics Click Drift Fix wizard.
*   **v5\***: The "Button Fallback" update. Adding alternative physical UI buttons on the Android app for left and right click, for those who don't want to use roll gestures.
*   **v6\***: The "Machine Learning" update. Personalized natural gesture recognition for clicking (learns your exact wrist twitch).

*\* indicates planned future version*

---

## 🚀 The "Whenever I Feel Like It" Roadmap (Future Ideas)

Because software is never actually "done," here are the things I might add when the caffeine hits:

*   [ ] **Bluetooth (BLE) Fallback:** Because sometimes Wi-Fi routers decide to stop working for absolutely no reason.
*   [ ] **macOS / Linux Support:** Currently built on Windows `ctypes`. Will eventually add `pynput` for the 3 people who want to air-mouse their Arch Linux setup.
*   [ ] **Background Service:** Let the Android app stream data while the screen is off so it doesn't drain your battery in 45 minutes.
*   [ ] **Custom Keybinds:** Map a violent wrist flick to Alt+F4. The possibilities are endless.

---

## 🛠️ The Tech Stack (What makes the magic happen)

*   **Android Client:** Python, Kivy, Pyjnius, Buildozer (Yes, it's Python on Android. Deal with it.)
*   **Desktop Server:** Python, PyQt5, `ctypes` (Injecting raw inputs directly into the Windows API).
*   **Protocol:** UDP JSON payloads (TCP is too slow and we like living on the edge).

---

## 📂 Project Structure (Where the spaghetti lives)

If you're brave enough to read the source code, here's what everything does:

**Android App**
*   `Android/src/main.py`: The Kivy frontend entry point. Hooks into the native Android `SensorManager` via Pyjnius to stream orientation.
*   `Android/src/ui_components.py`: Beautiful, modularized Kivy widgets (sliders, cards, buttons) to keep the UI clean.
*   `Android/src/settings_screen.py`: Handles Auto-Discovery, IP inputs, and PIN authorization logic.
*   `Android/src/udp_sender.py`: The network worker. It violently blasts the sensor data over Wi-Fi.
*   `Android/buildozer.spec`: The configuration file that tells the build system how to compile Python into a valid Android APK without crashing.

**Desktop App**
*   `Desktop/Desktop_app.py`: The sleek PyQt5 control center. This runs the main 60Hz loop and connects the UI with the tracking engine.
*   `Desktop/calib_wizard.py`: The interactive popup wizard that records your physiological wrist twist for the Drift Fix engine.
*   `Desktop/auth.py`: Generates the 4-digit PINs and authorizes incoming network streams.
*   `Desktop/mouse_move.py`: The Windows `ctypes` witchcraft and Inverse Kinematics engine. Translates raw angles into stabilized cursor movements.
*   `Desktop/udp_receiver_windows.py`: The background listener. It intercepts the UDP packets sent by your phone.

---

## ⚙️ Manual Labour (Running from Source)

Don't trust random `.exe` files from the internet? Fair enough. Here’s how you run the Desktop app manually like a true hacker:

1. Clone this repo and open a terminal.
2. Set up your Python environment using the provided Conda file so your main Python installation doesn't get contaminated:
   ```bash
   conda env create -f env.yml
   conda activate airmouse
   ```
   *(Don't use Conda? Fine. Just run `pip install PyQt5` instead).*
3. Run the script:
   ```bash
   cd Desktop
   python Desktop_app.py
   ```
*(Note: To run the Android app, you really just need the `.apk`. Trying to run Python on Android manually without an APK is a level of pain you do not want to experience).*

---

## 📦 How to Compile (For the Brave)

Want to turn the Python spaghetti into actual executables for your friends?

**Desktop App (Windows .exe)**
1. `cd Desktop`
2. `pip install pyinstaller pillow` (Pillow is required because Windows throws a tantrum if you give it a `.jpg` icon instead of an `.ico`).
3. Build it:
   ```bash
   pyinstaller --noconsole --onefile --icon=logo.jpg --add-data "logo.jpg;." Desktop_app.py
   ```
4. Find your shiny new standalone `.exe` in the `Desktop/dist/` folder.

**Android App (.apk)**
1. Spin up your WSL or Linux machine and navigate to the `Android/` folder.
2. Run `buildozer android debug`.
3. Wait anywhere from 5 minutes to 3 business days while it downloads the entire Android NDK.
4. Grab your `.apk` from `Android/bin/` and install it.

---

## ⚠️ Disclaimer

If you accidentally launch a nuclear missile, delete your `System32` folder, or give yourself carpal tunnel syndrome because you were violently shaking your phone trying to drag a window... that's on you. AirMouse comes with absolutely zero warranties.

*Built with anger, Python, and a stubborn refusal to spend $100 on a presentation remote.*
