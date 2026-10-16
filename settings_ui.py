from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QColorDialog,
    QGroupBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from config import SUPPORTED_LANGUAGES


class SettingsWindow(QMainWindow):
    # Sinyaller
    start_toggle_requested = pyqtSignal()
    settings_changed = pyqtSignal()
    select_area_requested = pyqtSignal()
    toggle_edit_mode_requested = pyqtSignal(bool)
    record_hotkey_requested = pyqtSignal()
    reset_defaults_requested = pyqtSignal()
    window_closed = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_active = False
        self.is_editing_overlay = False
        self.is_recording_hotkey = False
        self.lang_keys = list(SUPPORTED_LANGUAGES.keys())

        self.setWindowTitle("Translito - Ekran & Oyun Çevirici")
        self.setFixedSize(620, 740)

        self.init_ui()
        self.apply_dark_theme()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 1. Başlık & Durum Çubuğu
        header_layout = QHBoxLayout()
        title_label = QLabel("✨ Translito - Yapay Zeka Ekran Çevirici")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.status_badge = QLabel("DURDURULDU")
        self.status_badge.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;"
        )
        header_layout.addWidget(self.status_badge)
        main_layout.addLayout(header_layout)

        # 2. Ana Başlatma / Durdurma Butonu
        self.toggle_btn = QPushButton("🚀 Çeviriyi Başlat")
        self.toggle_btn.setFixedHeight(44)
        self.toggle_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.toggle_btn.setStyleSheet("background-color: #27ae60; color: white; border-radius: 8px;")
        self.toggle_btn.clicked.connect(self.on_toggle_clicked)
        main_layout.addWidget(self.toggle_btn)

        # 3. Dil Seçimi Bölümü (15 Kaynak Dil -> Türkçe)
        lang_group = QGroupBox("Dil Ayarı (Çevrilecek Oyun Dili)")
        lang_layout = QHBoxLayout(lang_group)
        lang_layout.addWidget(QLabel("Oyundaki Dil:"))
        self.combo_source_lang = QComboBox()
        for k in self.lang_keys:
            self.combo_source_lang.addItem(SUPPORTED_LANGUAGES[k]["display"], userData=k)

        curr_lang = self.config.get("source_lang", "Japonca")
        if curr_lang in self.lang_keys:
            self.combo_source_lang.setCurrentIndex(self.lang_keys.index(curr_lang))
        self.combo_source_lang.currentIndexChanged.connect(self.on_source_lang_changed)
        lang_layout.addWidget(self.combo_source_lang)

        arrow_lbl = QLabel("➔")
        arrow_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #5dade2;")
        lang_layout.addWidget(arrow_lbl)

        target_lbl = QLabel("🇹🇷 Türkçe (Satır Yapısı Korumalı)")
        target_lbl.setStyleSheet("font-weight: bold; color: #2ecc71;")
        lang_layout.addWidget(target_lbl)
        lang_layout.addStretch()
        main_layout.addWidget(lang_group)

        # 4. Kısayol Tuşu Belirleme Bölümü (Klavye veya Mouse, Sol Tık Engelli)
        hotkey_group = QGroupBox("Kısayol Tuşu (Çeviriyi Aç / Kapat)")
        hotkey_layout = QHBoxLayout(hotkey_group)

        self.hotkey_label = QLabel(f"Atanan Kısayol: <b>{self.config.get('hotkey_display', 'Tuş: F9')}</b>")
        hotkey_layout.addWidget(self.hotkey_label)
        hotkey_layout.addStretch()

        self.btn_record_hotkey = QPushButton("🎯 Tuş / Mouse Ata...")
        self.btn_record_hotkey.setToolTip("Klavyeden bir tuşa veya farenin tekerlek/yan tuşlarına basın (Sol tık hariç).")
        self.btn_record_hotkey.clicked.connect(self.on_record_hotkey_clicked)
        hotkey_layout.addWidget(self.btn_record_hotkey)
        main_layout.addWidget(hotkey_group)

        # 5. Alan ve Konum Ayarları
        pos_group = QGroupBox("Ekran Alanı ve Altyazı Konumu")
        pos_layout = QVBoxLayout(pos_group)

        btn_row = QHBoxLayout()
        self.btn_select_area = QPushButton("🔍 1. Okunacak Alanı Seç [F8]")
        self.btn_select_area.setToolTip("F8 tuşuna basarak veya bu butona tıklayarak oyunun altyazı alanını sürükleyip seçebilirsiniz.")
        self.btn_select_area.clicked.connect(self.select_area_requested.emit)
        btn_row.addWidget(self.btn_select_area)

        self.btn_move_overlay = QPushButton("📍 2. Altyazı Kutusunu Taşı / Boyutlandır")
        self.btn_move_overlay.setToolTip("Altyazının ekranda nerede görüneceğini ve boyutunu fareyle ayarlayın.")
        self.btn_move_overlay.clicked.connect(self.on_toggle_edit_overlay)
        btn_row.addWidget(self.btn_move_overlay)
        pos_layout.addLayout(btn_row)

        self.area_info_label = QLabel(self._get_area_info_text())
        self.area_info_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        pos_layout.addWidget(self.area_info_label)
        main_layout.addWidget(pos_group)

        # 6. Yazı Tipi, Kalınlık, Büyüklük, Hizalama ve Stil Ayarları
        font_group = QGroupBox("Yazı Tipi & Tipografi Özelleştirme")
        font_layout = QVBoxLayout(font_group)

        # Font Ailesi, Kalınlık ve Hizalama
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Stil:"))
        self.combo_font = QComboBox()
        self.combo_font.addItems(["Segoe UI", "Arial", "Roboto", "Calibri", "Trebuchet MS", "Impact", "Consolas"])
        curr_font = self.config.get("font_family", "Segoe UI")
        idx = self.combo_font.findText(curr_font)
        if idx >= 0:
            self.combo_font.setCurrentIndex(idx)
        self.combo_font.currentTextChanged.connect(self.on_font_family_changed)
        row1.addWidget(self.combo_font)

        row1.addWidget(QLabel("Kalınlık:"))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(["Normal", "Medium", "Bold", "ExtraBold", "Black"])
        curr_weight = self.config.get("font_weight", "Bold")
        w_idx = self.combo_weight.findText(curr_weight)
        if w_idx >= 0:
            self.combo_weight.setCurrentIndex(w_idx)
        self.combo_weight.currentTextChanged.connect(self.on_font_weight_changed)
        row1.addWidget(self.combo_weight)

        row1.addWidget(QLabel("Hiza:"))
        self.combo_align = QComboBox()
        self.combo_align.addItems(["Sol (Oyun Yapısı)", "Orta"])
        curr_align = self.config.get("alignment", "Left")
        self.combo_align.setCurrentIndex(0 if curr_align == "Left" else 1)
        self.combo_align.currentIndexChanged.connect(self.on_alignment_changed)
        row1.addWidget(self.combo_align)
        font_layout.addLayout(row1)

        # Büyüklük (Font Size Slider)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Büyüklük (Boyut):"))
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(14, 48)
        self.slider_size.setValue(int(self.config.get("font_size", 20)))
        self.lbl_size_val = QLabel(f"{self.slider_size.value()} px")
        self.slider_size.valueChanged.connect(self.on_font_size_changed)
        row2.addWidget(self.slider_size)
        row2.addWidget(self.lbl_size_val)
        font_layout.addLayout(row2)

        # Renkler (Metin Rengi, Kenarlık Rengi)
        row3 = QHBoxLayout()
        self.btn_text_color = QPushButton("Metin Rengi")
        self.btn_text_color.clicked.connect(self.on_pick_text_color)
        self.preview_text_col = QFrame()
        self.preview_text_col.setFixedSize(24, 24)
        self._update_color_preview(self.preview_text_col, self.config.get("text_color", "#FFFFFF"))
        row3.addWidget(self.btn_text_color)
        row3.addWidget(self.preview_text_col)

        self.btn_outline_color = QPushButton("Kenarlık Rengi")
        self.btn_outline_color.clicked.connect(self.on_pick_outline_color)
        self.preview_outline_col = QFrame()
        self.preview_outline_col.setFixedSize(24, 24)
        self._update_color_preview(self.preview_outline_col, self.config.get("outline_color", "#000000"))
        row3.addWidget(self.btn_outline_color)
        row3.addWidget(self.preview_outline_col)
        font_layout.addLayout(row3)

        # Arka Plan Saydamlık Slider'ı
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Arka Plan Saydamlığı:"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 255)
        self.slider_opacity.setValue(int(self.config.get("bg_opacity", 120)))
        self.lbl_opacity_val = QLabel(f"%{int(self.slider_opacity.value() / 2.55)}")
        self.slider_opacity.valueChanged.connect(self.on_bg_opacity_changed)
        row4.addWidget(self.slider_opacity)
        row4.addWidget(self.lbl_opacity_val)
        font_layout.addLayout(row4)

        main_layout.addWidget(font_group)

        # 7. Sıfırlama ve Bilgi Çubuğu
        footer_layout = QHBoxLayout()
        self.btn_reset = QPushButton("🔄 Varsayılan Ayarlara Sıfırla")
        self.btn_reset.setStyleSheet("background-color: #c0392b; color: white;")
        self.btn_reset.clicked.connect(self.on_reset_defaults_clicked)
        footer_layout.addWidget(self.btn_reset)

        footer_layout.addStretch()
        info_label = QLabel("RTX 4060: %0 GPU / 0 MB VRAM (CPU Modu)")
        info_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
        footer_layout.addWidget(info_label)
        main_layout.addLayout(footer_layout)

    def _get_area_info_text(self):
        a = self.config.get("capture_area", {})
        o = self.config.get("overlay_position", {})
        return (
            f"Okuma Alanı: [{a.get('x',0)}, {a.get('y',0)} - {a.get('width',0)}x{a.get('height',0)}] | "
            f"Altyazı Kutusu: [{o.get('x',0)}, {o.get('y',0)} - {o.get('width',0)}x{o.get('height',0)}]"
        )

    def _update_color_preview(self, frame, color_hex):
        frame.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #777; border-radius: 4px;")

    def on_source_lang_changed(self, index):
        if 0 <= index < len(self.lang_keys):
            self.config["source_lang"] = self.lang_keys[index]
            self.settings_changed.emit()

    def on_alignment_changed(self, index):
        self.config["alignment"] = "Left" if index == 0 else "Center"
        self.settings_changed.emit()

    def update_ui_from_config(self):
        """Ayarlar değiştiğinde veya sıfırlandığında arayüzü günceller"""
        self.hotkey_label.setText(f"Atanan Kısayol: <b>{self.config.get('hotkey_display', 'Tuş: F9')}</b>")
        self.area_info_label.setText(self._get_area_info_text())

        curr_lang = self.config.get("source_lang", "Japonca")
        self.combo_source_lang.blockSignals(True)
        if curr_lang in self.lang_keys:
            self.combo_source_lang.setCurrentIndex(self.lang_keys.index(curr_lang))
        self.combo_source_lang.blockSignals(False)

        curr_font = self.config.get("font_family", "Segoe UI")
        idx = self.combo_font.findText(curr_font)
        if idx >= 0:
            self.combo_font.blockSignals(True)
            self.combo_font.setCurrentIndex(idx)
            self.combo_font.blockSignals(False)

        curr_weight = self.config.get("font_weight", "Bold")
        w_idx = self.combo_weight.findText(curr_weight)
        if w_idx >= 0:
            self.combo_weight.blockSignals(True)
            self.combo_weight.setCurrentIndex(w_idx)
            self.combo_weight.blockSignals(False)

        curr_align = self.config.get("alignment", "Left")
        self.combo_align.blockSignals(True)
        self.combo_align.setCurrentIndex(0 if curr_align == "Left" else 1)
        self.combo_align.blockSignals(False)

        self.slider_size.blockSignals(True)
        self.slider_size.setValue(int(self.config.get("font_size", 20)))
        self.slider_size.blockSignals(False)
        self.lbl_size_val.setText(f"{self.slider_size.value()} px")

        self.slider_opacity.blockSignals(True)
        self.slider_opacity.setValue(int(self.config.get("bg_opacity", 120)))
        self.slider_opacity.blockSignals(False)
        self.lbl_opacity_val.setText(f"%{int(self.slider_opacity.value() / 2.55)}")

        self._update_color_preview(self.preview_text_col, self.config.get("text_color", "#FFFFFF"))
        self._update_color_preview(self.preview_outline_col, self.config.get("outline_color", "#000000"))

    def set_active_state(self, active: bool):
        self.is_active = active
        if active:
            self.status_badge.setText("AKTİF (ÇEVİRİYOR)")
            self.status_badge.setStyleSheet(
                "background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;"
            )
            self.toggle_btn.setText("⏸️ Çeviriyi Durdur")
            self.toggle_btn.setStyleSheet("background-color: #e67e22; color: white; border-radius: 8px;")
        else:
            self.status_badge.setText("DURDURULDU")
            self.status_badge.setStyleSheet(
                "background-color: #e74c3c; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;"
            )
            self.toggle_btn.setText("🚀 Çeviriyi Başlat")
            self.toggle_btn.setStyleSheet("background-color: #27ae60; color: white; border-radius: 8px;")

    def on_toggle_clicked(self):
        self.start_toggle_requested.emit()

    def on_record_hotkey_clicked(self):
        self.is_recording_hotkey = True
        self.btn_record_hotkey.setText("⏳ Tuşa / Mouse Tuşuna Basın...")
        self.btn_record_hotkey.setEnabled(False)
        self.record_hotkey_requested.emit()

    def finish_hotkey_recording(self, result_dict):
        self.is_recording_hotkey = False
        self.btn_record_hotkey.setText("🎯 Tuş / Mouse Ata...")
        self.btn_record_hotkey.setEnabled(True)
        self.config["hotkey_type"] = result_dict["hotkey_type"]
        self.config["hotkey_value"] = result_dict["hotkey_value"]
        self.config["hotkey_display"] = result_dict["hotkey_display"]
        self.hotkey_label.setText(f"Atanan Kısayol: <b>{result_dict['hotkey_display']}</b>")
        self.settings_changed.emit()

    def show_invalid_hotkey_warning(self, message):
        self.is_recording_hotkey = False
        self.btn_record_hotkey.setText("🎯 Tuş / Mouse Ata...")
        self.btn_record_hotkey.setEnabled(True)
        QMessageBox.warning(self, "Geçersiz Kısayol", message)

    def on_toggle_edit_overlay(self):
        self.set_edit_overlay_ui(not self.is_editing_overlay)
        self.toggle_edit_mode_requested.emit(self.is_editing_overlay)

    def set_edit_overlay_ui(self, editing: bool):
        self.is_editing_overlay = editing
        if editing:
            self.btn_move_overlay.setText("💾 Konumu Kilitle ve Kaydet")
            self.btn_move_overlay.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        else:
            self.btn_move_overlay.setText("📍 2. Altyazı Kutusunu Taşı / Boyutlandır")
            self.btn_move_overlay.setStyleSheet("")
            self.area_info_label.setText(self._get_area_info_text())

    def on_font_family_changed(self, text):
        self.config["font_family"] = text
        self.settings_changed.emit()

    def on_font_weight_changed(self, text):
        self.config["font_weight"] = text
        self.settings_changed.emit()

    def on_font_size_changed(self, val):
        self.lbl_size_val.setText(f"{val} px")
        self.config["font_size"] = val
        self.settings_changed.emit()

    def on_bg_opacity_changed(self, val):
        self.lbl_opacity_val.setText(f"%{int(val / 2.55)}")
        self.config["bg_opacity"] = val
        self.settings_changed.emit()

    def on_pick_text_color(self):
        curr = QColor(self.config.get("text_color", "#FFFFFF"))
        col = QColorDialog.getColor(curr, self, "Metin Rengi Seçin")
        if col.isValid():
            hex_c = col.name()
            self.config["text_color"] = hex_c
            self._update_color_preview(self.preview_text_col, hex_c)
            self.settings_changed.emit()

    def on_pick_outline_color(self):
        curr = QColor(self.config.get("outline_color", "#000000"))
        col = QColorDialog.getColor(curr, self, "Kenarlık / Gölge Rengi Seçin")
        if col.isValid():
            hex_c = col.name()
            self.config["outline_color"] = hex_c
            self._update_color_preview(self.preview_outline_col, hex_c)
            self.settings_changed.emit()

    def on_reset_defaults_clicked(self):
        reply = QMessageBox.question(
            self,
            "Ayarları Sıfırla",
            "Tüm yazı stili, konum ve kısayol ayarlarını varsayılan haline döndürmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_defaults_requested.emit()

    def closeEvent(self, event):
        self.window_closed.emit()
        super().closeEvent(event)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e24;
            }
            QWidget {
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                border: 1px solid #3d3d4a;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #5dade2;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #2b2b36;
                border: 1px solid #4a4a5a;
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #3b3b4a;
                border-color: #5dade2;
            }
            QPushButton:pressed {
                background-color: #1b1b24;
            }
            QComboBox {
                background-color: #2b2b36;
                border: 1px solid #4a4a5a;
                border-radius: 6px;
                padding: 4px 8px;
                color: #ffffff;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #3d3d4a;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ecf0f1;
                border: 1px solid #7f8c8d;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)
