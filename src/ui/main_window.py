from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QScrollArea, QFrame, QSplitter,
    QSizePolicy, QApplication, QMessageBox, QInputDialog, QMenu,
    QSystemTrayIcon, QAction
)
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QCursor, QColor,QIcon

from ..core.config import ConfigManager, DatabaseManager
from ..core.managers import NotificationWorker, TrayManager, EdgeTuckManager
from .styles import get_stylesheet, StyleHelper
from .task_card import TaskCard, CategoryItem
from .dialogs import TaskDialog
from .settings_dialogs import SettingsDialog, StatsDialog

class MainWindow(QMainWindow):
    theme_changed = pyqtSignal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 图标解析由 platform_utils 统一处理,资源缺失时回退到 Qt 标准图标
        from ..core.platform_utils import get_app_icon_path

        icon_path = get_app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon))

        self.config = ConfigManager()
        self.db = DatabaseManager()
        self.theme = self.config.get_theme()
        self.font_family, self.font_size = self.config.get_font()
        
        self.drag_pos = None
        self.resizing = False
        self.resize_edge = None
        self.current_category = None
        self.current_filter = "all"  # all, active, completed
        
        self._setup_ui()
        self._apply_theme()
        self._load_data()
        self._restore_geometry()
        
        # Notification worker
        # 新代码（修复）
        self.notify_worker = NotificationWorker(self.config)
        self.notify_worker.notify.connect(self._show_notification)
        self.notify_worker.start()
        
        # Edge tuck manager
        self.tuck_manager = EdgeTuckManager(self, self.config)
        
        # Auto refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._load_tasks)
        self.refresh_timer.start(30000)  # Refresh every 30s
    
    def _setup_ui(self):
        self.setStyleSheet(get_stylesheet(self.theme, self.font_family, self.font_size))
        
        # Central container with rounded corners
        self.container = QWidget(self)
        self.container.setObjectName("mainContainer")
        self.container.setStyleSheet(f"""
            QWidget#mainContainer {{
                background: {self.theme['window']};
                border-radius: 16px;
                border: 1px solid {self.theme['border']};
            }}
        """)
        
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Title bar
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(16, 10, 12, 10)
        title_bar.setSpacing(8)

        self.title_label = QLabel("DeskNoteX")
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {self.theme['text']};
                background: transparent;
                font-family: "Forte";
                font-size: {self.font_size + 6}px;
                font-weight: bold;
                border: none;
                padding: 0px;
                margin: 0px;
            }}
        """)
        title_bar.addWidget(self.title_label)
        title_bar.addStretch()
        
        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索任务...")
        self.search_edit.setFixedWidth(140)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {self.theme['input_bg']};
                border: 1px solid {self.theme['border']};
                border-radius: 8px;
                padding: 6px 10px;
                color: {self.theme['text']};
            }}
            QLineEdit:focus {{
                border: 2px solid {self.theme['accent']};
                border-radius: 8px;
                padding: 5px 9px;
            }}
        """)
        self.search_edit.textChanged.connect(self._on_search)
        title_bar.addWidget(self.search_edit)
        
        # Settings button (mini dot)
        self.settings_btn = QPushButton("...")
        self.settings_btn.setFixedSize(28, 20)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border']};
                border-radius: 4px;
                font-size: {self.font_size - 1}px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:hover {{
                background: {self.theme['hover']};
                color: {self.theme['text']};
            }}
        """)
        self.settings_btn.setToolTip("设置")
        self.settings_btn.clicked.connect(self._show_settings_menu)
        title_bar.addWidget(self.settings_btn)
        
        # Minimize button
        self.min_btn = QPushButton("-")
        self.min_btn.setFixedSize(28, 20)
        self.min_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border']};
                border-radius: 4px;
                font-size: {self.font_size}px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background: {self.theme['hover']};
                color: {self.theme['text']};
            }}
        """)
        self.min_btn.clicked.connect(self._minimize_to_tray)
        title_bar.addWidget(self.min_btn)
        
        # Close button
        self.close_btn = QPushButton("x")
        self.close_btn.setFixedSize(28, 20)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border']};
                border-radius: 4px;
                font-size: {self.font_size}px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background: {self.theme['priority_high']};
                color: white;
            }}
        """)
        self.close_btn.clicked.connect(self.close)
        title_bar.addWidget(self.close_btn)

        title_widget = QWidget()
        title_widget.setLayout(title_bar)
        title_widget.setStyleSheet(f"""
            QWidget {{
                border-bottom: 1px solid {self.theme['border']};
                background: {self.theme['window']};
            }}
        """)
        title_widget.mousePressEvent = self._title_mouse_press
        title_widget.mouseMoveEvent = self._title_mouse_move
        title_widget.mouseReleaseEvent = self._title_mouse_release
        main_layout.addWidget(title_widget)
        
        # Body splitter
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        
        # Left sidebar (categories)
        self.sidebar = QVBoxLayout()
        self.sidebar.setContentsMargins(10, 10, 6, 10)
        self.sidebar.setSpacing(6)
        
        sidebar_title = QLabel("分类")
        StyleHelper.apply_font(sidebar_title, self.font_family, self.font_size - 1, True)
        sidebar_title.setStyleSheet(f"color: {self.theme['text_secondary']};")
        self.sidebar.addWidget(sidebar_title)
        
        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cat_scroll.setStyleSheet("background: transparent; border: none;")
        self.cat_container = QWidget()
        self.cat_layout = QVBoxLayout(self.cat_container)
        self.cat_layout.setContentsMargins(0, 0, 0, 0)
        self.cat_layout.setSpacing(4)
        self.cat_layout.addStretch()
        self.cat_scroll.setWidget(self.cat_container)
        self.sidebar.addWidget(self.cat_scroll)
        
        # Add category button
        add_cat_btn = QPushButton("+ 新建分类")
        add_cat_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border: 1px dashed {self.theme['border']};
                border-radius: 8px;
                padding: 6px;
                font-size: {self.font_size - 1}px;
            }}
            QPushButton:hover {{
                background: {self.theme['hover']};
                color: {self.theme['text']};
                border: 1px dashed {self.theme['accent']};
            }}
        """)
        add_cat_btn.clicked.connect(self._add_category)
        self.sidebar.addWidget(add_cat_btn)
        
        sidebar_widget = QWidget()
        sidebar_widget.setLayout(self.sidebar)
        sidebar_widget.setFixedWidth(110)
        sidebar_widget.setStyleSheet(f"border-right: 1px solid {self.theme['border']};")
        body.addWidget(sidebar_widget)
        
        # Right area (tasks + archive)
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(10)
        
        # Filter tabs
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        
        self.filter_all = self._make_filter_btn("全部", "all")
        self.filter_active = self._make_filter_btn("进行中", "active")
        self.filter_completed = self._make_filter_btn("已完成", "completed")
        filter_row.addWidget(self.filter_all)
        filter_row.addWidget(self.filter_active)
        filter_row.addWidget(self.filter_completed)
        filter_row.addStretch()
        
        # Add task button
        self.add_btn = QPushButton("+ 新建任务")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: {self.font_size}px;
            }}
            QPushButton:hover {{
                background: {self.theme['accent'] + 'DD'};
            }}
        """)
        self.add_btn.clicked.connect(self._add_task)
        filter_row.addWidget(self.add_btn)
        
        right.addLayout(filter_row)
        
        # Task list scroll
        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_scroll.setStyleSheet("background: transparent; border: none;")
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.addStretch()
        self.task_scroll.setWidget(self.task_container)
        right.addWidget(self.task_scroll, 1)
        
        # Archive section (collapsible)
        self.archive_header = QHBoxLayout()
        self.archive_toggle = QPushButton("▶ 归档任务")
        self.archive_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border: none;
                text-align: left;
                padding: 4px 0px;
                font-size: {self.font_size - 1}px;
            }}
        """)
        self.archive_toggle.clicked.connect(self._toggle_archive)
        self.archive_header.addWidget(self.archive_toggle)
        self.archive_header.addStretch()
        right.addLayout(self.archive_header)
        
        self.archive_widget = QWidget()
        self.archive_layout = QVBoxLayout(self.archive_widget)
        self.archive_layout.setContentsMargins(0, 0, 0, 0)
        self.archive_layout.setSpacing(6)
        self.archive_layout.addStretch()
        self.archive_widget.hide()
        right.addWidget(self.archive_widget)
        
        right_widget = QWidget()
        right_widget.setLayout(right)
        body.addWidget(right_widget, 1)
        
        body_widget = QWidget()
        body_widget.setLayout(body)
        main_layout.addWidget(body_widget, 1)
        
        self.setCentralWidget(self.container)
        self.setMinimumSize(320, 480)
        self.setMaximumSize(600, 900)
    
    def _make_filter_btn(self, text, filter_type):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(self.current_filter == filter_type)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border: none;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: {self.font_size}px;
            }}
            QPushButton:checked {{
                background: {self.theme['accent'] + '30'};
                color: {self.theme['accent']};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {self.theme['hover']};
            }}
        """)
        btn.clicked.connect(lambda: self._set_filter(filter_type))
        return btn
    
    def _apply_theme(self):
        self.setStyleSheet(get_stylesheet(self.theme, self.font_family, self.font_size))
        self.container.setStyleSheet(f"""
            QWidget#mainContainer {{
                background: {self.theme['window']};
                border-radius: 16px;
                border: 1px solid {self.theme['border']};
            }}
        """)
    
    def _restore_geometry(self):
        pos = self.config.get("window_pos", [100, 100])
        size = self.config.get("window_size", [420, 640])
        self.move(pos[0], pos[1])
        self.resize(size[0], size[1])
        
        if self.config.get("always_on_top", True):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
    
    def _load_data(self):
        self._load_categories()
        self._load_tasks()
    
    def _load_categories(self):
        # Clear existing
        while self.cat_layout.count() > 1:
            item = self.cat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        categories = self.db.get_categories()
        for cat in categories:
            item = CategoryItem(cat, self.theme, self.font_family, self.font_size, 
                               active=(cat['id'] == self.current_category))
            item.selected.connect(self._on_category_selected)
            self.cat_layout.insertWidget(self.cat_layout.count() - 1, item)
    
    def _load_tasks(self):
        # Clear task list
        while self.task_layout.count() > 1:
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear archive
        while self.archive_layout.count() > 1:
            item = self.archive_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        search = self.search_edit.text().strip() or None
        
        if self.current_filter == "completed":
            status = 1
        elif self.current_filter == "active":
            status = 0
        else:
            status = None
        
        tasks = self.db.get_tasks(
            category_id=self.current_category,
            status=status,
            archived=False,
            search=search
        )
        
        for task in tasks:
            if task['status'] == 1 and task.get('archived', 0) == 0:
                # Show completed in archive section? No, keep in main list per spec
                pass
            card = TaskCard(task, self.theme, self.font_family, self.font_size)
            card.clicked.connect(self._on_task_clicked)
            card.toggle_completed.connect(self._on_task_toggled)
            card.delete_task.connect(self._on_task_delete)
            card.edit_task.connect(self._on_task_edit)
            card.archive_task.connect(self._on_task_archive)
            card.restore_task.connect(self._on_task_restore)
            self.task_layout.insertWidget(self.task_layout.count() - 1, card)
        
        # Load archived tasks
        archived = self.db.get_tasks(archived=True, search=search)
        for task in archived:
            card = TaskCard(task, self.theme, self.font_family, self.font_size)
            card.clicked.connect(self._on_task_clicked)
            card.toggle_completed.connect(self._on_task_toggled)
            card.delete_task.connect(self._on_task_delete)
            card.edit_task.connect(self._on_task_edit)
            card.archive_task.connect(self._on_task_archive)
            card.restore_task.connect(self._on_task_restore)
            self.archive_layout.insertWidget(self.archive_layout.count() - 1, card)
        
        self.archive_toggle.setText(f"{'▶' if self.archive_widget.isHidden() else '▼'} 归档任务 ({len(archived)})")
    
    def _on_category_selected(self, cat_id):
        self.current_category = cat_id if cat_id != self.current_category else None
        self._load_categories()
        self._load_tasks()
    
    def _set_filter(self, filter_type):
        self.current_filter = filter_type
        self.filter_all.setChecked(filter_type == "all")
        self.filter_active.setChecked(filter_type == "active")
        self.filter_completed.setChecked(filter_type == "completed")
        self._load_tasks()
    
    def _on_search(self, text):
        self._load_tasks()
    
    def _add_task(self):
        categories = self.db.get_categories()
        dialog = TaskDialog(self, self.theme, self.font_family, self.font_size, categories=categories)
        if dialog.exec_() == TaskDialog.Accepted:
            data = dialog.get_data()
            self.db.add_task(**data)
            self._load_tasks()
    
    def _on_task_clicked(self, task_id):
        pass
    
    def _on_task_toggled(self, task_id, completed):
        self.db.update_task(task_id, status=1 if completed else 0, completed_at=None if not completed else None)
        if completed:
            from datetime import datetime
            self.db.update_task(task_id, completed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self._load_tasks()
    
    def _on_task_delete(self, task_id):
        reply = QMessageBox.question(self, "确认", "确定删除此任务？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_task(task_id)
            self._load_tasks()
    
    def _on_task_edit(self, task_id):
        task = self.db.get_tasks(archived=False)
        task = next((t for t in task if t['id'] == task_id), None)
        if not task:
            return
        categories = self.db.get_categories()
        dialog = TaskDialog(self, self.theme, self.font_family, self.font_size, task=task, categories=categories)
        if dialog.exec_() == TaskDialog.Accepted:
            data = dialog.get_data()
            for k, v in data.items():
                self.db.update_task(task_id, **{k: v})
            self._load_tasks()
    
    def _on_task_archive(self, task_id):
        self.db.update_task(task_id, archived=1)
        self._load_tasks()
    
    def _on_task_restore(self, task_id):
        self.db.update_task(task_id, archived=0)
        self._load_tasks()

    def _add_category(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("新建分类")
        dialog.setLabelText("分类名称:")
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        from ..core.platform_utils import get_app_icon_path
        dialog.setWindowIcon(QIcon(get_app_icon_path()) if get_app_icon_path() else QIcon())
        # 设置对话框样式
        dialog.setStyleSheet(f"""
               QInputDialog {{
                   background: {self.theme['window']};
               }}
               QLabel {{
                   color: {self.theme['text']};
                   font-size: {self.font_size}px;
               }}
               QLineEdit {{
                   background: {self.theme['input_bg']};
                   border: 1px solid {self.theme['border']};
                   border-radius: 8px;
                   padding: 6px 10px;
                   color: {self.theme['text']};
               }}
               QPushButton {{
                   background: {self.theme['accent']};
                   color: white;
                   border: none;
                   border-radius: 8px;
                   padding: 6px 14px;
               }}
           """)

        if dialog.exec_() == QInputDialog.Accepted:
            name = dialog.textValue()
            if name.strip():
                import random
                colors = ["#4A90D9", "#FF6B6B", "#77DD77", "#FFB347", "#9B59B6", "#1ABC9C"]
                color = random.choice(colors)
                cat_id = self.db.add_category(name.strip(), color)
                if cat_id:
                    self._load_categories()
                else:
                    QMessageBox.warning(self, "提示", "分类名称已存在")
    
    def _toggle_archive(self):
        if self.archive_widget.isVisible():
            self.archive_widget.hide()
            self.archive_toggle.setText("▶ 归档任务")
        else:
            self.archive_widget.show()
            self._load_tasks()
    
    def _show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {self.theme['card']};
                border: 1px solid {self.theme['border']};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 6px;
                color: {self.theme['text']};
            }}
            QMenu::item:selected {{
                background: {self.theme['hover']};
            }}
        """)
        
        settings_action = QAction("设置", menu)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        
        stats_action = QAction("数据统计", menu)
        stats_action.triggered.connect(self._open_stats)
        menu.addAction(stats_action)
        
        menu.addSeparator()
        
        ontop_action = QAction("始终置顶", menu)
        ontop_action.setCheckable(True)
        ontop_action.setChecked(self.config.get("always_on_top", True))
        ontop_action.triggered.connect(self._toggle_ontop)
        menu.addAction(ontop_action)
        
        menu.exec_(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))
    
    def _open_settings(self):
        dialog = SettingsDialog(self, self.config, self.theme, self.font_family, self.font_size)
        if dialog.exec_() == SettingsDialog.Accepted:
            new_config = dialog.get_config()
            for k, v in new_config.items():
                self.config.set(k, v)
            self._reload_theme()
    
    def _open_stats(self):
        stats = self.db.get_stats()
        dialog = StatsDialog(self, stats, self.theme, self.font_family, self.font_size, self.db)
        dialog.exec_()
    
    def _toggle_ontop(self, checked):
        self.config.set("always_on_top", checked)
        # Need to recreate window flags
        was_visible = self.isVisible()
        geo = self.geometry()
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        if was_visible:
            self.show()
            self.setGeometry(geo)
    
    def _reload_theme(self):
        self.theme = self.config.get_theme()
        self.font_family, self.font_size = self.config.get_font()
        self._apply_theme()
        self._load_data()
        self.theme_changed.emit()
    
    def _show_notification(self, title, message, color):
        if not hasattr(self, 'tray_manager') or not self.tray_manager:
            return
        from ..core.platform_utils import show_notification
        show_notification(
            self.tray_manager.tray,
            title,
            message,
            color,
            duration_ms=5000,
        )
    
    def _minimize_to_tray(self):
        self.hide()
    
    def _title_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def _title_mouse_move(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()
    
    def _title_mouse_release(self, event):
        self.drag_pos = None
        event.accept()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(event.globalPos() - self.drag_pos)
    
    def mouseReleaseEvent(self, event):
        self.drag_pos = None
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.config.set("window_size", [self.width(), self.height()])
    
    def moveEvent(self, event):
        super().moveEvent(event)
        self.config.set("window_pos", [self.x(), self.y()])
    
    def closeEvent(self, event):
        self.notify_worker.stop()
        self.tuck_manager.stop()
        self.db.close()
        event.accept()
