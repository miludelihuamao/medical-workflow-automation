# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 主窗口】

用途：
    程序的主窗口。用户看到的第一个界面。
    显示欢迎语、硬件状态、任务按钮（点击执行工作流/编排）。

职责：
    1. 启动时自动连接硬件（采集卡 + 键鼠）
    2. 从 TaskManager 动态加载任务列表，渲染成按钮
    3. 点击任务按钮 → 打开 WorkflowRunner 执行面板
    4. 菜单栏：任务配置、编排管理、开发面板
    5. 支持切换账号

被谁使用：
    - 月亮副驾/main.py          （程序入口）

依赖：
    - 界面/功能面板/OCR面板.py
    - 界面/功能面板/硬件控制面板.py
    - 界面/功能面板/采集卡面板.py
    - 界面/执行面板.py
    - 界面/任务配置窗口.py
    - 界面/编排配置窗口.py
    - 界面/登录对话框.py
    - 核心/任务管理器.py
    - 核心/硬件管理器.py
================================================================
"""
import sys
import os

# 把项目根目录（月亮副驾/）加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QStatusBar,
    QAction, QDialog, QTabWidget, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

from 界面.功能面板.OCR面板 import OcrModule
from 界面.功能面板.硬件控制面板 import HardwareModule
from 界面.功能面板.采集卡面板 import HardwareModule as CameraModule
from 界面.功能面板.手机传文件面板 import HardwareModule as PhoneUploadModule

from 界面.执行面板 import WorkflowRunner
from 核心.任务管理器 import TaskManager
from 界面.任务配置窗口 import TaskConfigDialog
from 界面.编排配置窗口 import FlowConfigDialog
from 核心.硬件管理器 import HardwareManager


class MainWindow(QMainWindow):
    def __init__(self, username=""):
        super().__init__()
        self.username = username
        self.setWindowTitle("月亮副驾")
        self.resize(900, 600)

        self.task_manager = TaskManager()
        self.hw = HardwareManager.get_instance()

        self._init_ui()
        self._init_menu()

        self.hw.status_changed.connect(self._on_hw_status)

        QTimer.singleShot(200, self._auto_connect_hardware)

    # ==================== UI ====================
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        top_row = QHBoxLayout()
        welcome = QLabel(f"欢迎，{self.username}！")
        welcome.setStyleSheet("font-size: 22px; font-weight: bold;")
        top_row.addWidget(welcome)
        top_row.addStretch()

        self.lbl_hw_status = QLabel("硬件连接中...")
        self.lbl_hw_status.setStyleSheet(
            "color: orange; font-size: 12px;")
        top_row.addWidget(self.lbl_hw_status)
        main_layout.addLayout(top_row)

        # 任务按钮
        self.task_container = QWidget()
        self.task_grid = QGridLayout(self.task_container)
        self.task_grid.setSpacing(15)
        main_layout.addWidget(self.task_container)

        self.lbl_empty = QLabel(
            "还没有配置任何任务\n"
            "请通过菜单「任务」→「任务配置」添加")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet(
            "color: #999; font-size: 14px; padding: 40px;")
        main_layout.addWidget(self.lbl_empty)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

        btn_switch = QPushButton("切换账号")
        btn_switch.setFixedWidth(100)
        btn_switch.clicked.connect(self._switch_account)
        main_layout.addWidget(btn_switch, alignment=Qt.AlignRight)

        central.setLayout(main_layout)
        self.statusBar().showMessage("就绪")

        self._refresh_tasks()

    def _init_menu(self):
        menubar = self.menuBar()

        # 任务菜单
        task_menu = menubar.addMenu("任务")
        act_config = QAction("任务配置", self)
        act_config.triggered.connect(self._open_task_config)
        task_menu.addAction(act_config)

        act_reload = QAction("重新加载", self)
        act_reload.triggered.connect(self._refresh_tasks)
        task_menu.addAction(act_reload)

        # 编排菜单
        flow_menu = menubar.addMenu("编排")
        act_flow = QAction("编排管理", self)
        act_flow.triggered.connect(self._open_flow_config)
        flow_menu.addAction(act_flow)

        # 开发菜单
        dev_menu = menubar.addMenu("开发")
        open_dev_action = QAction("打开开发面板", self)
        open_dev_action.triggered.connect(self._open_dev_panel)
        dev_menu.addAction(open_dev_action)

        # 帮助
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ==================== 任务动态渲染 ====================
    def _refresh_tasks(self):
        while self.task_grid.count():
            item = self.task_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        tasks = self.task_manager.get_all()

        if not tasks:
            self.task_container.setVisible(False)
            self.lbl_empty.setVisible(True)
            return

        self.lbl_empty.setVisible(False)
        self.task_container.setVisible(True)

        for idx, task in enumerate(tasks):
            name = task.get("name", "(未命名)")
            desc = task.get("description", "")
            workflow = task.get("workflow", "")

            btn = QPushButton(f"{name}\n{desc}" if desc else name)
            btn.setMinimumHeight(80)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    padding: 10px;
                    background-color: #f9f9f9;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            btn.clicked.connect(
                lambda checked, n=name, w=workflow:
                self._task_clicked(n, w))
            self.task_grid.addWidget(btn, idx // 2, idx % 2)

    def _task_clicked(self, task_name, workflow_path):
        # 相对路径 → 相对于项目根目录（月亮副驾/）
        if not os.path.isabs(workflow_path):
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(base, workflow_path)
        else:
            full_path = workflow_path

        if not os.path.exists(full_path):
            QMessageBox.warning(
                self, "文件不存在",
                f"未找到文件:\n{full_path}")
            return

        self.statusBar().showMessage(f"打开任务：{task_name}")
        try:
            runner = WorkflowRunner(full_path, parent=self)
            runner.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开执行面板失败: {e}")
        finally:
            self.statusBar().showMessage("就绪")

    # ==================== 任务配置 ====================
    def _open_task_config(self):
        dlg = TaskConfigDialog(self)
        dlg.exec_()
        self.task_manager.load()
        self._refresh_tasks()

    # ==================== 编排配置 ====================
    def _open_flow_config(self):
        dlg = FlowConfigDialog(self)
        dlg.exec_()

    # ==================== 硬件自动连接 ====================
    def _auto_connect_hardware(self):
        self.lbl_hw_status.setText("硬件连接中...")
        self.lbl_hw_status.setStyleSheet(
            "color: orange; font-size: 12px;")
        self.hw.connect_all(screen_w=1920, screen_h=1080)
        self._update_hw_label()

    def _on_hw_status(self, device, ok, msg):
        pass

    def _update_hw_label(self):
        cam_ok = self.hw.cam_connected
        hid_ok = self.hw.hid_connected

        text = (f"采集卡: {'✅' if cam_ok else '❌'}   "
                f"键鼠: {'✅' if hid_ok else '❌'}")
        if cam_ok and hid_ok:
            color = "green"
        elif cam_ok or hid_ok:
            color = "orange"
        else:
            color = "red"

        self.lbl_hw_status.setText(text)
        self.lbl_hw_status.setStyleSheet(
            f"color: {color}; font-size: 12px;")

    # ==================== 账号 ====================
    def _switch_account(self):
        self.close()
        from 界面.登录对话框 import LoginDialog
        login = LoginDialog()
        if login.exec_() == LoginDialog.Accepted:
            self.username = login.username
            self._init_ui()
            self.statusBar().showMessage(f"已切换用户：{self.username}")

    # ==================== 开发面板 ====================
    def _open_dev_panel(self):
        dev_dialog = QDialog(self)
        dev_dialog.setWindowTitle("开发面板")
        dev_dialog.resize(800, 600)

        layout = QVBoxLayout(dev_dialog)
        tabs = QTabWidget()

        modules = [
            ("OCR测试", OcrModule()),
            ("硬件控制", HardwareModule()),
            ("采集卡GUI", CameraModule()),
            ("手机传文件", PhoneUploadModule()),
        ]
        for tab_name, module in modules:
            widget = module.create_widget()
            tabs.addTab(widget, tab_name)

        layout.addWidget(tabs)
        dev_dialog.exec_()

    def _show_about(self):
        QMessageBox.information(self, "关于",
                                "月亮副驾 v0.1\n内部测试版")

    def closeEvent(self, e):
        try:
            self.hw.disconnect_all()
        except Exception:
            pass
        e.accept()