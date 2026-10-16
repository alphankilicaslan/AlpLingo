import time
from pynput import keyboard, mouse
from PyQt6.QtCore import QObject, pyqtSignal


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()
    select_area_triggered = pyqtSignal()
    hotkey_recorded = pyqtSignal(dict)  # {"hotkey_type": "keyboard"|"mouse", "hotkey_value": str, "hotkey_display": str}
    invalid_hotkey = pyqtSignal(str)    # Sol tık seçildiğinde uyarı sinyali

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_recording = False
        self.is_temporarily_disabled = False
        self.pressed_keys = set()
        self.last_trigger_time = 0.0
        self.cooldown_sec = 0.40

        self.keyboard_listener = None
        self.mouse_listener = None

        self.start_listeners()

    def start_listeners(self):
        """Klavye ve fare dinleyicilerini arka planda başlatır"""
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.mouse_listener = mouse.Listener(
            on_click=self._on_mouse_click
        )
        self.keyboard_listener.daemon = True
        self.mouse_listener.daemon = True
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def set_recording(self, recording=True):
        self.is_recording = recording
        self.last_trigger_time = time.monotonic()

    def set_temporarily_disabled(self, disabled: bool):
        self.is_temporarily_disabled = disabled

    def update_config(self, config):
        self.config = config

    def _get_key_identifier(self, key):
        """Tuş adını normalize eder"""
        if hasattr(key, "name") and key.name:
            return key.name.lower(), key.name.upper()
        if hasattr(key, "char") and key.char:
            return key.char.lower(), key.char.upper()
        return str(key).lower(), str(key)

    def _can_trigger(self) -> bool:
        now = time.monotonic()
        if now - self.last_trigger_time < self.cooldown_sec:
            return False
        self.last_trigger_time = now
        return True

    def _on_key_press(self, key):
        raw_val, display_name = self._get_key_identifier(key)

        # Basılı tutma (auto-repeat) tekrarlarını engelle
        if raw_val in self.pressed_keys:
            return
        self.pressed_keys.add(raw_val)

        if self.is_recording:
            self.is_recording = False
            self.last_trigger_time = time.monotonic()
            self.hotkey_recorded.emit({
                "hotkey_type": "keyboard",
                "hotkey_value": raw_val,
                "hotkey_display": f"Tuş: {display_name}"
            })
            return

        if self.is_temporarily_disabled:
            return

        if raw_val == "f8" and self._can_trigger():
            self.select_area_triggered.emit()
            return

        if self.config.get("hotkey_type") == "keyboard":
            target_val = str(self.config.get("hotkey_value", "")).lower()
            if raw_val == target_val and self._can_trigger():
                self.hotkey_triggered.emit()

    def _on_key_release(self, key):
        raw_val, _ = self._get_key_identifier(key)
        self.pressed_keys.discard(raw_val)

    def _on_mouse_click(self, x, y, button, pressed):
        if not pressed:
            return

        button_name = getattr(button, "name", str(button)).lower()

        if self.is_recording:
            # KRİTİK KURAL: SOL CLICK SEÇİLEMEZ
            if button == mouse.Button.left or button_name == "left":
                self.invalid_hotkey.emit(
                    "Sol tık oyundaki temel saldırı ve eylemler için ayrılmıştır. Kısayol olarak seçilemez!"
                )
                return

            self.is_recording = False
            self.last_trigger_time = time.monotonic()
            btn_display = {
                "middle": "Mouse Orta Tık (Scroll)",
                "right": "Mouse Sağ Tık",
                "x1": "Mouse Yan Tuş 1 (Geri)",
                "x2": "Mouse Yan Tuş 2 (İleri)"
            }.get(button_name, f"Mouse: {button_name.upper()}")

            self.hotkey_recorded.emit({
                "hotkey_type": "mouse",
                "hotkey_value": button_name,
                "hotkey_display": btn_display
            })
            return

        if self.is_temporarily_disabled:
            return

        if self.config.get("hotkey_type") == "mouse":
            target_val = str(self.config.get("hotkey_value", "")).lower()
            if button_name == target_val and self._can_trigger():
                self.hotkey_triggered.emit()

    def stop(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
