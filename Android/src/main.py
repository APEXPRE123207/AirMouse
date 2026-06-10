"""
AirMouse - Android App  (Phase 1 + 2)
BUG FIX: pitch/roll swap caused by device-frame vs world-frame Euler angles.

ROOT CAUSE:
  Old code: raw quaternion → Euler using aerospace ZYX convention.
  These angles are relative to the DEVICE frame, so they shift meaning
  depending on how you hold the phone (flat vs upright).

FIX:
  Use Android's SensorManager.getRotationMatrixFromVector()
  + SensorManager.getOrientation() which returns WORLD-REFERENCED angles:
    values[0] = azimuth  → yaw   (rotation around world vertical Z)
    values[1] = pitch    → pitch (tilt front/back vs gravity)  ← always correct
    values[2] = roll     → roll  (tilt sideways vs gravity)    ← always correct

  These are gravity-referenced so pitch always means "nose up/down"
  and roll always means "lean left/right" regardless of phone orientation.
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

# ── Android bridge ───────────────────────────────────────────────────────────
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


# ── Sensor listener — FIXED to use world-frame angles ───────────────────────

class SensorListener:
    """
    Reads TYPE_GAME_ROTATION_VECTOR and converts to world-referenced
    yaw/pitch/roll using Android's own getOrientation() API.

    This gives gravity-referenced angles that work correctly regardless
    of how the phone is physically held.

    IMPORTANT — Pyjnius Java array note:
    getRotationMatrixFromVector() and getOrientation() require real Java
    float[] arrays, not Python lists. We use jnius.cast + array module to
    create them once at init and reuse every frame (avoids GC pressure).
    """

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


# ── Visual widgets ───────────────────────────────────────────────────────────

class GaugeBar(Widget):
    """
    Horizontal bar gauge: filled from centre outward.
    color: (r, g, b)
    """
    def __init__(self, color, **kwargs):
        super().__init__(**kwargs)
        self._color = color
        self._value = 0.0   # -1.0 .. +1.0
        self.bind(pos=self._draw, size=self._draw)

    def set_value(self, degrees, max_deg=90.0):
        self._value = max(-1.0, min(1.0, degrees / max_deg))
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        w, h = self.size
        cx = self.x + w / 2
        cy = self.y + h / 2
        r, g, b = self._color

        with self.canvas:
            # Track
            Color(r, g, b, 0.12)
            RoundedRectangle(pos=(self.x, cy - dp(3)),
                             size=(w, dp(6)),
                             radius=[dp(3)])
            # Centre tick
            Color(r, g, b, 0.3)
            Line(points=[cx, cy - dp(6), cx, cy + dp(6)], width=dp(1))

            # Fill bar
            fill_w = abs(self._value) * (w / 2)
            if fill_w > 0:
                Color(r, g, b, 0.85)
                if self._value >= 0:
                    RoundedRectangle(pos=(cx, cy - dp(4)),
                                     size=(fill_w, dp(8)),
                                     radius=[dp(4)])
                else:
                    RoundedRectangle(pos=(cx - fill_w, cy - dp(4)),
                                     size=(fill_w, dp(8)),
                                     radius=[dp(4)])

            # Indicator dot
            dot_x = cx + self._value * (w / 2)
            Color(r, g, b, 1.0)
            Ellipse(pos=(dot_x - dp(6), cy - dp(6)), size=(dp(12), dp(12)))
            Color(0.08, 0.08, 0.12, 1)
            Ellipse(pos=(dot_x - dp(3), cy - dp(3)), size=(dp(6), dp(6)))


class AngleCard(BoxLayout):
    """Card showing one angle with label, big value, and gauge."""

    ICONS = {'YAW': '↔', 'PITCH': '↕', 'ROLL': '↻'}

    def __init__(self, axis, label_text, color, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.padding  = [dp(18), dp(14), dp(18), dp(10)]
        self.spacing  = dp(4)
        self._color   = color
        r, g, b       = color

        # Card background
        with self.canvas.before:
            Color(r, g, b, 0.08)
            self._bg = RoundedRectangle(radius=[dp(20)])
            Color(r, g, b, 0.22)
            self._border = RoundedRectangle(radius=[dp(20)])

        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # Top row: icon + label on left, small axis tag on right
        top = BoxLayout(size_hint_y=None, height=dp(26))
        icon_lbl = Label(
            text=f'{self.ICONS.get(axis, "")}  {label_text}',
            font_size=sp(12), bold=True,
            color=(r, g, b, 0.9),
            halign='left', valign='middle',
        )
        icon_lbl.bind(size=icon_lbl.setter('text_size'))
        axis_tag = Label(
            text=axis,
            font_size=sp(10), bold=True,
            color=(r, g, b, 0.4),
            halign='right', valign='middle',
        )
        axis_tag.bind(size=axis_tag.setter('text_size'))
        top.add_widget(icon_lbl)
        top.add_widget(axis_tag)
        self.add_widget(top)

        # Big value
        self._val_lbl = Label(
            text='  0.0°',
            font_size=sp(42), bold=True,
            color=(1, 1, 1, 1),
            halign='left', valign='middle',
        )
        self._val_lbl.bind(size=self._val_lbl.setter('text_size'))
        self.add_widget(self._val_lbl)

        # Gauge bar
        self._gauge = GaugeBar(color=color, size_hint_y=None, height=dp(24))
        self.add_widget(self._gauge)

    def _upd_bg(self, *_):
        bw = dp(1)
        self._bg.pos    = self.pos
        self._bg.size   = self.size
        self._border.pos  = (self.x + bw, self.y + bw)
        self._border.size = (self.width - bw * 2, self.height - bw * 2)

    def set_value(self, v):
        sign = '+' if v >= 0 else ''
        self._val_lbl.text = f'{sign}{v:.1f}°'
        self._gauge.set_value(v)
        # Colour intensity: brighter when further from zero
        intensity = min(1.0, abs(v) / 45.0)
        r, g, b = self._color
        self._val_lbl.color = (
            0.7 + 0.3 * intensity * r,
            0.7 + 0.3 * intensity * g,
            0.7 + 0.3 * intensity * b,
            1.0,
        )


class _StatusDot(Widget):
    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(10), dp(10)), **kwargs)
        with self.canvas:
            self._col = Color(0.35, 0.35, 0.4, 1)
            self._dot = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._dot, 'pos', self.pos))

    def set_active(self, active):
        self._col.rgba = (0.15, 0.9, 0.45, 1) if active else (0.35, 0.35, 0.4, 1)


class _RoundedButton(Button):
    def __init__(self, text='', bg_color=(0.2, 0.6, 1.0), **kwargs):
        super().__init__(
            text=text, font_size=sp(14), bold=True, markup=True,
            color=(1, 1, 1, 1),
            background_color=(0, 0, 0, 0), **kwargs
        )
        self._bg_color = bg_color
        with self.canvas.before:
            self._col  = Color(*bg_color, 0.88)
            self._rect = RoundedRectangle(radius=[dp(14)])
        self.bind(
            pos =lambda *_: setattr(self._rect, 'pos',  self.pos),
            size=lambda *_: setattr(self._rect, 'size', self.size),
        )

    def on_press(self):
        self._col.a = 0.65

    def on_release(self):
        self._col.a = 0.88


# ── Main screen ──────────────────────────────────────────────────────────────

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

        self._dot = _StatusDot()

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
        btns = GridLayout(
            cols=2, size_hint_y=None, height=dp(52), spacing=dp(10)
        )
        self._cal_btn = _RoundedButton(
            text='[font=fa-solid-900.ttf]\uf192[/font]  SET ZERO', bg_color=(0.22, 0.58, 1.00)
        )
        self._cal_btn.bind(on_press=self._calibrate)

        self._tx_btn = _RoundedButton(
            text='[font=fa-solid-900.ttf]\uf04b[/font]  STREAM', bg_color=(0.15, 0.75, 0.45)
        )
        self._tx_btn.bind(on_press=self._toggle_stream)

        btns.add_widget(self._cal_btn)
        btns.add_widget(self._tx_btn)
        root.add_widget(btns)

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

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _calibrate(self, *_):
        self._offset['yaw']   = self._sensor.yaw
        self._offset['pitch'] = self._sensor.pitch
        self._offset['roll']  = self._sensor.roll
        self._cal_btn.text = '[font=fa-solid-900.ttf]\uf00c[/font]  ZEROED'
        Clock.schedule_once(
            lambda *_: setattr(self._cal_btn, 'text', '[font=fa-solid-900.ttf]\uf192[/font]  SET ZERO'), 1.5
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

    # ── Per-frame update ──────────────────────────────────────────────────

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


# ── Settings screen ──────────────────────────────────────────────────────────

class SettingsScreen(Screen):
    def __init__(self, sender, **kwargs):
        super().__init__(name='settings', **kwargs)
        self._sender = sender

        root = BoxLayout(
            orientation='vertical',
            padding=[dp(20), dp(52), dp(20), dp(28)],
            spacing=dp(14),
        )
        self.add_widget(root)

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        back = Button(
            text='[font=fa-solid-900.ttf]\uf060[/font]', font_size=sp(20), markup=True,
            color=(0.7, 0.7, 0.75, 1),
            background_color=(0, 0, 0, 0),
            size_hint_x=None, width=dp(44),
        )
        back.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        hdr.add_widget(back)
        hdr.add_widget(Label(
            text='S E T T I N G S', font_size=sp(16), bold=True,
            color=(0.95, 0.95, 0.98, 1), halign='left', valign='middle',
        ))
        root.add_widget(hdr)

        # Separator
        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(0.2, 0.2, 0.25, 1)
            RoundedRectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda w, v: setattr(sep.canvas.children[-1], 'pos', v))
        sep.bind(size=lambda w, v: setattr(sep.canvas.children[-1], 'size', v))
        root.add_widget(sep)

        def field_label(text):
            return Label(
                text=text, font_size=sp(11), bold=True,
                color=(0.5, 0.5, 0.55, 1),
                halign='left', valign='middle',
                size_hint_y=None, height=dp(20),
            )

        def text_field(hint, text='', input_filter=None):
            tf = TextInput(
                text=text, hint_text=hint,
                multiline=False,
                font_size=sp(17),
                size_hint_y=None, height=dp(50),
                foreground_color=(0.95, 0.95, 0.98, 1),
                hint_text_color=(0.35, 0.35, 0.4, 1),
                background_color=(0.10, 0.10, 0.15, 1),
                cursor_color=(0.22, 0.58, 1.0, 1),
                padding=[dp(14), dp(14)],
            )
            if input_filter:
                tf.input_filter = input_filter
            return tf

        # ── IP field + Discover button ────────────────────────────────────
        root.add_widget(field_label('PC IP ADDRESS'))

        ip_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(50),
            spacing=dp(8),
        )
        self._ip_input = text_field('e.g. 192.168.1.100', self._sender.host or '')
        self._ip_input.size_hint_x = 0.65

        self._discover_btn = _RoundedButton(
            text='DISCOVER', bg_color=(0.5, 0.35, 0.8)
        )
        self._discover_btn.size_hint_x = 0.35
        self._discover_btn.bind(on_press=self._discover)

        ip_row.add_widget(self._ip_input)
        ip_row.add_widget(self._discover_btn)
        root.add_widget(ip_row)

        root.add_widget(field_label('UDP PORT'))
        self._port_input = text_field(str(DEFAULT_PORT), str(self._sender.port), 'int')
        root.add_widget(self._port_input)

        # Info
        self._info_label = Label(
            text='Tap DISCOVER to auto-find your PC,\nor enter the IP manually.',
            font_size=sp(12),
            color=(0.38, 0.38, 0.43, 1),
            halign='left', valign='top',
            size_hint_y=None, height=dp(52),
        )
        self._info_label.bind(size=self._info_label.setter('text_size'))
        root.add_widget(self._info_label)

        save_btn = _RoundedButton(text='SAVE', bg_color=(0.22, 0.58, 1.00))
        save_btn.bind(on_press=self._save)
        root.add_widget(save_btn)

        root.add_widget(Widget())  # spacer

    def _discover(self, *_):
        """Run discovery in a background thread to avoid blocking the UI."""
        self._discover_btn.text = 'Searching...'
        self._discover_btn.disabled = True

        def _bg_discover():
            ip = UDPSender.discover_server()

            def _update(*_a):
                if ip:
                    self._ip_input.text = ip
                    self._discover_btn.text = 'Found!'
                    self._info_label.text = 'PC found at ' + ip
                    self._info_label.color = (0.15, 0.85, 0.55, 1)
                else:
                    self._discover_btn.text = 'Not found'
                    self._info_label.text = (
                        'Desktop app not detected.\n'
                        'Make sure it is running on the same Wi-Fi.'
                    )
                    self._info_label.color = (0.85, 0.35, 0.3, 1)
                self._discover_btn.disabled = False
                Clock.schedule_once(
                    lambda *_b: setattr(self._discover_btn, 'text', 'DISCOVER'),
                    2.5,
                )

            Clock.schedule_once(_update, 0)

        threading.Thread(target=_bg_discover, daemon=True).start()

    def _save(self, *_):
        ip   = self._ip_input.text.strip()
        port = int(self._port_input.text.strip() or DEFAULT_PORT)
        self._sender.set_target(ip, port)
        self.manager.current = 'main'


# ── App ──────────────────────────────────────────────────────────────────────

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