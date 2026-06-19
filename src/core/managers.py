import sys
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon

from .config import ConfigManager, DatabaseManager
from .platform_utils import (
    activate_application, make_tray_icon, is_macos,
    create_macos_status_item, remove_macos_status_item,
)


class NotificationWorker(QThread):
    notify = pyqtSignal(str, str, str)  # title, message, category_color

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.db = None  # 不在主线程创建
        self.running = True

    def run(self):
        # 在后台线程内独立创建数据库连接
        self.db = DatabaseManager()

        while self.running:
            try:
                if self.config.get("notifications_enabled", True):
                    reminders = self.db.get_pending_reminders()
                    for r in reminders:
                        self.notify.emit(
                            f"⏰ {r['title']}",
                            f"截止时间: {r['due_date'][:16] if r['due_date'] else '未设置'}",
                            r.get('category_color', '#4A90D9')
                        )
                        self.db.mark_reminder_sent(r['id'])
                    # Check repeats
                    repeats = self.db.get_due_repeats()
                    for t in repeats:
                        self.db.spawn_repeat_task(t['id'])
            except Exception as e:
                print(f"NotificationWorker error: {e}")

            # 用可中断的 100ms 循环等待 30 秒,期间任何 stop() 都会立即响应
            for _ in range(300):
                if not self.running:
                    break
                self.msleep(100)

        # 在创建连接的同一线程里 close,避免 SQLite 跨线程访问错误。
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                print(f"NotificationWorker close error: {e}")
            self.db = None

    def stop(self):
        # 仅设置标志;db.close() 由 run() 自己在子线程里调用,
        # 保证 SQLite 连接只在创建它的线程里被使用。
        self.running = False
        # wait() 加 2 秒超时:worker 在 SQLite 锁/长查询中卡住时,主线程不能无限阻塞
        # closeEvent 不返回会让 GUI 假死。超时后由进程退出强制回收子线程 + SQLite。
        if not self.wait(2000):
            print(
                f"[NotificationWorker] stop() 超时 2s,worker 仍在子线程跑 "
                f"(可能在 SQLite 锁/长查询中),将随进程退出强制清理。",
                file=sys.stderr,
            )


