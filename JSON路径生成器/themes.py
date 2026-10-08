# themes.py
"""
主题管理器 - 支持深色/浅色主题切换
"""


class ThemeManager:
    """主题管理器"""
    
    def __init__(self):
        self.is_dark = False  # 默认浅色主题
    
    def toggle_theme(self):
        """切换主题"""
        self.is_dark = not self.is_dark
    
    def get_stylesheet(self) -> str:
        """获取当前主题的样式表"""
        if self.is_dark:
            return self._get_dark_theme()
        else:
            return self._get_light_theme()
    
    def _get_dark_theme(self) -> str:
        """深色主题样式"""
        return """
        /* 深色主题 - 基于 #0F172A 深蓝灰 */
        QMainWindow, QWidget {
            background-color: #0F172A;
            color: #F8FAFC;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: 13px;
        }
        
        /* 工具栏 */
        QToolBar {
            background-color: #1E293B;
            border-bottom: 1px solid #334155;
            padding: 6px;
            spacing: 4px;
        }
        
        QToolBar QToolButton {
            background-color: transparent;
            color: #F8FAFC;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            margin: 2px;
        }
        
        QToolBar QToolButton:hover {
            background-color: #334155;
        }
        
        QToolBar QToolButton:pressed {
            background-color: #475569;
        }
        
        /* 树形视图 */
        QTreeWidget {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }
        
        /* 树形视图表头 */
        QHeaderView::section {
            background-color: #1E293B;
            color: #F8FAFC;
            border: none;
            border-bottom: 1px solid #334155;
            padding: 8px;
            font-weight: 600;
        }
        
        QTreeWidget::item {
            padding: 8px;
            border-radius: 4px;
            color: #F8FAFC;
        }
        
        QTreeWidget::item:hover {
            background-color: #334155;
        }
        
        QTreeWidget::item:selected {
            background-color: #38BDF8;
            color: #0F172A;
        }
        
        QTreeWidget::branch:has-children:closed {
            image: url(none);
        }
        
        QTreeWidget::branch:has-children:open {
            image: url(none);
        }
        
        /* 分组框 */
        QGroupBox {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 20px;
            font-weight: 600;
            color: #F8FAFC;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            color: #38BDF8;
        }
        
        /* 输入框 */
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            background-color: #0F172A;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 10px;
            color: #F8FAFC;
            selection-background-color: #38BDF8;
            selection-color: #0F172A;
        }
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #38BDF8;
            background-color: #1E293B;
        }
        
        QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color: #1E293B;
            color: #64748B;
            border: 1px solid #334155;
        }
        
        /* 下拉框 */
        QComboBox {
            background-color: #0F172A;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 10px;
            color: #F8FAFC;
        }
        
        QComboBox:hover {
            border: 1px solid #38BDF8;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        
        QComboBox::down-arrow {
            image: url(none);
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #F8FAFC;
            margin-right: 8px;
        }
        
        QComboBox QAbstractItemView {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 6px;
            selection-background-color: #38BDF8;
            selection-color: #0F172A;
            padding: 4px;
        }
        
        /* 复选框 */
        QCheckBox {
            color: #F8FAFC;
            spacing: 8px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #334155;
            border-radius: 4px;
            background-color: #0F172A;
        }
        
        QCheckBox::indicator:hover {
            border-color: #38BDF8;
        }
        
        QCheckBox::indicator:checked {
            background-color: #38BDF8;
            border-color: #38BDF8;
            image: url(none);
        }
        
        /* 按钮 */
        QPushButton {
            background-color: #38BDF8;
            color: #0F172A;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }
        
        QPushButton:hover {
            background-color: #22D3EE;
        }
        
        QPushButton:pressed {
            background-color: #0EA5E9;
        }
        
        QPushButton:disabled {
            background-color: #334155;
            color: #64748B;
        }
        
        QPushButton[class="secondary"] {
            background-color: #334155;
            color: #F8FAFC;
        }
        
        QPushButton[class="secondary"]:hover {
            background-color: #475569;
        }
        
        QPushButton[class="danger"] {
            background-color: #EF4444;
            color: #FFFFFF;
        }
        
        QPushButton[class="danger"]:hover {
            background-color: #DC2626;
        }
        
        /* 滚动条 */
        QScrollBar:vertical {
            background-color: #1E293B;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #475569;
            border-radius: 6px;
            min-height: 30px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #64748B;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollBar:horizontal {
            background-color: #1E293B;
            height: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #475569;
            border-radius: 6px;
            min-width: 30px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #64748B;
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        
        /* 标签 */
        QLabel#title {
            font-size: 20px;
            font-weight: 700;
            color: #F8FAFC;
            padding: 8px 0;
        }
        
        QLabel#subtitle {
            font-size: 14px;
            color: #94A3B8;
            padding: 4px 0;
        }
        
        /* 状态栏 */
        QStatusBar {
            background-color: #1E293B;
            color: #94A3B8;
            border-top: 1px solid #334155;
        }
        
        /* 菜单 */
        QMenu {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 4px;
        }
        
        QMenu::item {
            padding: 8px 24px;
            border-radius: 4px;
            color: #F8FAFC;
        }
        
        QMenu::item:selected {
            background-color: #38BDF8;
            color: #0F172A;
        }
        
        QMenu::separator {
            height: 1px;
            background-color: #334155;
            margin: 4px 8px;
        }
        
        /* 滚动区域 */
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        
        /* 分割器 */
        QSplitter::handle {
            background-color: #334155;
            width: 2px;
        }
        
        QSplitter::handle:hover {
            background-color: #38BDF8;
        }
        """
    
    def _get_light_theme(self) -> str:
        """浅色主题样式"""
        return """
        /* 浅色主题 - 基于白色和浅灰 */
        QMainWindow, QWidget {
            background-color: #FFFFFF;
            color: #1E293B;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: 13px;
        }
        
        /* 工具栏 */
        QToolBar {
            background-color: #F8FAFC;
            border-bottom: 1px solid #E2E8F0;
            padding: 6px;
            spacing: 4px;
        }
        
        QToolBar QToolButton {
            background-color: transparent;
            color: #1E293B;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            margin: 2px;
        }
        
        QToolBar QToolButton:hover {
            background-color: #E2E8F0;
        }
        
        QToolBar QToolButton:pressed {
            background-color: #CBD5E1;
        }
        
        /* 树形视图 */
        QTreeWidget {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }
        
        /* 树形视图表头 */
        QHeaderView::section {
            background-color: #F8FAFC;
            color: #1E293B;
            border: none;
            border-bottom: 1px solid #E2E8F0;
            padding: 8px;
            font-weight: 600;
        }
        
        QTreeWidget::item {
            padding: 8px;
            border-radius: 4px;
            color: #1E293B;
        }
        
        QTreeWidget::item:hover {
            background-color: #F1F5F9;
        }
        
        QTreeWidget::item:selected {
            background-color: #38BDF8;
            color: #FFFFFF;
        }
        
        /* 分组框 */
        QGroupBox {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 20px;
            font-weight: 600;
            color: #1E293B;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            color: #0EA5E9;
        }
        
        /* 输入框 */
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 6px 10px;
            color: #1E293B;
            selection-background-color: #38BDF8;
            selection-color: #FFFFFF;
        }
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #38BDF8;
            background-color: #FFFFFF;
        }
        
        QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color: #F1F5F9;
            color: #94A3B8;
            border: 1px solid #E2E8F0;
        }
        
        /* 下拉框 */
        QComboBox {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 6px 10px;
            color: #1E293B;
        }
        
        QComboBox:hover {
            border: 1px solid #38BDF8;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        
        QComboBox::down-arrow {
            image: url(none);
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #1E293B;
            margin-right: 8px;
        }
        
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            selection-background-color: #38BDF8;
            selection-color: #FFFFFF;
            padding: 4px;
        }
        
        /* 复选框 */
        QCheckBox {
            color: #1E293B;
            spacing: 8px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #CBD5E1;
            border-radius: 4px;
            background-color: #FFFFFF;
        }
        
        QCheckBox::indicator:hover {
            border-color: #38BDF8;
        }
        
        QCheckBox::indicator:checked {
            background-color: #38BDF8;
            border-color: #38BDF8;
        }
        
        /* 按钮 */
        QPushButton {
            background-color: #38BDF8;
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }
        
        QPushButton:hover {
            background-color: #0EA5E9;
        }
        
        QPushButton:pressed {
            background-color: #0284C7;
        }
        
        QPushButton:disabled {
            background-color: #E2E8F0;
            color: #94A3B8;
        }
        
        QPushButton[class="secondary"] {
            background-color: #E2E8F0;
            color: #1E293B;
        }
        
        QPushButton[class="secondary"]:hover {
            background-color: #CBD5E1;
        }
        
        QPushButton[class="danger"] {
            background-color: #EF4444;
            color: #FFFFFF;
        }
        
        QPushButton[class="danger"]:hover {
            background-color: #DC2626;
        }
        
        /* 滚动条 */
        QScrollBar:vertical {
            background-color: #F8FAFC;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #CBD5E1;
            border-radius: 6px;
            min-height: 30px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #94A3B8;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollBar:horizontal {
            background-color: #F8FAFC;
            height: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #CBD5E1;
            border-radius: 6px;
            min-width: 30px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #94A3B8;
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        
        /* 标签 */
        QLabel#title {
            font-size: 20px;
            font-weight: 700;
            color: #1E293B;
            padding: 8px 0;
        }
        
        QLabel#subtitle {
            font-size: 14px;
            color: #64748B;
            padding: 4px 0;
        }
        
        /* 状态栏 */
        QStatusBar {
            background-color: #F8FAFC;
            color: #64748B;
            border-top: 1px solid #E2E8F0;
        }
        
        /* 菜单 */
        QMenu {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 4px;
        }
        
        QMenu::item {
            padding: 8px 24px;
            border-radius: 4px;
            color: #1E293B;
        }
        
        QMenu::item:selected {
            background-color: #38BDF8;
            color: #FFFFFF;
        }
        
        QMenu::separator {
            height: 1px;
            background-color: #E2E8F0;
            margin: 4px 8px;
        }
        
        /* 滚动区域 */
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        
        /* 分割器 */
        QSplitter::handle {
            background-color: #E2E8F0;
            width: 2px;
        }
        
        QSplitter::handle:hover {
            background-color: #38BDF8;
        }
        """