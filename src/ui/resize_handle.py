"""不可见 resize grip(透明,无视觉)。

仅作为鼠标事件捕获区域,按住拖动调整父窗口大小/位置。
不画任何东西 —— 用户在 macOS 上看不到任何 grip 标记,
但 hover 进入区域时仍会自动切换为对应 resize cursor,
按住拖动可 resize 窗口(与 minimumSize / maximumSize 兼容)。

支持 8 个方向(4 角 + 4 边),通过 edge 参数指定:
  Edge.TOP / Edge.BOTTOM / Edge.LEFT / Edge.RIGHT — 边中点
  Edge.TOPLEFT / Edge.TOPRIGHT / Edge.BOTTOMLEFT / Edge.BOTTOMRIGHT — 角
默认为 Edge.BOTTOMRIGHT(右下角 grip,向后兼容)。

不依赖 QSizeGrip,避免后者在某些 Qt 版本下影响父 widget 的样式继承。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget


GRIP_SIZE = 16
EDGE_GRIP_SIZE = 8  # 边中点 grip 比角 grip 窄,避免抢中间区域


class Edge:
    """8 个 resize 方向的位标记(可组合表示 corner = 两边之和)。"""
    NONE = 0
    LEFT = 1
    TOP = 2
    RIGHT = 4
    BOTTOM = 8
    TOPLEFT = TOP | LEFT        # 3
    TOPRIGHT = TOP | RIGHT      # 6
    BOTTOMLEFT = BOTTOM | LEFT  # 9
    BOTTOMRIGHT = BOTTOM | RIGHT  # 12


# 每条 edge 对应的鼠标光标
_EDGE_CURSOR = {
    Edge.LEFT: Qt.SizeHorCursor,
    Edge.RIGHT: Qt.SizeHorCursor,
    Edge.TOP: Qt.SizeVerCursor,
    Edge.BOTTOM: Qt.SizeVerCursor,
    Edge.TOPLEFT: Qt.SizeFDiagCursor,
    Edge.BOTTOMRIGHT: Qt.SizeFDiagCursor,
    Edge.TOPRIGHT: Qt.SizeBDiagCursor,
    Edge.BOTTOMLEFT: Qt.SizeBDiagCursor,
}


class ResizeHandle(QWidget):
    """不可见 grip,按住拖动调整父窗口大小(对应 edge 方向)。

    edge 为边中点(LEFT/RIGHT/TOP/BOTTOM)时 grip 沿整条边;
    edge 为角时 grip 在角上,大小为 GRIP_SIZE。
    """

    def __init__(self, edge=Edge.BOTTOMRIGHT, parent=None):
        super().__init__(parent)
        self.edge = edge
        is_corner = (edge in (
            Edge.TOPLEFT, Edge.TOPRIGHT, Edge.BOTTOMLEFT, Edge.BOTTOMRIGHT,
        ))
        if is_corner:
            self.setFixedSize(GRIP_SIZE, GRIP_SIZE)
        else:
            # 边 grip:横向边 grip 沿宽,纵向边 grip 沿高,中间细一条
            if edge in (Edge.TOP, Edge.BOTTOM):
                self.setFixedSize(GRIP_SIZE * 6, EDGE_GRIP_SIZE)
            else:
                self.setFixedSize(EDGE_GRIP_SIZE, GRIP_SIZE * 6)
        self.setMouseTracking(True)
        self._dragging = False
        self._drag_start_pos = None
        self._drag_start_size = None
        self._drag_start_window_pos = None

    def enterEvent(self, event):
        # 进入区域:切换光标为对应 resize cursor
        self.setCursor(_EDGE_CURSOR.get(self.edge, Qt.ArrowCursor))

    def leaveEvent(self, event):
        if not self._dragging:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPos()
            parent = self.parent()
            self._drag_start_size = parent.size()
            self._drag_start_window_pos = parent.pos()
            # 独占鼠标事件:鼠标移出 grip 区域后 mouseMoveEvent 仍投递到本 widget,
            # 否则会被派给光标下方的 widget(标题栏 / mainContainer 等),resize 卡死。
            self.grabMouse()

    def mouseMoveEvent(self, event):
        if not self._dragging or self._drag_start_pos is None:
            return
        parent = self.parent()
        delta = event.globalPos() - self._drag_start_pos
        # 从起始 size + delta 算出新 size
        new_w = self._drag_start_size.width()
        new_h = self._drag_start_size.height()
        new_x = self._drag_start_window_pos.x()
        new_y = self._drag_start_window_pos.y()
        if self.edge & Edge.LEFT:
            new_w = max(parent.minimumWidth(), new_w - delta.x())
        if self.edge & Edge.RIGHT:
            new_w = max(parent.minimumWidth(), new_w + delta.x())
        if self.edge & Edge.TOP:
            new_h = max(parent.minimumHeight(), new_h - delta.y())
        if self.edge & Edge.BOTTOM:
            new_h = max(parent.minimumHeight(), new_h + delta.y())
        max_size = parent.maximumSize()
        if max_size.width() < 16777215:  # QWIDGETSIZE_MAX
            new_w = min(new_w, max_size.width())
        if max_size.height() < 16777215:
            new_h = min(new_h, max_size.height())

        # 边涉及 LEFT/TOP 时,resize 后需重新计算 x/y,让窗口的"右边/底边"
        # 保持在原位(用户感知:抓住左边拖动,右边不动)。
        actual_delta_w = new_w - self._drag_start_size.width()
        actual_delta_h = new_h - self._drag_start_size.height()
        if self.edge & Edge.LEFT:
            new_x = self._drag_start_window_pos.x() - actual_delta_w
        if self.edge & Edge.TOP:
            new_y = self._drag_start_window_pos.y() - actual_delta_h
        parent.setGeometry(new_x, new_y, new_w, new_h)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            # 释放独占,让鼠标事件恢复正常路由。
            self.releaseMouse()