class TrayManager:
    """系统托盘管理器。

    macOS 上完全不用 QSystemTrayIcon —— 因为 PyQt5 的 QSystemTrayIcon.setIcon
    在内部把 QIcon 转 NSImage 时会强制把 isTemplate 设为 False,导致 macOS menu bar
    不应用圆形遮罩(用户看到完整方形图片)。改为直接用 NSStatusBar 创建 status item
    + NSImage(template)+ NSMenu,让 macOS 真正按 template image 处理(自动反色 +
    应用 menu bar 圆形遮罩)。

    其他平台继续用 QSystemTrayIcon(行为不变)。
    """

    def __init__(self, app, window, config):
        self.app = app
        self.window = window
        self.config = config

        if is_macos():
            self._init_macos()
        else:
            self._init_qsystemtray()

    def _init_qsystemtray(self):
        """非 macOS 平台:用 QSystemTrayIcon(原行为不变)。"""
        self.backend = "qsystemtray"
        self.tray = QSystemTrayIcon(self.app)
        self.tray.setToolTip("DeskNoteX")
        self.tray.setIcon(make_tray_icon(18))

        menu = QMenu()
        show_action = QAction("显示", menu)
        show_action.triggered.connect(self.show_window)
        hide_action = QAction("隐藏", menu)
        hide_action.triggered.connect(self.hide_window)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def _init_macos(self):
        """macOS 平台:直接用 NSStatusBar 创建 statusItem(template NSImage + NSMenu)。"""
        self.backend = "nsstatus"
        try:
            self.status_item, self.status_target, self.status_bar = (
                create_macos_status_item(
                    on_show=self.show_window,
                    on_hide=self.hide_window,
                    on_quit=self.quit_app,
                    tooltip="DeskNoteX",
                )
            )
        except Exception as exc:
            print(f"[TrayManager] NSStatusBar 创建失败,fallback 到 QSystemTrayIcon: {exc}",
                  file=sys.stderr)
            self.backend = "qsystemtray"
            self._init_qsystemtray()

    def show_window(self):
        # macOS 上 hide() 会让整个 application 进入 hidden 状态,
        # 仅 unhide_ + activateIgnoringOtherApps 还不够,必须让 NSWindow
        # 主动 makeKeyAndOrderFront_ 才能把窗口重新拉到屏幕。
        activate_application()
        if self.window.isMinimized():
            self.window.showNormal()
        else:
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def hide_window(self):
        self.window.hide()

    def on_tray_activated(self, reason):
        """QSystemTrayIcon 双击响应(其他平台)。"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show_window()

    def quit_app(self):
        # tray 自身清理(QSystemTrayIcon 需要 hide,NSStatusItem 由 AppKit 管理)
        if self.backend == "qsystemtray" and hasattr(self, "tray"):
            self.tray.hide()
        # 让 MainWindow 走 closeEvent,统一收尾 refresh_timer + worker + db
        # (closeEvent 末尾会调 app.quit())。
        # 注意:不要在这里再 self.app.quit() —— 双重 quit 在某些 Qt 5.15 patch 上会 warn,
        # 且 closeEvent 已经处理 quit 流程。
        if self.window:
            self.window.close()

    def cleanup(self):
        """应用退出前清理 tray 资源(可选,系统退出时不必)。"""
        if self.backend == "nsstatus":
            try:
                remove_macos_status_item(self.status_item, self.status_bar)
            except Exception as exc:
                print(f"[TrayManager] cleanup 失败: {exc}", file=sys.stderr)

class EdgeTuckManager:
    def __init__(self, window, config):
        self.window = window
        self.config = config
        self.tucked = False
        self.tuck_edge = config.get("tuck_edge", "right")
        self.tucked_width = 6
        self.normal_geometry = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_edge)
        self.timer.start(500)
    
    def check_edge(self):
        if not self.config.get("auto_tuck", True):
            return
        if not self.window.isVisible():
            return
        if self.window.isMaximized() or self.window.isFullScreen():
            return

        # 用窗口所在的屏幕而非 primaryScreen(),否则副屏窗口的"右边"永远对不上
        # primaryScreen.right()(副屏通常在主屏右侧,geo.right() << screen.right())。
        # screenAt 返回 None 时退化到 primaryScreen(罕见,跨屏拖动瞬间)。
        screen = QApplication.screenAt(self.window.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()
        geo = self.window.geometry()
        
        # Check if mouse is near window
        from PyQt5.QtGui import QCursor
        mouse = QCursor.pos()
        
        if not self.tucked:
            # Check if window is at edge and mouse is away
            at_right = abs(geo.right() - screen_geo.right()) < 10
            at_left = abs(geo.left() - screen_geo.left()) < 10

            if at_right and mouse.x() < screen_geo.right() - geo.width():
                self.tuck("right")
            elif at_left and mouse.x() > geo.width():
                self.tuck("left")
        else:
            # Check if mouse is near edge to expand
            if self.tuck_edge == "right" and mouse.x() > screen_geo.right() - 40:
                self.expand()
            elif self.tuck_edge == "left" and mouse.x() < 40:
                self.expand()
    
    def tuck(self, edge):
        if self.tucked:
            return
        self.normal_geometry = self.window.geometry()
        # 同 check_edge:用窗口所在屏幕而非 primaryScreen(),副屏也能正确贴边。
        screen = QApplication.screenAt(self.window.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()
        geo = self.window.geometry()
        if edge == "right":
            geo.setLeft(screen_geo.right() - self.tucked_width)
        else:
            geo.setRight(screen_geo.left() + self.tucked_width)
        self.window.setGeometry(geo)
        self.tucked = True
        self.tuck_edge = edge
    
    def expand(self):
        if not self.tucked or not self.normal_geometry:
            return
        self.window.setGeometry(self.normal_geometry)
        self.tucked = False
    
    def stop(self):
        self.timer.stop()
