import sys
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon

from .config import ConfigManager, DatabaseManager
from .platform_utils import activate_application, make_tray_icon


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
        # 仅设置标志并无限等待线程退出;db.close() 由 run() 自己在子线程里调用,
        # 保证 SQLite 连接只在创建它的线程里被使用。
        self.running = False
        self.wait()  # 无超时等待,确保 run() 收尾 close db 后再返回

class TrayManager:
    def __init__(self, app, window, config):
        self.app = app
        self.window = window
        self.config = config
        self.tray = QSystemTrayIcon(app)
        self.tray.setToolTip("DeskNoteX")
        # 用程序绘制的 template icon(macOS 自动反色 + 应用圆形遮罩),
        # 比 Qt 内置 SP_ComputerIcon(彩色,macOS 不遮罩)更符合 menu bar 视觉规范
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
        if reason == QSystemTrayIcon.DoubleClick:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show_window()
    
    def quit_app(self):
        self.tray.hide()
        # 让 MainWindow 走 closeEvent,统一收尾 refresh_timer + worker + db
        if self.window and self.window.isVisible():
            self.window.close()
        self.app.quit()

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
        
        screen = QApplication.primaryScreen().geometry()
        geo = self.window.geometry()
        
        # Check if mouse is near window
        from PyQt5.QtGui import QCursor
        mouse = QCursor.pos()
        
        if not self.tucked:
            # Check if window is at edge and mouse is away
            at_right = abs(geo.right() - screen.right()) < 10
            at_left = abs(geo.left() - screen.left()) < 10
            
            if at_right and mouse.x() < screen.right() - geo.width():
                self.tuck("right")
            elif at_left and mouse.x() > geo.width():
                self.tuck("left")
        else:
            # Check if mouse is near edge to expand
            if self.tuck_edge == "right" and mouse.x() > screen.right() - 40:
                self.expand()
            elif self.tuck_edge == "left" and mouse.x() < 40:
                self.expand()
    
    def tuck(self, edge):
        if self.tucked:
            return
        self.normal_geometry = self.window.geometry()
        screen = QApplication.primaryScreen().geometry()
        geo = self.window.geometry()
        if edge == "right":
            geo.setLeft(screen.right() - self.tucked_width)
        else:
            geo.setRight(screen.left() + self.tucked_width)
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
