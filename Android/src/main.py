"""
AirMouse - Android App
Phases 1 + 2: Sensor → Yaw/Pitch/Roll display + UDP transmission

Packet sent to Windows:
  {"yaw": 15.2, "pitch": -8.4, "roll": 2.1}
"""

import math
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition

from udp_sender import UDPSender, DEFAULT_PORT

# ── Android bridge ──────────────────────────────────────────────────────────
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


# ── Math ────────────────────────────────────────────────────────────────────

def quaternion_to_euler(x, y, z, w):
    """Unit quaternion → (yaw, pitch, roll) in degrees."""
    norm = math.sqrt(x*x + y*y + z*z + w*w)
    if norm == 0:
        return 0.0, 0.0, 0.0
    x, y, z, w = x/norm, y/norm, z/norm, w/norm

    yaw   = math.degrees(math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)))
    sinp  = max(-1.0, min(1.0, 2*(w*x - z*y)))
    pitch = math.degrees(math.asin(sinp))
    roll  = math.degrees(math.atan2(2*(w*y + z*x), 1 - 2*(x*x + y*y)))

    return yaw, pitch, roll


# ── Sensor listener ─────────────────────────────────────────────────────────

class SensorListener:
    def __init__(self):
        self.yaw = self.pitch = self.roll = 0.0
        self._active = False

        if not ANDROID:
            return

        activity     = PythonActivity.mActivity
        self._sm     = activity.getSystemService(Context.SENSOR_SERVICE)
        self._sensor = self._sm.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)
        self._listener = self._make_listener()

    def _make_listener(self):
        ref = self

        class Listener(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/SensorEventListener']
            __javacontext__    = 'app'

            @java_method('(Landroid/hardware/SensorEvent;)V')
            def onSensorChanged(self, event):
                v  = event.values
                qx = float(v[0]); qy = float(v[1]); qz = float(v[2])
                qw = float(v[3]) if len(v) > 3 else 1.0
                ref.yaw, ref.pitch, ref.roll = quaternion_to_euler(qx, qy, qz, qw)

            @java_method('(Landroid/hardware/Sensor;I)V')
            def onAccuracyChanged(self, sensor, accuracy):
                pass

        return Listener()

    def start(self):
        if not ANDROID or self._active:
            return
        self._sm.registerListener(self._listener, self._sensor,
                                   SensorManager.SENSOR_DELAY_GAME)
        self._active = True

    def stop(self):
        if not ANDROID or not self._active:
            return
        self._sm.unregisterListener(self._listener)
        self._active = False


# ── Reusable UI helpers ──────────────────────────────────────────────────────

def rounded_bg(widget, r, g, b, a=1.0, radius=12):
    """Attach a rounded rectangle background to widget.canvas.before."""
    with widget.canvas.before:
        col = Color(r, g, b, a)
        rect = RoundedRectangle(radius=[dp(radius)])

    def update(*_):
        rect.pos  = widget.pos
        rect.size = widget.size

    widget.bind(pos=update, size=update)
    return col, rect


class AngleCard(BoxLayout):
    def __init__(self, label_text, color, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.padding = [dp(16), dp(12)]
        self.spacing = dp(2)

        with self.canvas.before:
            Color(*color, 0.15)
            self._bg = RoundedRectangle(radius=[dp(16)])

        self.bind(pos=self._upd, size=self._upd)

        self.add_widget(Label(
            text=label_text, font_size=sp(13), color=(0.75, 0.75, 0.75, 1),
            bold=True, halign='center', size_hint_y=None, height=dp(22),
        ))
        self._val = Label(
            text='0.0°', font_size=sp(38), color=(1, 1, 1, 1),
            bold=True, halign='center',
        )
        self.add_widget(self._val)

        self._bar = Label(
            text='', font_size=sp(10), color=(*color[:3], 0.55),
            halign='center', size_hint_y=None, height=dp(16),
        )
        self.add_widget(self._bar)

    def _upd(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def set_value(self, v):
        self._val.text = f'{v:+.1f}°'
        n = max(-1.0, min(1.0, v / 90.0))
        bars = int(abs(n) * 10)
        self._bar.text = ('▓' * bars).rjust(10) if n >= 0 else ('▓' * bars).ljust(10)


# ── Main screen ──────────────────────────────────────────────────────────────

class MainScreen(Screen):
    def __init__(self, sensor, sender, **kwargs):
        super().__init__(name='main', **kwargs)
        self._sensor = sensor
        self._sender = sender
        self._offset = {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0}
        self._sim_t  = 0.0
        self._tx_enabled = False

        root = BoxLayout(orientation='vertical',
                         padding=[dp(20), dp(44), dp(20), dp(24)],
                         spacing=dp(12))
        self.add_widget(root)

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(48))
        self._dot = _StatusDot()
        title = Label(text='✈  AirMouse', font_size=sp(22), bold=True,
                      color=(1, 1, 1, 1), halign='left', valign='middle')
        title.bind(size=title.setter('text_size'))
        self._net_label = Label(
            text='Not streaming', font_size=sp(11),
            color=(0.55, 0.55, 0.55, 1), halign='right', valign='middle',
        )
        self._net_label.bind(size=self._net_label.setter('text_size'))
        hdr.add_widget(title)
        hdr.add_widget(self._net_label)
        hdr.add_widget(self._dot)
        root.add_widget(hdr)

        # Angle cards
        self._yaw_card   = AngleCard('YAW  ←→',    (0.2, 0.6, 1.0))
        self._pitch_card = AngleCard('PITCH  ↑↓',  (0.2, 0.9, 0.5))
        self._roll_card  = AngleCard('ROLL  ↺↻',   (1.0, 0.6, 0.2))
        for c in (self._yaw_card, self._pitch_card, self._roll_card):
            root.add_widget(c)

        # Bottom buttons
        btns = GridLayout(cols=2, size_hint_y=None, height=dp(56), spacing=dp(10))
        self._cal_btn = _RoundedButton(text='SET ZERO', color=(0.2, 0.6, 1.0))
        self._cal_btn.bind(on_press=self._calibrate)
        self._tx_btn  = _RoundedButton(text='▶  STREAM', color=(0.2, 0.8, 0.4))
        self._tx_btn.bind(on_press=self._toggle_stream)
        btns.add_widget(self._cal_btn)
        btns.add_widget(self._tx_btn)
        root.add_widget(btns)

        # Settings link
        cfg_btn = Button(
            text='⚙  Settings', font_size=sp(13),
            color=(0.5, 0.5, 0.5, 1), background_color=(0, 0, 0, 0),
            size_hint_y=None, height=dp(36),
        )
        cfg_btn.bind(on_press=lambda *_: setattr(self.manager, 'current', 'settings'))
        root.add_widget(cfg_btn)

        # Wire sender callback
        self._sender.on_status_change = self._on_net_status

    # ── Callbacks ────────────────────────────────────────────────────────

    def _calibrate(self, *_):
        self._offset['yaw']   = self._sensor.yaw
        self._offset['pitch'] = self._sensor.pitch
        self._offset['roll']  = self._sensor.roll
        self._cal_btn.text = 'ZERO SET ✓'
        Clock.schedule_once(lambda *_: setattr(self._cal_btn, 'text', 'SET ZERO'), 1.5)

    def _toggle_stream(self, *_):
        self._tx_enabled = not self._tx_enabled
        if self._tx_enabled:
            self._tx_btn.text = '⏹  STOP'
            self._sender.start()
        else:
            self._tx_btn.text = '▶  STREAM'
            self._sender.stop()

    def _on_net_status(self, connected: bool):
        def _update(*_):
            if connected:
                self._net_label.text = f'Streaming → {self._sender.host}'
                self._net_label.color = (0.2, 0.9, 0.4, 1)
                self._dot.set_active(True)
            else:
                self._net_label.text = 'Not streaming'
                self._net_label.color = (0.55, 0.55, 0.55, 1)
                self._dot.set_active(False)
        Clock.schedule_once(_update, 0)

    # ── Per-frame update ─────────────────────────────────────────────────

    def update(self, dt):
        if ANDROID:
            yaw   = self._sensor.yaw   - self._offset['yaw']
            pitch = self._sensor.pitch - self._offset['pitch']
            roll  = self._sensor.roll  - self._offset['roll']
        else:
            self._sim_t += dt
            t     = self._sim_t
            yaw   = 30.0 * math.sin(t * 0.5)
            pitch = 20.0 * math.sin(t * 0.7 + 1.0)
            roll  = 10.0 * math.sin(t * 0.3 + 2.0)

        self._yaw_card.set_value(yaw)
        self._pitch_card.set_value(pitch)
        self._roll_card.set_value(roll)

        if self._tx_enabled:
            self._sender.send(yaw, pitch, roll)

        self._dot.set_active(self._sensor._active or not ANDROID)


# ── Settings screen ──────────────────────────────────────────────────────────

class SettingsScreen(Screen):
    def __init__(self, sender, **kwargs):
        super().__init__(name='settings', **kwargs)
        self._sender = sender

        root = BoxLayout(orientation='vertical',
                         padding=[dp(24), dp(50), dp(24), dp(30)],
                         spacing=dp(16))
        self.add_widget(root)

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(48))
        back = Button(
            text='←', font_size=sp(22), color=(1, 1, 1, 1),
            background_color=(0, 0, 0, 0),
            size_hint_x=None, width=dp(48),
        )
        back.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        title = Label(text='Settings', font_size=sp(20), bold=True,
                      color=(1, 1, 1, 1), halign='left')
        title.bind(size=title.setter('text_size'))
        hdr.add_widget(back)
        hdr.add_widget(title)
        root.add_widget(hdr)

        # PC IP input
        root.add_widget(Label(
            text='Windows PC IP Address', font_size=sp(13),
            color=(0.6, 0.6, 0.6, 1), halign='left', size_hint_y=None, height=dp(24),
        ))
        self._ip_input = TextInput(
            text=self._sender.host or '',
            hint_text='e.g. 192.168.1.100',
            multiline=False,
            font_size=sp(18),
            size_hint_y=None,
            height=dp(52),
            foreground_color=(1, 1, 1, 1),
            background_color=(0.15, 0.15, 0.22, 1),
            cursor_color=(0.2, 0.6, 1.0, 1),
            padding=[dp(12), dp(14)],
        )
        root.add_widget(self._ip_input)

        # Port input
        root.add_widget(Label(
            text='UDP Port', font_size=sp(13),
            color=(0.6, 0.6, 0.6, 1), halign='left', size_hint_y=None, height=dp(24),
        ))
        self._port_input = TextInput(
            text=str(self._sender.port),
            hint_text=str(DEFAULT_PORT),
            multiline=False,
            input_filter='int',
            font_size=sp(18),
            size_hint_y=None,
            height=dp(52),
            foreground_color=(1, 1, 1, 1),
            background_color=(0.15, 0.15, 0.22, 1),
            cursor_color=(0.2, 0.6, 1.0, 1),
            padding=[dp(12), dp(14)],
        )
        root.add_widget(self._port_input)

        # Info box
        info = Label(
            text=(
                'Make sure your phone and PC are on the same Wi-Fi network.\n'
                'Find your PC IP: run  ipconfig  in Command Prompt.\n'
                f'Default port: {DEFAULT_PORT}'
            ),
            font_size=sp(12),
            color=(0.5, 0.5, 0.5, 1),
            halign='left',
            valign='top',
            size_hint_y=None,
            height=dp(72),
        )
        info.bind(size=info.setter('text_size'))
        root.add_widget(info)

        # Save button
        save_btn = _RoundedButton(text='SAVE', color=(0.2, 0.6, 1.0))
        save_btn.bind(on_press=self._save)
        root.add_widget(save_btn)

        root.add_widget(Widget())  # spacer

    def _save(self, *_):
        ip   = self._ip_input.text.strip()
        port = int(self._port_input.text.strip() or DEFAULT_PORT)
        self._sender.set_target(ip, port)
        self.manager.current = 'main'


# ── Shared micro-widgets ─────────────────────────────────────────────────────

class _StatusDot(Widget):
    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(12), dp(12)), **kwargs)
        with self.canvas:
            self._col = Color(0.4, 0.4, 0.4, 1)
            self._dot = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
        self.bind(pos=lambda *_: setattr(self._dot, 'pos', self.pos))

    def set_active(self, active):
        self._col.rgba = (0.2, 0.9, 0.4, 1) if active else (0.4, 0.4, 0.4, 1)


