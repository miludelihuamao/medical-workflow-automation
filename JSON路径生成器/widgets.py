# widgets.py
"""
自定义控件集合
"""
import os
from PyQt5.QtWidgets import (
    QWidget, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QFileDialog, QDialog, QTextEdit, QSpinBox, QCheckBox,
    QComboBox, QGroupBox, QFormLayout, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QFont
from PyQt5.QtWidgets import QMessageBox


class ImagePathEdit(QWidget):
    """支持拖拽的图片路径输入框"""
    pathChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setAcceptDrops(True)
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("拖入图片或点击浏览...")
        self.path_edit.textChanged.connect(self.pathChanged.emit)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setFixedWidth(60)
        self.browse_btn.clicked.connect(self.browse_image)
        
        layout.addWidget(self.path_edit)
        layout.addWidget(self.browse_btn)
    
    def browse_image(self):
        """浏览图片文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*.*)"
        )
        if path:
            self.set_path(path)
    
    def set_path(self, path):
        """设置路径"""
        self.path_edit.setText(path)
    
    def get_path(self):
        """获取路径"""
        return self.path_edit.text()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """放下事件"""
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            # 检查是否为图片文件
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                self.set_path(path)
                event.acceptProposedAction()


class MultiImageWidget(QWidget):
    """多图片管理控件（用于识别多个图片定位）"""
    imagesChanged = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 列表显示
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(120)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        
        # 按钮组
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("添加图片")
        self.add_btn.clicked.connect(self.add_image)
        
        self.remove_btn = QPushButton("移除")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_all)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        
        layout.addWidget(self.list_widget)
        layout.addLayout(btn_layout)
        
        # 信号连接
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        
        # 启用拖拽
        self.setAcceptDrops(True)
    
    def add_image(self):
        """添加图片"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*.*)"
        )
        for path in paths:
            if path and path not in self.image_paths:
                self.image_paths.append(path)
                self.list_widget.addItem(os.path.basename(path))
        
        if paths:
            self.imagesChanged.emit(self.image_paths)
    
    def remove_selected(self):
        """移除选中项"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.list_widget.takeItem(current_row)
            self.image_paths.pop(current_row)
            self.imagesChanged.emit(self.image_paths)
    
    def clear_all(self):
        """清空所有"""
        self.list_widget.clear()
        self.image_paths.clear()
        self.imagesChanged.emit([])
    
    def on_selection_changed(self):
        """选择改变"""
        self.remove_btn.setEnabled(self.list_widget.currentRow() >= 0)
    
    def get_images(self):
        """获取所有图片路径"""
        return self.image_paths
    
    def set_images(self, paths):
        """设置图片路径列表"""
        self.clear_all()
        self.image_paths = paths.copy()
        for path in paths:
            self.list_widget.addItem(os.path.basename(path))
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """放下事件"""
        urls = event.mimeData().urls()
        added = False
        for url in urls:
            path = url.toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                if path not in self.image_paths:
                    self.image_paths.append(path)
                    self.list_widget.addItem(os.path.basename(path))
                    added = True
        
        if added:
            event.acceptProposedAction()
            self.imagesChanged.emit(self.image_paths)


class TextImageDialog(QDialog):
    """文字图片生成对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成文字图片")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        # 文字内容
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("输入要生成的文字（1-10个字符）")
        self.text_edit.setMaxLength(10)
        layout.addRow("文字内容:", self.text_edit)
        
        # 字号
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(14)
        self.font_size_spin.setSuffix(" px")
        layout.addRow("字号:", self.font_size_spin)
        
        # 加粗
        self.bold_check = QCheckBox("加粗")
        layout.addRow("样式:", self.bold_check)
        
        # 字体
        self.font_combo = QComboBox()
        self.font_combo.addItems([
            "Microsoft YaHei",
            "SimSun",
            "SimHei",
            "KaiTi",
            "FangSong",
            "Arial",
            "Times New Roman"
        ])
        layout.addRow("字体:", self.font_combo)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.ok_btn = QPushButton("确定")
        self.ok_btn.setObjectName("primary")
        self.ok_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        
        layout.addRow("", btn_layout)
        
        self.setFixedWidth(400)
    
    def get_config(self):
        """获取配置"""
        return {
            'text': self.text_edit.text(),
            'font_size': self.font_size_spin.value(),
            'bold': self.bold_check.isChecked(),
            'font_family': self.font_combo.currentText()
        }


from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QDialog, QComboBox, QCheckBox, QListWidget, QListWidgetItem,
    QFormLayout, QGroupBox, QMessageBox
)
from PyQt5.QtGui import QKeySequence

