"""
AirMouse - Android App
Because physical mice are so 1990s.
"""

import math
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp, sp
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.animation import Animation

from udp_sender import UDPSender, DEFAULT_PORT
from ui_components import GaugeBar, AngleCard, StatusDot, RoundedButton
from settings_screen import SettingsScreen

# The bridge between Python and Android. Let's hope it doesn't collapse.
try:
    from jnius import autoclass, PythonJavaClass, java_method
    from android.permissions import request_permissions, Permission

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context        = autoclass('android.content.Context')
    Sensor         = autoclass('android.hardware.Sensor')
    SensorManager  = autoclass('android.hardware.SensorManager')

    ANDROID = True
except Exception:
    ANDROID = False


# Listening to your phone sensors. Yes, it knows when you hold it upside down.

class SensorListener:

    def __init__(self):
        self.yaw   = 0.0
        self.pitch = 0.0
        self.roll  = 0.0
        self._active = False
        self._sensor = None
        self._listener = None

        if not ANDROID:
            return

        activity     = PythonActivity.mActivity
        self._sm     = activity.getSystemService(Context.SENSOR_SERVICE)
        self._sensor = self._sm.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)

        if self._sensor is None:
            print('[SensorListener] TYPE_GAME_ROTATION_VECTOR not available')
            return

        # Create real Java float[] arrays via jnius
        # These are passed by reference into getRotationMatrixFromVector /
        # getOrientation so they get filled in-place every frame.
        jarray        = autoclass('java.lang.reflect.Array')
        Float         = autoclass('java.lang.Float')
        jfloat        = autoclass('java.lang.Float').TYPE
        self._rot9    = jarray.newInstance(jfloat, 9)   # 3×3 rotation matrix
        self._orient3 = jarray.newInstance(jfloat, 3)   # azimuth, pitch, roll

        self._listener = self._make_listener()

    def _make_listener(self):
        ref  = self
        sm   = self._sm
        rot9 = self._rot9
        ori3 = self._orient3

        class Listener(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/SensorEventListener']
            __javacontext__    = 'app'

            @java_method('(Landroid/hardware/SensorEvent;)V')
            def onSensorChanged(self, event):
                # Step 1: rotation-vector quaternion → 3×3 rotation matrix
                sm.getRotationMatrixFromVector(rot9, event.values)

                # Step 2: rotation matrix → world-frame Euler angles
                sm.getOrientation(rot9, ori3)

                # ori3[0] = azimuth  (yaw,   radians, -π..+π)
                # ori3[1] = pitch    (radians, -π/2..+π/2, negative = nose up)
                # ori3[2] = roll     (radians, -π..+π,   positive = right lean)
                ref.yaw   =  math.degrees(ori3[0])
                ref.pitch = -math.degrees(ori3[1])  # negate: positive = nose up
                ref.roll  =  math.degrees(ori3[2])

            @java_method('(Landroid/hardware/Sensor;I)V')
            def onAccuracyChanged(self, sensor, accuracy):
                pass

        return Listener()

    def start(self):
        if not ANDROID or self._active or self._sensor is None:
            return
        self._sm.registerListener(
            self._listener, self._sensor, SensorManager.SENSOR_DELAY_GAME
        )
        self._active = True

    def stop(self):
        if not ANDROID or not self._active or self._sensor is None:
            return
        self._sm.unregisterListener(self._listener)
        self._active = False


# The shiny buttons. Please don't press them all at once.

class MainScreen(Screen):
    def __init__(self, sensor, sender, **kwargs):
        super().__init__(name='main', **kwargs)
        self._sensor     = sensor
        self._sender     = sender
        self._offset     = {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0}
        self._sim_t      = 0.0
        self._tx_enabled = False

        root = BoxLayout(
            orientation='vertical',
            padding=[dp(16), dp(48), dp(16), dp(20)],
            spacing=dp(10),
        )
        self.add_widget(root)

        # ── Header ───────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))

        logo = Image(source='logo.jpg', size_hint_x=None, width=dp(32))

        title = Label(
            text='A I R M O U S E',
            font_size=sp(18), bold=True,
            color=(0.95, 0.95, 0.98, 1),
            halign='left', valign='middle',
        )
        title.bind(size=title.setter('text_size'))

        hdr.add_widget(logo)

        self._status_lbl = Label(
            text='offline',
            font_size=sp(11),
            color=(0.45, 0.45, 0.5, 1),
            halign='right', valign='middle',
        )
        self._status_lbl.bind(size=self._status_lbl.setter('text_size'))

        self._dot = StatusDot()

        hdr.add_widget(title)
        hdr.add_widget(self._status_lbl)
        hdr.add_widget(self._dot)
        root.add_widget(hdr)

        # ── Angle cards ───────────────────────────────────────────────────
        self._yaw_card   = AngleCard('YAW',   'Left / Right', (0.22, 0.58, 1.00))
        self._pitch_card = AngleCard('PITCH', 'Up / Down',    (0.15, 0.85, 0.55))
        self._roll_card  = AngleCard('ROLL',  'Tilt',         (1.00, 0.55, 0.20))

        for card in (self._yaw_card, self._pitch_card, self._roll_card):
            root.add_widget(card)

        # ── Action buttons ────────────────────────────────────────────────
        btn_box = GridLayout(
            cols=2, size_hint_y=None, height=dp(52), spacing=dp(10)
        )
        root.add_widget(btn_box)

        # Play button
        self._tx_btn = RoundedButton(
            text='[font=fa-solid-900.ttf]\uf04b[/font]  START STREAM',
            bg_color=(0.15, 0.75, 0.45),
            size_hint_y=None, height=dp(56)
        )
        self._tx_btn.bind(on_press=self._toggle_stream)
        btn_box.add_widget(self._tx_btn)

        # Set Zero (Calibrate) button
        self._cal_btn = RoundedButton(
            text='[font=fa-solid-900.ttf]\uf140[/font]  SET ZERO',
            bg_color=(0.22, 0.58, 1.0),
            size_hint_y=None, height=dp(56)
        )
        self._cal_btn.bind(on_press=self._calibrate)
        btn_box.add_widget(self._cal_btn)

        # Center Cursor button
        self._home_btn = RoundedButton(
            text='[font=fa-solid-900.ttf]\uf05b[/font]  CENTER CURSOR',
            bg_color=(0.6, 0.2, 0.8),
            size_hint_y=None, height=dp(56)
        )
        self._home_btn.bind(on_press=self._center_cursor)
        root.add_widget(self._home_btn)

        # ── Settings link ─────────────────────────────────────────────────
        cfg = Button(
            text='[font=fa-solid-900.ttf]\uf013[/font]  Settings',
            font_size=sp(14), markup=True,
            color=(0.4, 0.4, 0.45, 1),
            background_color=(0, 0, 0, 0),
            size_hint_y=None, height=dp(32),
        )
        cfg.bind(on_press=lambda *_: setattr(self.manager, 'current', 'settings'))
        root.add_widget(cfg)

        self._sender.on_status_change = self._on_net_status

    # Button click handlers. Stuff that happens when you poke the screen.

    def _calibrate(self, *_):
        self._offset['yaw']   = self._sensor.yaw
        self._offset['pitch'] = self._sensor.pitch
        self._offset['roll']  = self._sensor.roll
        self._sender.send_command('calibrate')
        self._cal_btn.text = '[font=fa-solid-900.ttf]\uf00c[/font]  ZEROED'
        Clock.schedule_once(
            lambda *_: setattr(self._cal_btn, 'text', '[font=fa-solid-900.ttf]\uf192[/font]  SET ZERO'), 1.5
        )

    def _center_cursor(self, *_):
        self._sender.send_command('home')
        self._home_btn.text = '[font=fa-solid-900.ttf]\uf00c[/font]  CENTERED'
        Clock.schedule_once(
            lambda *_: setattr(self._home_btn, 'text', '[font=fa-solid-900.ttf]\uf015[/font]  CENTER CURSOR'), 1.5
        )

    def _toggle_stream(self, *_):
        self._tx_enabled = not self._tx_enabled
        if self._tx_enabled:
            self._tx_btn.text = '[font=fa-solid-900.ttf]\uf04d[/font]  STOP'
            self._tx_btn._col.rgb = (0.75, 0.25, 0.22)
            self._sender.start()
        else:
            self._tx_btn.text = '[font=fa-solid-900.ttf]\uf04b[/font]  STREAM'
            self._tx_btn._col.rgb = (0.15, 0.75, 0.45)
            self._sender.stop()

    def _on_net_status(self, connected: bool):
        def _upd(*_):
            if connected:
                self._status_lbl.text  = f'To: {self._sender.host}'
                self._status_lbl.color = (0.15, 0.85, 0.55, 1)
                self._dot.set_active(True)
            else:
                self._status_lbl.text  = 'offline'
                self._status_lbl.color = (0.45, 0.45, 0.5, 1)
                self._dot.set_active(False)
        Clock.schedule_once(_upd, 0)

    # Runs 60 times a second. Don't put slow code here or your phone will melt.

    def update(self, dt):
        if ANDROID:
            yaw   = self._sensor.yaw   - self._offset['yaw']
            pitch = self._sensor.pitch - self._offset['pitch']
            roll  = self._sensor.roll  - self._offset['roll']
            active = self._sensor._active
        else:
            self._sim_t += dt
            t     = self._sim_t
            yaw   =  35.0 * math.sin(t * 0.4)
            pitch =  20.0 * math.sin(t * 0.6 + 1.0)
            roll  =  12.0 * math.sin(t * 0.25 + 2.0)
            active = True

        self._yaw_card.set_value(yaw)
        self._pitch_card.set_value(pitch)
        self._roll_card.set_value(roll)
        self._dot.set_active(active)

        if self._tx_enabled:
            self._sender.send(yaw, pitch, roll)

# Let's fire this thing up

class AirMouseApp(App):
    def build(self):
        self.title = 'AirMouse'
        self.icon = 'logo.jpg'
        Window.clearcolor = (0.07, 0.07, 0.10, 1)

        self._sensor = SensorListener()
        self._sender = UDPSender()

        sm = ScreenManager(transition=SlideTransition())
        self._main = MainScreen(self._sensor, self._sender)
        sm.add_widget(self._main)
        sm.add_widget(SettingsScreen(self._sender))
        return sm

    def on_start(self):
        if ANDROID:
            request_permissions([Permission.BODY_SENSORS])
        self._sensor.start()
        Clock.schedule_interval(self._main.update, 1 / 60)

    def on_stop(self):
        self._sensor.stop()
        self._sender.stop()
        Clock.unschedule(self._main.update)

    def on_pause(self):
        self._sensor.stop()
        return True

    def on_resume(self):
        self._sensor.start()


if __name__ == '__main__':
    AirMouseApp().run()