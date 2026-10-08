# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 功能面板 / OCR面板】
================================================================
"""
import sys
import os
import time
import traceback
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QTextEdit, QFileDialog, QMessageBox, QSplitter,
                             QRadioButton, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from 界面.功能面板.面板基类 import BaseModule
from 核心.OCR引擎 import create_engines
from 硬件 import FrameBuffer


# ==================== 后台识别线程 ====================
class OcrWorker(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, engine, source, declared_type=None, 处理配置=None):
        super().__init__()
        self.engine = engine
        self.source = source
        self.declared_type = declared_type
        self.处理配置 = 处理配置 or {}

    def run(self):
        try:
            self.log_signal.emit(f"使用引擎：{self.engine.name}")

            # ---- 1. 引擎识别 ----
            self.log_signal.emit("[DEBUG] 调用 engine.recognize()")
            ocr结果 = self.engine.recognize(
                self.source,
                log=self.log_signal.emit,
                declared_type=self.declared_type,
            )
            pages_count = len(ocr结果.get("pages", []))
            self.log_signal.emit(f"[DEBUG] 识别完成，pages={pages_count}")

            # ---- 2. 写入缓存 ----
            try:
                from 核心.OCR缓存 import OCR缓存
                OCR缓存.get_instance().set(ocr结果)
                OCR缓存.get_instance().save_to_disk(ocr结果)
            except Exception as e:
                self.log_signal.emit(f"⚠ 缓存写入失败: {e}")

            # ---- 3. 处理调度 ----
            self.log_signal.emit("[DEBUG] 调用处理调度器")
            from 核心.文本处理.处理调度器 import 处理
            加工结果 = 处理(ocr结果, self.处理配置)
            self.log_signal.emit(
                f"[DEBUG] 处理完成，declared_type={加工结果.get('declared_type')}")

            # ---- 4. 发回界面 ----
            self.log_signal.emit("[DEBUG] 发送 result_signal")
            self.result_signal.emit({
                "ocr": ocr结果,
                "processed": 加工结果,
            })
            self.log_signal.emit("[DEBUG] result_signal 已发送")

        except Exception as e:
            tb = traceback.format_exc()
            self.error_signal.emit(f"识别失败: {e}\n{tb}")
        finally:
            self.finished_signal.emit()


# ==================== 主模块 ====================
class OcrModule(BaseModule):
    name = "OCR识别"

    def __init__(self):
        self.engines = {}
        self.image_path = ""
        self.save_dir = ""
        self.worker = None

        self.combo_engine = None
        self.radio_file = None
        self.radio_camera = None
        self.edit_image = None
        self.btn_browse = None
        self.chk_save = None
        self.edit_save_dir = None
        self.btn_save_dir = None
        self.btn_run = None
        self.txt_result = None
        self.txt_log = None

    # ================== UI ==================
    def create_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ---- 引擎选择 ----
        top = QGroupBox("识别引擎")
        top_layout = QHBoxLayout(top)
        top_layout.addWidget(QLabel("引擎:"))
        self.combo_engine = QComboBox()
        try:
            self.engines = create_engines()
            for name in self.engines:
                self.combo_engine.addItem(name)
        except Exception as e:
            self.combo_engine.addItem("(加载失败)")
            print(f"OCR 引擎加载失败: {e}")
        top_layout.addWidget(self.combo_engine)
        top_layout.addStretch()
        layout.addWidget(top)

        # ---- 数据源 ----
        src_group = QGroupBox("数据源")
        src_layout = QVBoxLayout(src_group)

        radio_row = QHBoxLayout()
        self.radio_file = QRadioButton("文件")
        self.radio_camera = QRadioButton("采集卡（当前帧）")
        self.radio_file.setChecked(True)
        radio_row.addWidget(self.radio_file)
        radio_row.addWidget(self.radio_camera)
        radio_row.addStretch()
        src_layout.addLayout(radio_row)

        file_row = QHBoxLayout()
        self.edit_image = QLineEdit()
        self.edit_image.setPlaceholderText("选择图片...")
        self.edit_image.setReadOnly(True)
        file_row.addWidget(self.edit_image)

        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self._browse)
        file_row.addWidget(self.btn_browse)
        src_layout.addLayout(file_row)

        def on_source_changed():
            is_file = self.radio_file.isChecked()
            self.edit_image.setEnabled(is_file)
            self.btn_browse.setEnabled(is_file)
        self.radio_file.toggled.connect(on_source_changed)
        self.radio_camera.toggled.connect(on_source_changed)

        layout.addWidget(src_group)

        # ---- 保存选项 ----
        save_group = QGroupBox("识别画面保存")
        save_layout = QHBoxLayout(save_group)
        self.chk_save = QCheckBox("保存识别时的画面")
        self.chk_save.setChecked(False)
        save_layout.addWidget(self.chk_save)

        self.edit_save_dir = QLineEdit()
        self.edit_save_dir.setPlaceholderText("默认保存到 数据/截图/ocr/")
        save_layout.addWidget(self.edit_save_dir, stretch=1)

        self.btn_save_dir = QPushButton("选择目录")
        self.btn_save_dir.clicked.connect(self._choose_save_dir)
        save_layout.addWidget(self.btn_save_dir)

        layout.addWidget(save_group)

        # ---- 执行按钮 ----
        run_row = QHBoxLayout()
        self.btn_run = QPushButton("开始识别")
        self.btn_run.setMinimumHeight(36)
        self.btn_run.clicked.connect(self._run)
        run_row.addWidget(self.btn_run)
        layout.addLayout(run_row)

        # ---- 结果 + 日志 ----
        split = QSplitter(Qt.Vertical)

        res_group = QGroupBox("识别结果")
        res_layout = QVBoxLayout(res_group)
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        res_layout.addWidget(self.txt_result)
        split.addWidget(res_group)

        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        log_layout.addWidget(self.txt_log)
        split.addWidget(log_group)

        layout.addWidget(split, stretch=1)
        return widget

    # ================== 日志 ==================
    def _log(self, msg):
        if self.txt_log:
            self.txt_log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ================== 文件 / 目录选择 ==================
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.image_path = path
            self.edit_image.setText(path)

    def _choose_save_dir(self):
        d = QFileDialog.getExistingDirectory(None, "选择保存目录")
        if d:
            self.save_dir = d
            self.edit_save_dir.setText(d)

    # ================== 执行 ==================
    def _run(self):
        # 保护：上次还在跑就忽略
        if self.worker is not None and self.worker.isRunning():
            self._log("⚠ 上一次识别还在进行中，忽略本次点击")
            return

        if not self.engines:
            QMessageBox.warning(None, "提示", "没有可用的 OCR 引擎")
            return

        name = self.combo_engine.currentText()
        engine = self.engines.get(name)
        if engine is None:
            QMessageBox.warning(None, "提示", f"引擎 '{name}' 未加载")
            return

        # 数据源
        if self.radio_file.isChecked():
            if not self.image_path:
                QMessageBox.information(None, "提示", "请先选择图片")
                return
            source = self.image_path
            source_desc = f"文件: {os.path.basename(source)}"
        else:
            if FrameBuffer is None:
                QMessageBox.warning(None, "提示", "帧缓存加载失败")
                return
            frame, age = FrameBuffer.get_instance().get_frame()
            if frame is None:
                QMessageBox.warning(None, "提示",
                                    "采集卡当前没有可用帧\n请先打开采集卡模块")
                return
            self._log(f"从缓存取帧，帧龄 {age:.3f}s，尺寸 {frame.shape}")
            source = frame
            source_desc = f"采集卡缓存 ({age*1000:.0f}ms前)"

        if self.chk_save.isChecked():
            self._save_frame(source, source_desc)

        # 声明类型：一律用引擎自带的默认类型
        declared_type = getattr(engine, "default_declared_type", "整段")

        self.btn_run.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.txt_result.clear()
        self._log(f"开始识别 ({source_desc})")

        # 创建 worker
        self.worker = OcrWorker(
            engine, source,
            declared_type=declared_type,
            处理配置=None,
        )

        # 连接信号
        self.worker.log_signal.connect(self._log)
        self.worker.result_signal.connect(self._show_result)
        self.worker.error_signal.connect(self._log)
        self.worker.finished_signal.connect(self._enable_buttons)

        self.worker.start()

    def _enable_buttons(self):
        self.btn_run.setEnabled(True)
        if self.radio_file.isChecked():
            self.btn_browse.setEnabled(True)

    # ================== 通用渲染 ==================
    def _show_result(self, payload):
        print("[DEBUG] _show_result 被调用，payload 类型:", type(payload))

        self.txt_result.clear()

        if not isinstance(payload, dict) or "processed" not in payload:
            self.txt_result.append("payload 异常：")
            self.txt_result.append(str(payload))
            return

        processed = payload["processed"]
        print("[DEBUG] processed 的键:", list(processed.keys()))

        # ========== 顶部：所有字段的摘要 ==========
        self.txt_result.append("【字段摘要】")
        self.txt_result.append(f"  declared_type = {processed.get('declared_type')!r}")
        self.txt_result.append(f"  final_text    = {processed.get('final_text')!r}")
        self.txt_result.append(f"  raw_text 长度 = {len(processed.get('raw_text') or '')}")
        self.txt_result.append(f"  paragraphs    = {len(processed.get('paragraphs') or [])} 段")
        self.txt_result.append(f"  items         = {len(processed.get('items') or [])} 项")
        self.txt_result.append(f"  table         = {len(processed.get('table') or [])} 行")
        self.txt_result.append(f"  table_output  = {len(processed.get('table_output') or [])} 项")
        self.txt_result.append(f"  table_final   = {len(processed.get('table_final') or [])} 项")
        self.txt_result.append(f"  lines         = {len(processed.get('lines') or [])} 行")
        self.txt_result.append("")

        # ========== 段落 ==========
        paragraphs = processed.get("paragraphs") or []
        if paragraphs:
            self.txt_result.append("=" * 50)
            self.txt_result.append(f"【段落】共 {len(paragraphs)} 段")
            for i, p in enumerate(paragraphs, 1):
                title = p.get("title", "")
                header = f"段 {i}"
                if title:
                    header += f"  标题: {title}"
                self.txt_result.append(header)
                self.txt_result.append(f"  {p.get('text', '')}")
                self.txt_result.append("")

        # ========== items ==========
        items = processed.get("items") or []
        if items:
            self.txt_result.append("=" * 50)
            self.txt_result.append(f"【条目】共 {len(items)} 项")
            for i, it in enumerate(items, 1):
                if isinstance(it, dict):
                    parts = "  ".join(str(v) for v in it.values())
                    self.txt_result.append(f"  {i:03d}: {parts}")
                else:
                    self.txt_result.append(f"  {i:03d}: {it}")
            self.txt_result.append("")

        # ========== 分析输出 ==========
        table_output = processed.get("table_output") or []
        if table_output:
            self.txt_result.append("=" * 50)
            self.txt_result.append(f"【分析输出】共 {len(table_output)} 项")
            for it in table_output:
                self.txt_result.append(
                    f"  {it.get('项目','')}  {it.get('结果','')}  "
                    f"{it.get('单位','')}  [{it.get('状态','')}]")
            self.txt_result.append("")

        # ========== 过滤后 ==========
        table_final = processed.get("table_final") or []
        if table_final:
            self.txt_result.append("=" * 50)
            self.txt_result.append(f"【过滤后】共 {len(table_final)} 项")
            for it in table_final:
                self.txt_result.append(
                    f"  {it.get('项目','')}  {it.get('结果','')}  "
                    f"{it.get('单位','')}  [{it.get('状态','')}]")
            self.txt_result.append("")

        # ========== 行列表（通用） ==========
        lines = processed.get("lines") or []
        if lines:
            self.txt_result.append("=" * 50)
            self.txt_result.append(f"【行列表】共 {len(lines)} 行")
            for i, l in enumerate(lines, 1):
                if isinstance(l, dict):
                    text = l.get("text", "")
                    y = l.get("y_mid", 0)
                    self.txt_result.append(f"  {i:03d} [y={y}]: {text}")
                else:
                    self.txt_result.append(f"  {i:03d}: {l}")
            self.txt_result.append("")

        # ========== 最终文本 ==========
        final_text = processed.get("final_text")
        self.txt_result.append("=" * 50)
        self.txt_result.append("【最终文本】")
        self.txt_result.append(repr(final_text))
        self.txt_result.append("")
        self.txt_result.append("（上面 repr(...) 是原始字符串，带引号；下方是普通显示）")
        self.txt_result.append("")
        self.txt_result.append(str(final_text))