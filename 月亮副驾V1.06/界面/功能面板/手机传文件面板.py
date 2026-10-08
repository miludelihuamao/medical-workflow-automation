# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 功能面板 / 手机传文件面板】
================================================================

注意：
    涉及到 Qt 信号槽的变量名/方法名用英文（PyQt5 C++ 层不认中文标识符）。
    其他标识符保持中文。
================================================================
"""
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage

from 界面.功能面板.面板基类 import BaseModule
from 核心.工具.手机传文件 import 手机传文件服务

import qrcode
from io import BytesIO


class HardwareModule(BaseModule):
    name = "手机传文件"

    def __init__(self):
        self.服务 = None
        self.保存目录 = None
        self.二维码标签 = None
        self.状态标签 = None
        self.日志框 = None
        self.按钮 = None

        # 待处理文件（HTTP 线程写，主线程读）
        self._pending_files = []      # ← 英文，避免歧义
        self._lock = threading.Lock()

        # 定时器（英文标识符）
        self._poll_timer = None        # ← 英文

    def create_widget(self) -> QWidget:
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        self.保存目录 = os.path.join(base, "数据", "手机上传")
        os.makedirs(self.保存目录, exist_ok=True)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 状态
        status_group = QGroupBox("服务状态")
        status_layout = QHBoxLayout(status_group)
        self.状态标签 = QLabel("未启动")
        self.状态标签.setStyleSheet("color: orange; font-size: 14px;")
        status_layout.addWidget(self.状态标签)
        status_layout.addStretch()
        layout.addWidget(status_group)

        # 按钮
        self.按钮 = QPushButton("启动服务")
        self.按钮.setMinimumHeight(45)
        self.按钮.clicked.connect(self._toggle)     # ← _toggle 已经是英文
        layout.addWidget(self.按钮)

        # 二维码
        qr_group = QGroupBox("扫码上传")
        qr_layout = QVBoxLayout(qr_group)
        self.二维码标签 = QLabel("（启动服务后显示二维码）")
        self.二维码标签.setAlignment(Qt.AlignCenter)
        self.二维码标签.setMinimumHeight(260)
        self.二维码标签.setStyleSheet(
            "background: #f9f9f9; border: 1px solid #ddd;")
        qr_layout.addWidget(self.二维码标签)
        layout.addWidget(qr_group)

        # 日志
        log_group = QGroupBox("上传记录")
        log_layout = QVBoxLayout(log_group)
        self.日志框 = QTextEdit()
        self.日志框.setReadOnly(True)
        self.日志框.setMaximumHeight(120)
        log_layout.addWidget(self.日志框)
        layout.addWidget(log_group)

        layout.addStretch()

        # ★ 定时器（用英文标识符）
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._check_new_files)  # ← 英文方法名
        self._poll_timer.start(500)

        return w

    # ==================== 按钮 ====================
    def _toggle(self):
        if self.服务 is None or not self.服务.是否运行():
            self._start_service()
        else:
            self._stop_service()

    def _start_service(self):
        self.服务 = 手机传文件服务(
            保存目录=self.保存目录,
            端口=8765,
            回调=self._on_upload_callback,   # ← 英文方法名
        )
        if not self.服务.启动():
            QMessageBox.critical(None, "错误", "启动失败，端口可能被占用")
            self.服务 = None
            return

        url = self.服务.获取URL()
        self.状态标签.setText(f"已启动：{url}")
        self.状态标签.setStyleSheet("color: green; font-size: 14px;")
        self.按钮.setText("停止服务")
        self._show_qrcode(url)
        self.日志框.append(f"[已启动] {url}")
        self.日志框.append(f"保存到：{self.保存目录}")

    def _stop_service(self):
        if self.服务 is not None:
            self.服务.停止()
        self.状态标签.setText("未启动")
        self.状态标签.setStyleSheet("color: orange; font-size: 14px;")
        self.按钮.setText("启动服务")
        self.二维码标签.setText("（服务已停止）")
        self.二维码标签.setPixmap(QPixmap())
        self.日志框.append("[已停止]")

    # ==================== 二维码 ====================
    def _show_qrcode(self, text):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        qimage = QImage.fromData(buf.getvalue())
        pix = QPixmap.fromImage(qimage)
        self.二维码标签.setPixmap(pix)

    # ==================== 上传回调（HTTP 线程调用）====================
    def _on_upload_callback(self, 类型, 数据):
        """HTTP 线程调用：只入队，不碰 UI"""
        with self._lock:
            self._pending_files.append((类型, 数据))

    # ==================== 定时器（主线程调用）====================
    def _check_new_files(self):
        with self._lock:
            if not self._pending_files:
                return
            待处理 = self._pending_files
            self._pending_files = []

        for 类型, 数据 in 待处理:
            if 类型 == "file":
                for p in 数据:
                    self.日志框.append(f"[文件] {p}")
            elif 类型 == "text":
                self.日志框.append(f"[文字] {数据}")

        # 汇总提示
        文件数 = sum(len(d) for t, d in 待处理 if t == "file")
        文字数 = sum(1 for t, d in 待处理 if t == "text")
        提示 = []
        if 文件数:
            提示.append(f"{文件数} 个文件")
        if 文字数:
            提示.append(f"{文字数} 条文字")
        if 提示:
            QMessageBox.information(
                None, "收到",
                "收到：" + "、".join(提示) + f"\n保存到：{self.保存目录}")

    # ==================== 退出清理 ====================
    def shutdown(self):
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        if self.服务 is not None:
            self.服务.停止()
            self.服务 = None