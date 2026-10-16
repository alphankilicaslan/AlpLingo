import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from config import load_config, save_config, reset_to_defaults
from translator_engine import TranslationEngine
from overlay_window import OverlayWindow
from area_selector import AreaSelector
from hotkey_manager import HotkeyManager
from settings_ui import SettingsWindow


def set_low_cpu_priority():
    """
    Oyunun FPS'ini (özellikle %1 Low FPS ve frame-time stabilitesini)
    asla etkilememesi için Windows işlem önceliğini BELOW_NORMAL yapar.
    Oyun CPU'ya ihtiyaç duyduğunda Windows tüm çekirdekleri öncelikle oyuna bırakır.
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.SetPriorityClass.restype = ctypes.c_bool
        # 0x00004000: BELOW_NORMAL_PRIORITY_CLASS
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00004000)
    except Exception as e:
        print(f"İşlem önceliği ayarlama notu: {e}")


class TranslationWorker(QThread):
    text_translated = pyqtSignal(str)
    engine_loaded = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        # 4 iş parçacığı: i7-13620H'nin 16 çekirdeğinin sadece 4'ünü sınır olarak kullanır.
        # Geriye kalan 12 iş parçacığı tamamen oyuna ve sisteme kalır.
        self.engine = TranslationEngine(intra_threads=4)
        self.is_running = True
        self.is_active = False
        self.empty_count = 0

    def run(self):
        self.engine.load_models()
        self.engine_loaded.emit()

        while self.is_running:
            base_interval = max(200, int(self.config.get("scan_interval_ms", 350)))
            sleep_interval = base_interval

            if self.is_active:
                try:
                    area = self.config.get("capture_area")
                    source_lang = self.config.get("source_lang", "Japonca")
                    raw_text, tr_text = self.engine.scan_and_translate(area, source_lang=source_lang)

                    # Tarama sürerken kullanıcı çeviriyi kapattıysa sonucu ekrana basma!
                    if not self.is_active:
                        continue

                    if tr_text:
                        self.empty_count = 0
                        self.text_translated.emit(tr_text)
                        # Altyazı ekrandayken sakin bekle (GPU ve oyun kare zamanlamasını %100 korur)
                        sleep_interval = 600
                    else:
                        self.empty_count += 1
                        # 3 ardışık boş tarama (~1.2 saniye) sonra altyazıyı temizle
                        if self.empty_count >= 3:
                            self.text_translated.emit("")
                        # Ekranda diyalog yokken rölanti modu
                        sleep_interval = 400
                except Exception as e:
                    print(f"Tarama döngüsü hatası: {e}")

            time.sleep(sleep_interval / 1000.0)

    def set_active(self, active: bool):
        self.is_active = active
        self.empty_count = 0
        self.engine.reset_state()

    def stop(self):
        self.is_active = False
        self.is_running = False
        self.quit()
        self.wait(1500)


class MainApp(QObject):
    def __init__(self):
        super().__init__()
        self.config = load_config()

        # Pencereler & Araçlar
        self.settings_window = SettingsWindow(self.config)
        self.overlay_window = OverlayWindow(self.config)
        self.area_selector = AreaSelector()
        self.hotkey_manager = HotkeyManager(self.config)

        # Arka Plan Çeviri Thread'i
        self.worker = TranslationWorker(self.config)

        self.connect_signals()

        # Başlat
        self.overlay_window.show()
        self.settings_window.show()
        self.worker.start()

    def connect_signals(self):
        # Ayarlar -> Çeviriyi Aç/Kapat
        self.settings_window.start_toggle_requested.connect(self.toggle_translation)

        # Kısayol Tuşu -> Çeviriyi Aç/Kapat (Klavye veya Mouse)
        self.hotkey_manager.hotkey_triggered.connect(self.toggle_translation)

        # Kısayol Kaydetme
        self.settings_window.record_hotkey_requested.connect(
            lambda: self.hotkey_manager.set_recording(True)
        )
        self.hotkey_manager.hotkey_recorded.connect(self.on_hotkey_recorded)
        self.hotkey_manager.invalid_hotkey.connect(
            self.settings_window.show_invalid_hotkey_warning
        )

        # Alan Seçimi (Buton veya F8 Tuşu)
        self.settings_window.select_area_requested.connect(self.on_start_area_selection)
        self.hotkey_manager.select_area_triggered.connect(self.on_start_area_selection)
        self.area_selector.area_selected.connect(self.on_area_selected)
        self.area_selector.selection_closed.connect(self.on_area_selection_closed)

        # Altyazı Kutusunu Taşıma / Düzenleme
        self.settings_window.toggle_edit_mode_requested.connect(self.on_toggle_edit_mode)
        self.overlay_window.position_changed.connect(self.on_overlay_moved)

        # Ayar Değişiklikleri & Sıfırlama
        self.settings_window.settings_changed.connect(self.on_settings_changed)
        self.settings_window.reset_defaults_requested.connect(self.on_reset_defaults)
        self.settings_window.window_closed.connect(self.on_window_closed)

        # Çeviri Thread Sinyalleri
        self.worker.text_translated.connect(self.on_text_translated)
        self.worker.engine_loaded.connect(self.on_engine_loaded)

    def on_engine_loaded(self):
        print("Çeviri motoru hazır.")

    def on_text_translated(self, text: str):
        # Çeviri kapalıysa veya düzenleme modundaysa gelen metni yoksay
        if not self.worker.is_active or self.overlay_window.is_edit_mode:
            return
        self.overlay_window.set_text(text)

    def toggle_translation(self):
        # Eğer kutu taşıma (edit) modundaysa önce onu kilitle
        if self.overlay_window.is_edit_mode:
            self.settings_window.set_edit_overlay_ui(False)
            self.overlay_window.set_edit_mode(False)
            self.hotkey_manager.set_temporarily_disabled(False)
            save_config(self.config)

        new_state = not self.worker.is_active
        self.worker.set_active(new_state)
        self.settings_window.set_active_state(new_state)
        self.overlay_window.set_text("")
        if new_state:
            self.overlay_window.show()
        self.overlay_window.update()

    def on_start_area_selection(self):
        # Alan seçilirken kısayol tuşunun yanlışlıkla tetiklenmesini engelle
        self.hotkey_manager.set_temporarily_disabled(True)
        self.overlay_window.set_text("")
        self.area_selector.start_selection()

    def on_area_selected(self, area_dict):
        self.config["capture_area"] = area_dict
        self.worker.engine.reset_state()
        save_config(self.config)
        self.settings_window.update_ui_from_config()

    def on_area_selection_closed(self):
        self.hotkey_manager.set_temporarily_disabled(False)

    def on_toggle_edit_mode(self, editing: bool):
        self.hotkey_manager.set_temporarily_disabled(editing)
        self.overlay_window.set_edit_mode(editing)
        if not editing:
            self.worker.engine.reset_state()
            save_config(self.config)

    def on_overlay_moved(self, pos_dict):
        self.config["overlay_position"] = pos_dict
        save_config(self.config)
        self.settings_window.update_ui_from_config()

    def on_hotkey_recorded(self, res_dict):
        self.settings_window.finish_hotkey_recording(res_dict)
        self.hotkey_manager.update_config(self.config)
        save_config(self.config)

    def on_settings_changed(self):
        self.worker.engine.reset_state()
        save_config(self.config)
        self.overlay_window.apply_position()
        self.overlay_window.update()

    def on_reset_defaults(self):
        self.config = reset_to_defaults()
        self.settings_window.config = self.config
        self.overlay_window.config = self.config
        self.hotkey_manager.config = self.config
        self.worker.config = self.config
        self.worker.engine.reset_state()

        if self.overlay_window.is_edit_mode:
            self.settings_window.set_edit_overlay_ui(False)
            self.overlay_window.set_edit_mode(False)
            self.hotkey_manager.set_temporarily_disabled(False)

        self.settings_window.update_ui_from_config()
        self.overlay_window.apply_position()
        self.overlay_window.set_text("")
        self.overlay_window.update()

    def on_window_closed(self):
        self.cleanup()
        QApplication.instance().quit()

    def cleanup(self):
        self.overlay_window.hide()
        self.overlay_window.close()
        self.area_selector.close()
        self.worker.stop()
        self.hotkey_manager.stop()


def main():
    set_low_cpu_priority()
    app = QApplication(sys.argv)
    main_app = MainApp()

    app.aboutToQuit.connect(main_app.cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
