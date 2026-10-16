import sys
import ctypes
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QCursor, QFontMetrics

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

EDIT_PREVIEW_TEXT = (
    "Jinhsi - Jinzhou Yargıcı\n"
    "[Taşıma Modu] Kutuyu sürükleyerek taşıyın, sağ alt köşeden boyutlandırın."
)


class OverlayWindow(QWidget):
    position_changed = pyqtSignal(dict)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_text = ""
        self.is_edit_mode = False
        self.drag_position = QPoint()
        self.is_resizing = False
        self.resize_margin = 18

        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.apply_position()
        self.set_edit_mode(False)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_win32_Protection()

    def _apply_win32_Protection(self):
        """
        1) Oyun modunda tıklamaları arkaya geçirir (Click-Through).
        2) WDA_EXCLUDEFROMCAPTURE ile ekran yakalamanın (mss/OCR) bu pencereyi
           görmesini engeller. Böylece kendi çevirdiği yazıyı ASLA tekrar okumaz!
        """
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if not self.is_edit_mode:
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, styles | WS_EX_TRANSPARENT | WS_EX_LAYERED
                )
            else:
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, (styles & ~WS_EX_TRANSPARENT) | WS_EX_LAYERED
                )
            # Ekran yakalamadan (mss) gizle - kullanıcı ekranda görür ama OCR görmez!
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            print(f"Windows pencere stili ayar hatası: {e}")

    def apply_position(self):
        pos = self.config.get("overlay_position", {"x": 400, "y": 600, "width": 1120, "height": 130})
        self.setGeometry(
            int(pos.get("x", 400)),
            int(pos.get("y", 600)),
            max(200, int(pos.get("width", 1120))),
            max(60, int(pos.get("height", 130)))
        )
        self.update()

    def set_edit_mode(self, edit_mode: bool):
        """
        Düzenleme Modu: Kullanıcı pencereyi sürükleyip boyutlandırabilir.
        Oyun Modu: Pencere tıklandığında arkaya geçer (Click-Through) ve oyunu engellemez.
        """
        self.is_edit_mode = edit_mode
        if edit_mode:
            self.current_text = EDIT_PREVIEW_TEXT
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            self.show()
        else:
            if self.current_text == EDIT_PREVIEW_TEXT:
                self.current_text = ""
            self.is_resizing = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        self._apply_win32_Protection()
        self.update()

    def set_text(self, text: str):
        # Düzenleme modundayken örnek metni koru
        if self.is_edit_mode:
            return
        cleaned = text.strip() if text else ""
        if self.current_text != cleaned:
            self.current_text = cleaned
            self.update()

    def _in_resize_zone(self, pos: QPoint) -> bool:
        return (
            pos.x() >= self.width() - self.resize_margin and
            pos.y() >= self.height() - self.resize_margin
        )

    def mousePressEvent(self, event):
        if self.is_edit_mode and event.button() == Qt.MouseButton.LeftButton:
            if self._in_resize_zone(event.pos()):
                self.is_resizing = True
            else:
                self.is_resizing = False
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_edit_mode:
            return

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.is_resizing:
                new_w = max(250, event.pos().x())
                new_h = max(60, event.pos().y())
                self.resize(new_w, new_h)
            else:
                new_pos = event.globalPosition().toPoint() - self.drag_position
                self.move(new_pos)
            event.accept()
        else:
            if self._in_resize_zone(event.pos()):
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def mouseReleaseEvent(self, event):
        if self.is_edit_mode and event.button() == Qt.MouseButton.LeftButton:
            self.is_resizing = False
            geo = self.geometry()
            new_pos_dict = {
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height()
            }
            self.config["overlay_position"] = new_pos_dict
            self.position_changed.emit(new_pos_dict)
            event.accept()

    def paintEvent(self, event):
        # Oyun modunda metin yoksa hiçbir şey çizme (hayalet kutu kalmasın)
        if not self.is_edit_mode and not self.current_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()

        font_family = self.config.get("font_family", "Segoe UI")
        font_size = int(self.config.get("font_size", 20))
        font_weight_str = self.config.get("font_weight", "Bold")

        weight_map = {
            "Normal": QFont.Weight.Normal,
            "Medium": QFont.Weight.Medium,
            "Bold": QFont.Weight.Bold,
            "ExtraBold": QFont.Weight.ExtraBold,
            "Black": QFont.Weight.Black
        }
        weight = weight_map.get(font_weight_str, QFont.Weight.Bold)
        font = QFont(font_family, font_size, weight)
        painter.setFont(font)

        alignment_str = self.config.get("alignment", "Left")
        if alignment_str == "Center":
            h_align = Qt.AlignmentFlag.AlignHCenter
        elif alignment_str == "Right":
            h_align = Qt.AlignmentFlag.AlignRight
        else:
            h_align = Qt.AlignmentFlag.AlignLeft

        draw_flags = int(h_align | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
        inner_rect = rect.adjusted(16, 10, -16, -10)

        # Metnin kapladığı gerçek alanı hesapla (Satır yapısını \n ile birebir korur)
        fm = QFontMetrics(font)
        text_bound = fm.boundingRect(inner_rect, draw_flags, self.current_text)

        # 1. Arka Plan Çizimi
        bg_opacity = int(self.config.get("bg_opacity", 120))
        bg_hex = self.config.get("bg_color", "#000000")
        bg_col = QColor(bg_hex)
        bg_col.setAlpha(bg_opacity)

        if self.is_edit_mode:
            painter.fillRect(rect, QColor(0, 0, 0, 170))
            pen = QPen(QColor(255, 215, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            # Sağ alt boyutlandırma tutamacı
            painter.setBrush(QColor(255, 215, 0))
            painter.drawRect(rect.right() - 12, rect.bottom() - 12, 10, 10)
        else:
            if bg_opacity > 0 and self.current_text:
                bg_rect = QRect(
                    rect.left(),
                    rect.top(),
                    rect.width(),
                    min(rect.height(), max(text_bound.height() + 22, 44))
                )
                painter.setBrush(bg_col)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bg_rect, 8, 8)

        if not self.current_text:
            return

        # 2. Metin Çizimi (Kenar Çizgili & Satır Yapısı Korunmuş Altyazı)
        text_color = QColor(self.config.get("text_color", "#FFFFFF"))
        outline_color = QColor(self.config.get("outline_color", "#000000"))
        outline_width = int(self.config.get("outline_width", 2))

        if outline_width > 0:
            painter.setPen(outline_color)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                offset_rect = inner_rect.adjusted(
                    dx * outline_width,
                    dy * outline_width,
                    dx * outline_width,
                    dy * outline_width
                )
                painter.drawText(offset_rect, draw_flags, self.current_text)

        painter.setPen(text_color)
        painter.drawText(inner_rect, draw_flags, self.current_text)