# 按键下拉框选项（显示文本，Qt键码）
KEY_OPTIONS = [
    ("A", Qt.Key_A), ("B", Qt.Key_B), ("C", Qt.Key_C), ("D", Qt.Key_D),
    ("E", Qt.Key_E), ("F", Qt.Key_F), ("G", Qt.Key_G), ("H", Qt.Key_H),
    ("I", Qt.Key_I), ("J", Qt.Key_J), ("K", Qt.Key_K), ("L", Qt.Key_L),
    ("M", Qt.Key_M), ("N", Qt.Key_N), ("O", Qt.Key_O), ("P", Qt.Key_P),
    ("Q", Qt.Key_Q), ("R", Qt.Key_R), ("S", Qt.Key_S), ("T", Qt.Key_T),
    ("U", Qt.Key_U), ("V", Qt.Key_V), ("W", Qt.Key_W), ("X", Qt.Key_X),
    ("Y", Qt.Key_Y), ("Z", Qt.Key_Z),
    ("0", Qt.Key_0), ("1", Qt.Key_1), ("2", Qt.Key_2), ("3", Qt.Key_3),
    ("4", Qt.Key_4), ("5", Qt.Key_5), ("6", Qt.Key_6), ("7", Qt.Key_7),
    ("8", Qt.Key_8), ("9", Qt.Key_9),
    ("F1", Qt.Key_F1), ("F2", Qt.Key_F2), ("F3", Qt.Key_F3), ("F4", Qt.Key_F4),
    ("F5", Qt.Key_F5), ("F6", Qt.Key_F6), ("F7", Qt.Key_F7), ("F8", Qt.Key_F8),
    ("F9", Qt.Key_F9), ("F10", Qt.Key_F10), ("F11", Qt.Key_F11), ("F12", Qt.Key_F12),
    ("Enter", Qt.Key_Enter), ("Space", Qt.Key_Space), ("Tab", Qt.Key_Tab),
    ("Esc", Qt.Key_Escape), ("Backspace", Qt.Key_Backspace), ("Delete", Qt.Key_Delete),
    ("Up", Qt.Key_Up), ("Down", Qt.Key_Down), ("Left", Qt.Key_Left), ("Right", Qt.Key_Right),
    ("Home", Qt.Key_Home), ("End", Qt.Key_End), ("PageUp", Qt.Key_PageUp), ("PageDown", Qt.Key_PageDown),
]

class KeyRecorderDialog(QDialog):
    """手动配置按键序列的对话框"""
    
    def __init__(self, parent=None, existing_keys=None):
        super().__init__(parent)
        self.setWindowTitle("手动配置按键序列")
        self.setModal(True)
        self.keys = existing_keys.copy() if existing_keys else []
        self.setup_ui()
        self.refresh_list()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        tip_label = QLabel("添加按键组合，最多支持4个按键（每个组合可包含修饰键）")
        tip_label.setObjectName("subtitle")
        layout.addWidget(tip_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.list_widget)
        
        config_group = QGroupBox("添加按键组合")
        config_layout = QFormLayout(config_group)
        
        self.key_combo = QComboBox()
        for text, code in KEY_OPTIONS:
            self.key_combo.addItem(text, code)
        config_layout.addRow("按键:", self.key_combo)
        
        mod_widget = QWidget()
        mod_layout = QHBoxLayout(mod_widget)
        mod_layout.setContentsMargins(0, 0, 0, 0)
        self.ctrl_check = QCheckBox("Ctrl")
        self.shift_check = QCheckBox("Shift")
        self.alt_check = QCheckBox("Alt")
        self.meta_check = QCheckBox("Win")
        mod_layout.addWidget(self.ctrl_check)
        mod_layout.addWidget(self.shift_check)
        mod_layout.addWidget(self.alt_check)
        mod_layout.addWidget(self.meta_check)
        mod_layout.addStretch()
        config_layout.addRow("修饰键:", mod_widget)
        
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_key)
        config_layout.addRow("", self.add_btn)
        
        layout.addWidget(config_group)
        
        btn_layout = QHBoxLayout()
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(self.move_up)
        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(self.move_down)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        dialog_btn = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        dialog_btn.addStretch()
        dialog_btn.addWidget(self.cancel_btn)
        dialog_btn.addWidget(self.ok_btn)
        layout.addLayout(dialog_btn)
        
        self.resize(400, 400)
    
    def add_key(self):
        if len(self.keys) >= 4:
            QMessageBox.warning(self, "提示", "最多只能添加4个按键组合")
            return
        
        key_text = self.key_combo.currentText()
        key_code = self.key_combo.currentData()
        ctrl = self.ctrl_check.isChecked()
        shift = self.shift_check.isChecked()
        alt = self.alt_check.isChecked()
        meta = self.meta_check.isChecked()
        
        key_info = {
            'key': key_code,
            'text': key_text,
            'ctrl': ctrl,
            'shift': shift,
            'alt': alt,
            'meta': meta
        }
        self.keys.append(key_info)
        self.refresh_list()
    
    def remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            del self.keys[row]
            self.refresh_list()
    
    def move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            self.keys[row], self.keys[row-1] = self.keys[row-1], self.keys[row]
            self.refresh_list()
            self.list_widget.setCurrentRow(row-1)
    
    def move_down(self):
        row = self.list_widget.currentRow()
        if row < len(self.keys)-1:
            self.keys[row], self.keys[row+1] = self.keys[row+1], self.keys[row]
            self.refresh_list()
            self.list_widget.setCurrentRow(row+1)
    
    def refresh_list(self):
        self.list_widget.clear()
        for key_info in self.keys:
            mod_text = []
            if key_info['ctrl']:
                mod_text.append('Ctrl')
            if key_info['shift']:
                mod_text.append('Shift')
            if key_info['alt']:
                mod_text.append('Alt')
            if key_info['meta']:
                mod_text.append('Win')
            mod_text.append(key_info['text'])
            display_text = '+'.join(mod_text)
            self.list_widget.addItem(display_text)
        self.ok_btn.setEnabled(len(self.keys) > 0)
    
    def get_recorded_keys(self):
        return self.keys


