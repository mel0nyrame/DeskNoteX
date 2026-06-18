import sys
import os
from PyQt5.QtGui import QIcon

# 设置应用程序 ID（必须在创建 QApplication 之前）
import ctypes

myappid = 'mycompany.desknotex.1.0'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Add src to path
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_path)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from src.ui.main_window import MainWindow


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 加载 .ico 图标（Windows 任务栏只认 .ico）
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, "assets", "icon.ico")
    else:
        icon_path = os.path.join(base_path, "assets", "icon.ico")

    app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    from src.core.managers import TrayManager
    window.tray_manager = TrayManager(app, window, window.config)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()