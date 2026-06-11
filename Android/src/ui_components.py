from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp, sp

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
        # clamp between -1.0 and 1.0
        val = max(-1.0, min(1.0, degrees / max_deg))
        if abs(val - self._value) > 0.01:
            self._value = val
            self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        w = self.width
        cx = self.x + w / 2
        cy = self.y + self.height / 2
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

class StatusDot(Widget):
    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(10), dp(10)), **kwargs)
        with self.canvas:
            self._col = Color(0.35, 0.35, 0.4, 1)
            self._dot = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._dot, 'pos', self.pos))

    def set_active(self, active):
        self._col.rgba = (0.15, 0.9, 0.45, 1) if active else (0.35, 0.35, 0.4, 1)

class RoundedButton(Button):
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