class _RoundedButton(Button):
    def __init__(self, text='', color=(0.2, 0.6, 1.0), **kwargs):
        super().__init__(text=text, font_size=sp(15), bold=True,
                         background_color=(0, 0, 0, 0), **kwargs)
        with self.canvas.before:
            self._bg_col  = Color(*color, 0.9)
            self._bg_rect = RoundedRectangle(radius=[dp(12)])
        self.bind(
            pos =lambda *_: setattr(self._bg_rect, 'pos',  self.pos),
            size=lambda *_: setattr(self._bg_rect, 'size', self.size),
        )

    @property
    def text(self):
        return Button.text.__get__(self, type(self))

    @text.setter
    def text(self, v):
        Button.text.__set__(self, v)


# ── App ──────────────────────────────────────────────────────────────────────

class AirMouseApp(App):
    def build(self):
        self.title = 'AirMouse'
        Window.clearcolor = (0.06, 0.06, 0.10, 1)

        self._sensor = SensorListener()
        self._sender = UDPSender()

        sm = ScreenManager(transition=SlideTransition())
        self._main_screen = MainScreen(self._sensor, self._sender)
        sm.add_widget(self._main_screen)
        sm.add_widget(SettingsScreen(self._sender))
        return sm

    def on_start(self):
        if ANDROID:
            request_permissions([Permission.BODY_SENSORS])
        self._sensor.start()
        Clock.schedule_interval(self._main_screen.update, 1 / 60)

    def on_stop(self):
        self._sensor.stop()
        self._sender.stop()
        Clock.unschedule(self._main_screen.update)

    def on_pause(self):
        self._sensor.stop()
        return True

    def on_resume(self):
        self._sensor.start()


if __name__ == '__main__':
    AirMouseApp().run()
