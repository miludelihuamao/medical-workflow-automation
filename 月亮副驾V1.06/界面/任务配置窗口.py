# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 任务配置窗口】

用途：
    任务配置对话框。让用户可视化地管理任务列表：
      - 添加新任务（任务名 + 描述 + 工作流文件）
      - 修改/删除已有任务
      - 调整任务顺序
      - 保存到 数据/任务配置.json

职责：
    1. 左侧显示任务列表
    2. 右侧编辑任务详情
    3. 底部按钮：添加 / 更新 / 删除 / 上移 / 下移 / 保存 / 关闭
    4. 浏览按钮：选择工作流 JSON（默认打开 数据/工作流/）

被谁使用：
    - 界面/主窗口.py            （菜单「任务」→「任务配置」）

依赖：
    - 核心/任务管理器.py         （TaskManager 读写配置）
================================================================
"""
import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QWidget, QSplitter
)
from PyQt5.QtCore import Qt

from 核心.任务管理器 import TaskManager


class TaskConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务配置")
        self.resize(800, 500)

        self.manager = TaskManager()
        self.current_index = -1

        self._init_ui()
        self._refresh_list()

    # ==================== UI ====================
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        # ---- 左：任务列表 ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("任务列表："))
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self.list_widget)

        splitter.addWidget(left)

        # ---- 右：编辑区 ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        form_group = QGroupBox("任务详情")
        form_layout = QFormLayout(form_group)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("例如：进入**")
        form_layout.addRow("任务名:", self.edit_name)

        self.edit_desc = QLineEdit()
        self.edit_desc.setPlaceholderText("可选，例如：登录**系统")
        form_layout.addRow("描述:", self.edit_desc)

        # 工作流路径 + 浏览按钮
        path_row = QHBoxLayout()
        self.edit_workflow = QLineEdit()
        self.edit_workflow.setPlaceholderText("数据/工作流/xxx.json")
        path_row.addWidget(self.edit_workflow)

        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_workflow)
        path_row.addWidget(btn_browse)

        form_layout.addRow("工作流:", path_row)

        right_layout.addWidget(form_group)
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # ---- 底部按钮 ----
        btn_row = QHBoxLayout()

        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self._on_add)
        btn_row.addWidget(btn_add)

        btn_update = QPushButton("更新选中")
        btn_update.clicked.connect(self._on_update)
        btn_row.addWidget(btn_update)

        btn_remove = QPushButton("删除选中")
        btn_remove.clicked.connect(self._on_remove)
        btn_row.addWidget(btn_remove)

        btn_row.addSpacing(20)

        btn_up = QPushButton("↑ 上移")
        btn_up.clicked.connect(self._on_move_up)
        btn_row.addWidget(btn_up)

        btn_down = QPushButton("↓ 下移")
        btn_down.clicked.connect(self._on_move_down)
        btn_row.addWidget(btn_down)

        btn_row.addStretch()

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    # ==================== 数据刷新 ====================
    def _refresh_list(self):
        self.list_widget.clear()
        for task in self.manager.get_all():
            name = task.get("name", "(未命名)")
            desc = task.get("description", "")
            text = f"{name}  -  {desc}" if desc else name
            self.list_widget.addItem(QListWidgetItem(text))
        # 选中第一个
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_select(self, row):
        self.current_index = row
        if row < 0:
            return
        tasks = self.manager.get_all()
        if row >= len(tasks):
            return
        task = tasks[row]
        self.edit_name.setText(task.get("name", ""))
        self.edit_desc.setText(task.get("description", ""))
        self.edit_workflow.setText(task.get("workflow", ""))

    # ==================== 按钮事件 ====================
    def _on_add(self):
        name = self.edit_name.text().strip()
        desc = self.edit_desc.text().strip()
        workflow = self.edit_workflow.text().strip()

        if not name:
            QMessageBox.warning(self, "提示", "请填写任务名")
            return
        if not workflow:
            QMessageBox.warning(self, "提示", "请选择工作流 JSON 文件")
            return

        self.manager.add(name, desc, workflow)
        self._clear_form()
        self._refresh_list()

    def _on_update(self):
        if self.current_index < 0:
            QMessageBox.information(self, "提示", "请先在左侧选择一项")
            return
        name = self.edit_name.text().strip()
        desc = self.edit_desc.text().strip()
        workflow = self.edit_workflow.text().strip()

        if not name or not workflow:
            QMessageBox.warning(self, "提示", "任务名和工作流不能为空")
            return

        self.manager.update(self.current_index, name, desc, workflow)
        self._refresh_list()

    def _on_remove(self):
        if self.current_index < 0:
            return
        reply = QMessageBox.question(
            self, "确认", "确定删除选中的任务吗？",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.manager.remove(self.current_index)
            self._clear_form()
            self._refresh_list()

    def _on_move_up(self):
        if self.current_index > 0:
            self.manager.move_up(self.current_index)
            self.current_index -= 1
            self._refresh_list()
            self.list_widget.setCurrentRow(self.current_index)

    def _on_move_down(self):
        if 0 <= self.current_index < len(self.manager.get_all()) - 1:
            self.manager.move_down(self.current_index)
            self.current_index += 1
            self._refresh_list()
            self.list_widget.setCurrentRow(self.current_index)

    def _on_save(self):
        try:
            self.manager.save()
            QMessageBox.information(self, "成功", "任务配置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _browse_workflow(self):
        # 项目根目录 = 月亮副驾/
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 默认从 数据/工作流/ 开始
        default_dir = os.path.join(base, "数据", "工作流")
        if not os.path.exists(default_dir):
            os.makedirs(default_dir, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self, "选择工作流 JSON", default_dir,
            "JSON 文件 (*.json)")
        if not path:
            return

        # 尝试转成相对路径（如果位于项目目录下）
        try:
            rel = os.path.relpath(path, base)
            if not rel.startswith(".."):
                path = rel.replace("\\", "/")
        except Exception:
            pass

        self.edit_workflow.setText(path)

    def _clear_form(self):
        self.edit_name.clear()
        self.edit_desc.clear()
        self.edit_workflow.clear()