class KeyRecorderWidget(QWidget):
    """按键序列配置控件（手动配置版）"""
    keysChanged = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recorded_keys = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("点击'配置'按钮添加按键...")
        
        self.config_btn = QPushButton("配置")
        self.config_btn.setFixedWidth(60)
        self.config_btn.clicked.connect(self.open_config_dialog)
        
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedWidth(30)
        self.clear_btn.clicked.connect(self.clear_keys)
        
        layout.addWidget(self.display)
        layout.addWidget(self.config_btn)
        layout.addWidget(self.clear_btn)
    
    def open_config_dialog(self):
        dialog = KeyRecorderDialog(self, existing_keys=self.recorded_keys)
        if dialog.exec_() == QDialog.Accepted:
            self.recorded_keys = dialog.get_recorded_keys()
            self.update_display()
            self.keysChanged.emit(self.recorded_keys)
    
    def clear_keys(self):
        self.recorded_keys.clear()
        self.update_display()
        self.keysChanged.emit([])
    
    def set_keys(self, keys):
        self.recorded_keys = keys
        self.update_display()
    
    def get_keys(self):
        return self.recorded_keys
    
    def update_display(self):
        if not self.recorded_keys:
            self.display.setText("")
            return
        
        parts = []
        for key_info in self.recorded_keys:
            mod_text = []
            if key_info.get('ctrl'):
                mod_text.append('Ctrl')
            if key_info.get('shift'):
                mod_text.append('Shift')
            if key_info.get('alt'):
                mod_text.append('Alt')
            if key_info.get('meta'):
                mod_text.append('Win')
            mod_text.append(key_info['text'])
            parts.append('+'.join(mod_text))
        
        self.display.setText(' → '.join(parts))


class RoiConfigWidget(QWidget):
    """ROI区域配置控件"""
    configChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # X偏移
        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-9999, 9999)
        self.offset_x_spin.setValue(0)
        self.offset_x_spin.valueChanged.connect(self.emit_config)
        layout.addRow("X偏移:", self.offset_x_spin)
        
        # Y偏移
        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-9999, 9999)
        self.offset_y_spin.setValue(-20)
        self.offset_y_spin.valueChanged.connect(self.emit_config)
        layout.addRow("Y偏移:", self.offset_y_spin)
        
        # 宽度
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 9999)
        self.width_spin.setValue(25)
        self.width_spin.valueChanged.connect(self.emit_config)
        layout.addRow("宽度:", self.width_spin)
        
        # 高度
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 9999)
        self.height_spin.setValue(22)
        self.height_spin.valueChanged.connect(self.emit_config)
        layout.addRow("高度:", self.height_spin)
    
    def emit_config(self):
        """发送配置信号"""
        self.configChanged.emit(self.get_config())
    
    def get_config(self):
        """获取配置"""
        return {
            'offset_x': self.offset_x_spin.value(),
            'offset_y': self.offset_y_spin.value(),
            'width': self.width_spin.value(),
            'height': self.height_spin.value()
        }
    
    def set_config(self, config):
        """设置配置"""
        self.offset_x_spin.setValue(config.get('offset_x', 0))
        self.offset_y_spin.setValue(config.get('offset_y', -20))
        self.width_spin.setValue(config.get('width', 25))
        self.height_spin.setValue(config.get('height', 22))