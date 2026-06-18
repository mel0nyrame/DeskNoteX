"""macOS 风格的红绿灯按钮控件(关闭 / 最小化 / 放大)。

仅在 macOS 上使用,其他平台保留应用原有的字符按钮。
每个圆默认只显示颜色,鼠标 hover 时圆心显示 × / − / + 符号。
"""

from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QBrush, QPen
from PyQt5.QtWidgets import QWidget


# macOS 红绿灯标准颜色
COLOR_CLOSE = "#FF5F57"
COLOR_MINIMIZE = "#FEBC2E"
COLOR_ZOOM = "#28C840"

# 按下时用的暗色
COLOR_CLOSE_DARK = "#E0443E"
COLOR_MINIMIZE_DARK = "#DEA123"
COLOR_ZOOM_DARK = "#1AAB29"

# hover 符号颜色(深红褐色,贴近 macOS 原生)
HOVER_SYMBOL_COLOR = "#4D0000"

# 圆点几何参数
DOT_DIAMETER = 12
DOT_SPACING = 8
TOTAL_WIDTH = DOT_DIAMETER * 3 + DOT_SPACING * 2
TOTAL_HEIGHT = DOT_DIAMETER


class TrafficLightButtons(QWidget):
    """macOS 风格的红黄绿三圆按钮。

    三个按钮分别发出 close_clicked / minimize_clicked / zoom_clicked 信号。
    """

    close_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()
    zoom_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(TOTAL_WIDTH, TOTAL_HEIGHT)
        self.setMouseTracking(True)
        # None 表示未 hover/pressed;0/1/2 分别对应 close/minimize/zoom
        self._hovered = None
        self._pressed = None

    # --- 几何 ---
    def _dot_rect(self, index):
        """返回第 index 个圆的外接矩形。index: 0=close,1=minimize,2=zoom"""
        x = index * (DOT_DIAMETER + DOT_SPACING)
        return QRect(x, 0, DOT_DIAMETER, DOT_DIAMETER)

    def _dot_at(self, pos):
        """根据局部坐标返回点中的圆 index,未点中返回 None。"""
        for i in range(3):
            if self._dot_rect(i).contains(pos):
                return i
        return None

    # --- 鼠标事件 ---
    def mouseMoveEvent(self, event):
        prev = self._hovered
        self._hovered = self._dot_at(event.pos())
        if prev != self._hovered:
            self.update()

    def leaveEvent(self, event):
        self._hovered = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = self._dot_at(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed is not None:
            released = self._dot_at(event.pos())
            if released == self._pressed:
                if self._pressed == 0:
                    self.close_clicked.emit()
                elif self._pressed == 1:
                    self.minimize_clicked.emit()
                elif self._pressed == 2:
                    self.zoom_clicked.emit()
        self._pressed = None
        self.update()

    # --- 绘制 ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        colors = [COLOR_CLOSE, COLOR_MINIMIZE, COLOR_ZOOM]
        dark_colors = [COLOR_CLOSE_DARK, COLOR_MINIMIZE_DARK, COLOR_ZOOM_DARK]
        symbols = ["×", "−", "+"]  # × − +

        for i in range(3):
            rect = self._dot_rect(i)

            # 按下用暗色,否则用正常色
            if self._pressed == i:
                fill = QColor(dark_colors[i])
            else:
                fill = QColor(colors[i])

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(rect)

            # hover 时在圆心画符号(按下时不画,避免视觉冲突)
            if self._hovered == i and self._pressed != i:
                painter.setPen(QPen(QColor(HOVER_SYMBOL_COLOR)))
                font = QFont()
                font.setPixelSize(9)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(rect, Qt.AlignCenter, symbols[i])

        painter.end()