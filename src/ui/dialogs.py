from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QComboBox, QCheckBox, QPushButton, QDateTimeEdit,
    QSpinBox, QWidget, QMessageBox
)
from PyQt5.QtCore import Qt, QDateTime

class TaskDialog(QDialog):
    def __init__(self, parent, theme, font_family, font_size, task=None, categories=None):
        super().__init__(parent, Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.theme = theme
        self.task = task
        self.categories = categories or []
        self.result_data = None
        self._setup_ui(font_family, font_size)
        self._apply_theme()
    
    def _setup_ui(self, font_family, font_size):
        from .styles import StyleHelper, get_stylesheet
        self.setStyleSheet(get_stylesheet(self.theme, font_family, font_size))
        
        container = QWidget(self)
        container.setObjectName("dialogContainer")
        container.setStyleSheet(f"""
            QWidget#dialogContainer {{
                background: {self.theme['window']};
                border-radius: 12px;
                border: 1px solid {self.theme['border']};
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title_label = QLabel("编辑任务" if self.task else "新建任务")
        StyleHelper.apply_font(title_label, font_family, font_size + 2, True)
        header.addWidget(title_label)
        header.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_secondary']};
                border-radius: 12px;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background: {self.theme['hover']};
                color: {self.theme['text']};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)
        
        # Title
        layout.addWidget(QLabel("任务标题"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("输入任务标题...")
        if self.task:
            self.title_edit.setText(self.task.get('title', ''))
        layout.addWidget(self.title_edit)
        
        # Content
        layout.addWidget(QLabel("备注内容"))
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("添加详细描述...")
        self.content_edit.setMaximumHeight(100)
        if self.task:
            self.content_edit.setPlainText(self.task.get('content', '') or '')
        layout.addWidget(self.content_edit)
        
        # Category & Priority row
        row1 = QHBoxLayout()
        
        cat_layout = QVBoxLayout()
        cat_layout.addWidget(QLabel("分类"))
        self.cat_combo = QComboBox()
        for cat in self.categories:
            self.cat_combo.addItem(cat['name'], cat['id'])
        if self.task:
            idx = self.cat_combo.findData(self.task.get('category_id', 1))
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
        cat_layout.addWidget(self.cat_combo)
        row1.addLayout(cat_layout)
        
        pri_layout = QVBoxLayout()
        pri_layout.addWidget(QLabel("优先级"))
        self.pri_combo = QComboBox()
        self.pri_combo.addItem("🔴 高", 2)
        self.pri_combo.addItem("🟡 中", 1)
        self.pri_combo.addItem("🟢 低", 0)
        if self.task:
            self.pri_combo.setCurrentIndex(2 - (self.task.get('priority', 1)))
        pri_layout.addWidget(self.pri_combo)
        row1.addLayout(pri_layout)
        
        layout.addLayout(row1)
        
        # Due date
        due_row = QHBoxLayout()
        self.due_enabled_check = QCheckBox("截止时间")
        self.due_enabled_check.setChecked(bool(self.task and self.task.get('due_date')) or not self.task)
        self.due_enabled_check.toggled.connect(self._on_due_enabled_toggled)
        due_row.addWidget(self.due_enabled_check)
        due_row.addStretch()
        layout.addLayout(due_row)

        self.due_edit = QDateTimeEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        if self.task and self.task.get('due_date'):
            from datetime import datetime
            dt = datetime.fromisoformat(self.task['due_date'])
            self.due_edit.setDateTime(QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute))
        else:
            self.due_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        # 编辑模式无 due_date 时,默认勾选=启用(避免丢旧任务数据);
        # 新建模式 + 未勾选时,_save 写 None。
        if self.task and not self.task.get('due_date'):
            self.due_enabled_check.setChecked(False)
        self._on_due_enabled_toggled(self.due_enabled_check.isChecked())
        self.due_edit.setStyleSheet(f"""
            QDateTimeEdit {{
                background: {self.theme['input_bg']};
                border: 1px solid {self.theme['border']};
                border-radius: 8px;
                padding: 4px 8px;
                color: {self.theme['text']};
            }}
            QCalendarWidget {{
                background: {self.theme['window']};
                border: 1px solid {self.theme['border']};
                border-radius: 12px;
            }}
            QCalendarWidget QTableView {{
                background: {self.theme['window']};
                color: {self.theme['text']};
                border: none;
                selection-background-color: {self.theme['accent']};
                selection-color: white;
                gridline-color: {self.theme['border']};
            }}
            QCalendarWidget QTableView::item:selected {{
                background: {self.theme['accent']};
                color: white;
                border-radius: 6px;
            }}
            QCalendarWidget QHeaderView::section {{
                background: {self.theme['card']};
                color: {self.theme['text']};
                border: none;
                padding: 6px;
                font-weight: bold;
            }}
            QCalendarWidget QToolButton {{
                background: {self.theme['card']};
                color: {self.theme['text']};
                border: 1px solid {self.theme['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {self.theme['hover']};
            }}
            QCalendarWidget QSpinBox {{
                background: {self.theme['input_bg']};
                color: {self.theme['text']};
                border: 1px solid {self.theme['border']};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.due_edit)
        
        # Reminder
        remind_row = QHBoxLayout()
        self.remind_check = QCheckBox("开启提醒")
        if self.task:
            self.remind_check.setChecked(self.task.get('remind_enabled', 1) == 1)
        else:
            self.remind_check.setChecked(True)
        remind_row.addWidget(self.remind_check)
        
        self.remind_edit = QDateTimeEdit()
        self.remind_edit.setCalendarPopup(True)
        self.remind_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        if self.task and self.task.get('remind_time'):
            from datetime import datetime
            dt = datetime.fromisoformat(self.task['remind_time'])
            self.remind_edit.setDateTime(QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute))
        else:
            self.remind_edit.setDateTime(QDateTime.currentDateTime().addSecs(1800))
        self.remind_edit.setStyleSheet(f"""
            QDateTimeEdit {{
                background: {self.theme['input_bg']};
                border: 1px solid {self.theme['border']};
                border-radius: 8px;
                padding: 4px 8px;
                color: {self.theme['text']};
            }}
            QCalendarWidget {{
                background: {self.theme['window']};
                border: 1px solid {self.theme['border']};
                border-radius: 12px;
            }}
            QCalendarWidget QTableView {{
                background: {self.theme['window']};
                color: {self.theme['text']};
                border: none;
                selection-background-color: {self.theme['accent']};
                selection-color: white;
                gridline-color: {self.theme['border']};
            }}
            QCalendarWidget QTableView::item:selected {{
                background: {self.theme['accent']};
                color: white;
                border-radius: 6px;
            }}
            QCalendarWidget QHeaderView::section {{
                background: {self.theme['card']};
                color: {self.theme['text']};
                border: none;
                padding: 6px;
                font-weight: bold;
            }}
            QCalendarWidget QToolButton {{
                background: {self.theme['card']};
                color: {self.theme['text']};
                border: 1px solid {self.theme['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {self.theme['hover']};
            }}
            QCalendarWidget QSpinBox {{
                background: {self.theme['input_bg']};
                color: {self.theme['text']};
                border: 1px solid {self.theme['border']};
                border-radius: 4px;
            }}
        """)
        remind_row.addWidget(self.remind_edit)
        layout.addLayout(remind_row)
        
        # Repeat
        repeat_row = QHBoxLayout()
        repeat_layout = QVBoxLayout()
        repeat_layout.addWidget(QLabel("循环规则"))
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItem("不重复", "none")
        self.repeat_combo.addItem("每天", "daily")
        self.repeat_combo.addItem("每周", "weekly")
        self.repeat_combo.addItem("每月", "monthly")
        self.repeat_combo.addItem("每年", "yearly")
        if self.task:
            idx = self.repeat_combo.findData(self.task.get('repeat_type', 'none'))
            if idx >= 0:
                self.repeat_combo.setCurrentIndex(idx)
        repeat_layout.addWidget(self.repeat_combo)
        repeat_row.addLayout(repeat_layout)
        
        interval_layout = QVBoxLayout()
        interval_layout.addWidget(QLabel("间隔"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 99)
        self.interval_spin.setValue(self.task.get('repeat_interval', 1) if self.task else 1)
        interval_layout.addWidget(self.interval_spin)
        repeat_row.addLayout(interval_layout)
        
        layout.addLayout(repeat_row)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        # Main dialog layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        self.setFixedSize(400, 520)
        self._center_on_parent()
    
    def _apply_theme(self):
        from .styles import get_stylesheet
        from PyQt5.QtGui import QFont
        font = QFont(self.parent().font().family(), self.parent().font().pointSize())
        self.setFont(font)
    
    def _center_on_parent(self):
        if self.parent():
            geo = self.geometry()
            parent_geo = self.parent().geometry()
            geo.moveCenter(parent_geo.center())
            self.setGeometry(geo)
    
    def _save(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入任务标题")
            return

        from datetime import datetime
        # due_enabled_check 未勾选 → 写 None(用户明确不要截止日期)。
        if self.due_enabled_check.isChecked():
            due_dt = self.due_edit.dateTime().toPyDateTime()
            due_date = due_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            due_date = None
        remind_dt = self.remind_edit.dateTime().toPyDateTime()

        self.result_data = {
            'title': title,
            'content': self.content_edit.toPlainText().strip(),
            'category_id': self.cat_combo.currentData(),
            'priority': self.pri_combo.currentData(),
            'due_date': due_date,
            'remind_time': remind_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'remind_enabled': 1 if self.remind_check.isChecked() else 0,
            'repeat_type': self.repeat_combo.currentData(),
            'repeat_interval': self.interval_spin.value(),
        }
        self.accept()

    def _on_due_enabled_toggled(self, checked):
        """勾选切换时同步启用/禁用 due_edit,避免改值后被忽略。"""
        self.due_edit.setEnabled(checked)

    def get_data(self):
        return self.result_data
