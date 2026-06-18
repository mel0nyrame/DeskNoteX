import sys
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon

from .config import ConfigManager, DatabaseManager


class NotificationWorker(QThread):
    notify = pyqtSignal(str, str, str)  # title, message, category_color

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.db = None  # 不在主线程创建
        self.running = True

    def run(self):
        from time import sleep

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
            sleep(30)  # Check every 30 seconds

    def stop(self):
        self.running = False
        self.wait(1000)
        if self.db:
            self.db.close()  # 关闭线程自己的连接

class TrayManager:
    def __init__(self, app, window, config):
        self.app = app
        self.window = window
        self.config = config
        self.tray = QSystemTrayIcon(app)
        self.tray.setToolTip("DeskNoteX")
        # Use a simple built-in icon if no custom one
        self.tray.setIcon(QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon))
        
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
        self.window.showNormal()
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
