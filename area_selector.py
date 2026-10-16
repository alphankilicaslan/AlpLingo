from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor


class AreaSelector(QWidget):
    """Kullanıcının ekranda diyalog alanını sürükleyerek seçmesini sağlayan tam ekran aracı"""
    area_selected = pyqtSignal(dict)
    selection_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        self.begin = QPoint()
        self.end = QPoint()
        self.is_selecting = False

    def start_selection(self):
        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        self.setGeometry(geo)
        self.begin = QPoint()
        self.end = QPoint()
        self.is_selecting = False
        self.showFullScreen()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.pos()
            self.end = self.begin
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end = event.pos()

            x = min(self.begin.x(), self.end.x())
            y = min(self.begin.y(), self.end.y())
            w = abs(self.begin.x() - self.end.x())
            h = abs(self.begin.y() - self.end.y())

            # En az 20x20 piksel alan seçilmiş olmalı
            if w > 20 and h > 20:
                self.area_selected.emit({
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h)
                })
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.selection_closed.emit()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        text = "Farenin Sol Tuşuyla Diyalog / Altyazı Alanını Seçin (İptal için ESC)"
        painter.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignmentFlag.AlignHCenter, text)

        if self.begin != self.end:
            rect = QRect(self.begin, self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)

            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 255, 128), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            painter.setPen(QColor(0, 255, 128))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(rect.x() + 5, max(20, rect.y() - 5), f"{rect.width()} x {rect.height()} px")
