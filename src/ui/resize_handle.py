"""自绘的右下角 resize grip。

画 3 条斜线模拟 macOS 原生 grip 样式。
通过 mousePress / mouseMove / mouseRelease 调父窗口 resize。
不依赖 QSizeGrip,避免后者在某些 Qt 版本下影响父 widget 的样式继承。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget


GRIP_SIZE = 16
GRIP_LINE_COUNT = 3
GRIP_LINE_COLOR = "#999999"        # 默认灰色
GRIP_LINE_HOVER_COLOR = "#666666"  # hover / 拖动时的深灰


class ResizeHandle(QWidget):
    """右下角斜线 grip,按住拖动调整父窗口大小。

    父窗口会被 resize 到鼠标拖动距离 + 起始 size,
    且不超过父窗口的 minimumSize / maximumSize。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(GRIP_SIZE, GRIP_SIZE)
        self.setMouseTracking(True)
        self._hovered = False
        self._dragging = False
        self._drag_start_pos = None
        self._drag_start_size = None

    def enterEvent(self, event):
        self._hovered = True
        self.setCursor(Qt.SizeFDiagCursor)
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        if not self._dragging:
            self.unsetCursor()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPos()
            self._drag_start_size = self.parent().size()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_start_pos is not None:
            parent = self.parent()
            delta = event.globalPos() - self._drag_start_pos
            new_w = max(
                parent.minimumWidth(),
                self._drag_start_size.width() + delta.x(),
            )
            new_h = max(
                parent.minimumHeight(),
                self._drag_start_size.height() + delta.y(),
            )
            max_size = parent.maximumSize()
            if max_size.width() < 16777215:  # QWIDGETSIZE_MAX
                new_w = min(new_w, max_size.width())
            if max_size.height() < 16777215:
                new_h = min(new_h, max_size.height())
            parent.resize(new_w, new_h)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(
            GRIP_LINE_HOVER_COLOR if (self._hovered or self._dragging) else GRIP_LINE_COLOR
        )
        pen = QPen(color)
        pen.setWidth(1)
        painter.setPen(pen)

        # 画 3 条斜线(从右下角向左上方向延伸,每条偏移 3px)
        offset = 3
        spacing = 3
        for i in range(GRIP_LINE_COUNT):
            start_x = GRIP_SIZE - offset - i * spacing
            start_y = GRIP_SIZE - 2
            end_x = 2
            end_y = GRIP_SIZE - offset - i * spacing
            painter.drawLine(start_x, start_y, end_x, end_y)

        painter.end()