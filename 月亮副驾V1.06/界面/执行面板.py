# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 执行面板】

用途：
    执行对话框。当用户在主界面点击任务按钮时弹出。
    自动识别工作流类型（原子 / 编排），启动对应的执行引擎。

职责：
    1. 显示任务信息（名称、类型、文件、分辨率）
    2. 显示硬件连接状态
    3. 提供 开始 / 暂停 / 继续 / 停止 控制
    4. 实时显示执行日志和当前步骤
    5. 根据文件名后缀自动选择 WorkflowWorker 或 FlowWorker

工作流类型判断：
    文件名以 .编排.json 结尾 → FlowWorker（编排）
    其他 .json                 → WorkflowWorker（原子工作流）

被谁使用：
    - 界面/主窗口.py            （点击任务按钮打开）

依赖：
    - 核心/工作流引擎.py         （WorkflowWorker + gen_step_name）
    - 核心/编排引擎.py           （FlowWorker）
    - 核心/定位函数.py           （locate）
    - 核心/硬件管理器.py         （HardwareManager）
================================================================
"""
import sys
import os
import json

# 把项目根目录（月亮副驾/）加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QTextEdit, QMessageBox, QLineEdit
)
from PyQt5.QtCore import Qt

from 核心.工作流引擎 import WorkflowWorker, gen_step_name
from 核心.编排引擎 import FlowWorker
from 核心.定位函数 import locate
from 核心.硬件管理器 import HardwareManager


class WorkflowRunner(QDialog):

    def __init__(self, workflow_path, parent=None):
        super().__init__(parent)
        self.workflow_path = self._abs_path(workflow_path)
        self.worker = None
        self.is_flow = self._detect_flow(self.workflow_path)

        self._init_ui()
        self._load_workflow_info()

    @staticmethod
    def _detect_flow(path):
        """判断是不是编排文件"""
        name = os.path.basename(path)
        return name.endswith(".编排.json")

    def _init_ui(self):
        title = "执行编排" if self.is_flow else "执行工作流"
        self.setWindowTitle(title)
        self.resize(700, 550)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # ---- 任务信息 ----
        info_group = QGroupBox("任务信息")
        info_layout = QVBoxLayout(info_group)

        self.lbl_name = QLabel("任务名: -")
        self.lbl_name.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.lbl_name)

        type_str = "编排" if self.is_flow else "工作流"
        self.lbl_type = QLabel(f"类型: {type_str}")
        self.lbl_type.setStyleSheet("color: #1565c0;")
        info_layout.addWidget(self.lbl_type)

        self.lbl_path = QLabel(f"文件: {os.path.basename(self.workflow_path)}")
        self.lbl_path.setStyleSheet("color: #666; font-size: 11px;")
        info_layout.addWidget(self.lbl_path)

        # 目标机分辨率
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("目标机分辨率:"))
        self.edit_w = QLineEdit("1920")
        self.edit_w.setFixedWidth(60)
        res_row.addWidget(self.edit_w)
        res_row.addWidget(QLabel("×"))
        self.edit_h = QLineEdit("1080")
        self.edit_h.setFixedWidth(60)
        res_row.addWidget(self.edit_h)
        res_row.addStretch()
        info_layout.addLayout(res_row)

        layout.addWidget(info_group)

        # ---- 硬件状态 ----
        hw = HardwareManager.get_instance()
        parts = []
        parts.append("采集卡: " + ("✅" if hw.cam_connected else "❌"))
        parts.append("键鼠: " + ("✅" if hw.hid_connected else "❌"))
        self.lbl_hw = QLabel("硬件状态: " + "   ".join(parts))
        self.lbl_hw.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.lbl_hw)

        # ---- 控制按钮 ----
        ctrl_row = QHBoxLayout()
        self.btn_start = QPushButton("开始")
        self.btn_start.clicked.connect(self._on_start)
        ctrl_row.addWidget(self.btn_start)

        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause)
        ctrl_row.addWidget(self.btn_pause)

        self.btn_resume = QPushButton("继续")
        self.btn_resume.setEnabled(False)
        self.btn_resume.clicked.connect(self._on_resume)
        ctrl_row.addWidget(self.btn_resume)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addStretch()

        layout.addLayout(ctrl_row)

        # ---- 当前步骤 ----
        self.lbl_step = QLabel("当前状态: -")
        self.lbl_step.setStyleSheet("color: #1565c0; font-size: 13px;")
        layout.addWidget(self.lbl_step)

        # ---- 日志 ----
        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout(log_group)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px;")
        log_layout.addWidget(self.txt_log)
        layout.addWidget(log_group, stretch=1)

    def _load_workflow_info(self):
        try:
            with open(self.workflow_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", "未命名")
            if self.is_flow:
                total = len(data.get("nodes", []))
                self.lbl_name.setText(
                    f"任务名: {name}  （共 {total} 个工作流）")
            else:
                total = len(data.get("steps", []))
                self.lbl_name.setText(
                    f"任务名: {name}  （共 {total} 步）")
        except Exception as e:
            self.lbl_name.setText(f"任务名: (读取失败: {e})")

    @staticmethod
    def _abs_path(path):
        if os.path.isabs(path):
            return path
        # 相对路径 → 相对于项目根（月亮副驾/）
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, path)

    def _append_log(self, msg):
        self.txt_log.append(msg)

    # ==================== 按钮 ====================
    def _on_start(self):
        if self.worker is not None and self.worker.isRunning():
            return

        hw = HardwareManager.get_instance()

        if not hw.cam_connected:
            QMessageBox.warning(self, "提示",
                                "采集卡未连接\n请检查硬件后重启程序")
            return
        if not hw.hid_connected:
            QMessageBox.warning(self, "提示",
                                "键鼠串口未连接\n请检查硬件后重启程序")
            return

        try:
            rw = max(2, int(self.edit_w.text()))
            rh = max(2, int(self.edit_h.text()))
        except ValueError:
            QMessageBox.warning(self, "提示", "分辨率必须是整数")
            return

        if hw.mouse is not None:
            hw.mouse.screen_w = rw
            hw.mouse.screen_h = rh

        # 根据类型创建对应 worker
        try:
            if self.is_flow:
                self.worker = FlowWorker(
                    flow_path=self.workflow_path,
                    mouse=hw.mouse,
                    keyboard=hw.keyboard,
                    screenshot_func=hw.screenshot_func,
                    locate_func=locate,
                )
            else:
                self.worker = WorkflowWorker(
                    workflow_path=self.workflow_path,
                    mouse=hw.mouse,
                    keyboard=hw.keyboard,
                    screenshot_func=hw.screenshot_func,
                    locate_func=locate,
                )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建执行器失败: {e}")
            return

        self.worker.log_signal.connect(self._append_log)
        self.worker.error_signal.connect(self._on_error)
        self.worker.finished_signal.connect(self._on_finished)

        if self.is_flow:
            self.worker.node_started.connect(self._on_node_started)

        self.worker.start()
        self._set_running_state(True)

    def _on_pause(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.pause()
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(True)

    def _on_resume(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.resume()
            self.btn_pause.setEnabled(True)
            self.btn_resume.setEnabled(False)

    def _on_stop(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(False)

    # ==================== 引擎信号 ====================
    def _on_node_started(self, idx, name):
        self.lbl_step.setText(f"当前: [{idx+1}] {name}")

    def _on_error(self, msg):
        QMessageBox.critical(self, "执行错误", msg)

    def _on_finished(self, success):
        self._set_running_state(False)
        if success:
            self.lbl_step.setText("当前状态: ✅ 执行完成")
        else:
            self.lbl_step.setText("当前状态: ⏹️ 执行结束")

    def _set_running_state(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(running)
        self.edit_w.setEnabled(not running)
        self.edit_h.setEnabled(not running)

    def closeEvent(self, e):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        e.accept()