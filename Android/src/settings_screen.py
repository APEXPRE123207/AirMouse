import threading
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp

from udp_sender import UDPSender, DEFAULT_PORT
from ui_components import RoundedButton

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

        self._discover_btn = RoundedButton(
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

        # ── PIN field ─────────────────────────────────────────────────────
        root.add_widget(field_label('PAIRING PIN'))
        self._pin_input = text_field('4-digit PIN from desktop', '', 'int')
        root.add_widget(self._pin_input)

        # Info
        self._info_label = Label(
            text='1. Tap DISCOVER to find your PC\n2. Enter the PIN shown on desktop\n3. Tap PAIR to connect',
            font_size=sp(12),
            color=(0.38, 0.38, 0.43, 1),
            halign='left', valign='top',
            size_hint_y=None, height=dp(52),
        )
        self._info_label.bind(size=self._info_label.setter('text_size'))
        root.add_widget(self._info_label)

        pair_btn = RoundedButton(
            text='[font=fa-solid-900.ttf]\uf0c1[/font]  PAIR', bg_color=(0.15, 0.75, 0.45)
        )
        pair_btn.bind(on_press=self._pair)
        root.add_widget(pair_btn)

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
                    self._info_label.text = 'PC found at ' + ip + '\nNow enter the PIN and tap PAIR.'
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

    def _pair(self, *_):
        """Validate PIN with desktop in a background thread, then save."""
        ip   = self._ip_input.text.strip()
        port = int(self._port_input.text.strip() or DEFAULT_PORT)
        pin  = self._pin_input.text.strip()

        if not ip:
            self._info_label.text = 'Enter an IP or tap DISCOVER first.'
            self._info_label.color = (0.85, 0.35, 0.3, 1)
            return
        if not pin or len(pin) != 4:
            self._info_label.text = 'Enter the 4-digit PIN from the desktop app.'
            self._info_label.color = (0.85, 0.35, 0.3, 1)
            return

        self._info_label.text = 'Pairing...'
        self._info_label.color = (0.6, 0.6, 0.65, 1)

        def _bg_pair():
            ok = UDPSender.pair_with_server(ip, port, pin)

            def _update(*_a):
                if ok:
                    self._sender.set_target(ip, port)
                    self._info_label.text = 'Paired successfully!'
                    self._info_label.color = (0.15, 0.85, 0.55, 1)
                    Clock.schedule_once(
                        lambda *_c: setattr(self.manager, 'current', 'main'), 1.0
                    )
                else:
                    self._info_label.text = 'Wrong PIN or connection failed.\nCheck the PIN and try again.'
                    self._info_label.color = (0.85, 0.35, 0.3, 1)

            Clock.schedule_once(_update, 0)

        threading.Thread(target=_bg_pair, daemon=True).start()
