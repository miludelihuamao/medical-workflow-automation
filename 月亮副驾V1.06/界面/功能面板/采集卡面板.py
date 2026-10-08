# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 功能面板 / 采集卡面板】

用途：
    采集卡功能面板。提供图形界面让用户：
      - 自动连接采集卡，持续读帧并写入 FrameBuffer
      - 全屏预览画面（Q/Esc 退出，S 截图保存）
      - 显示连接状态和分辨率信息

职责：
    1. 打开采集卡，后台线程持续读帧
    2. 每帧写入 硬件/采集卡帧缓存.py 的 FrameBuffer
    3. 支持独立全屏预览 + 截图

被谁使用：
    - 界面/主窗口.py            （作为"开发面板"的一个标签页）

依赖：
    - 界面/功能面板/面板基类.py
    - 硬件/采集卡.py             （CaptureCard 驱动）
    - 硬件/采集卡帧缓存.py        （FrameBuffer）
================================================================
"""
import sys
import os
import time
import ctypes
import importlib.util
from datetime import datetime

# 把项目根目录（月亮副驾/）加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap
import cv2

from 界面.功能面板.面板基类 import BaseModule


# ==================== Windows API ====================
IS_WIN = hasattr(ctypes, "windll")
if IS_WIN:
    user32 = ctypes.windll.user32
else:
    user32 = None

VK_ESCAPE = 0x1B
VK_Q = 0x51
VK_S = 0x53


# ==================== 用 importlib 加载 硬件/ 下的中文文件 ====================
HARDWARE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "硬件")


def _load_module(module_name, file_name):
    path = os.path.join(HARDWARE_DIR, file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 加载驱动
try:
    _cam_mod = _load_module("采集卡驱动", "采集卡.py")
    CaptureCard = _cam_mod.CaptureCard
    CaptureOpenError = _cam_mod.CaptureOpenError
    CaptureConfigError = _cam_mod.CaptureConfigError
except Exception as e:
    _cam_mod = None
    CaptureCard = None
    CaptureOpenError = Exception
    CaptureConfigError = Exception
    print(f"采集卡驱动加载失败: {e}")

from 硬件 import FrameBuffer

# ==================== 读帧线程 ====================
class FrameGrabber(QThread):
    frame_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, cam, buffer):
        super().__init__()
        self.cam = cam
        self.buffer = buffer
        self._run = True

    def run(self):
        while self._run:
            try:
                f = self.cam.read()
            except Exception as e:
                self.error.emit(str(e))
                break
            if f is None:
                time.sleep(0.01)
                continue
            self.buffer.set_frame(f)
            self.frame_ready.emit(f)
            time.sleep(0.003)

    def stop(self):
        self._run = False
        self.wait(1500)


# ==================== 全屏窗口 ====================
class FullscreenWindow(QWidget):
    closed = pyqtSignal()
    snapshot = pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint |
                            Qt.Window)
        self.setStyleSheet("background: black;")
        self.setCursor(Qt.BlankCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: black;")
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.hint = QLabel("Q/Esc 退出    S 截图", self)
        self.hint.setStyleSheet(
            "color: rgba(255,255,255,140); background: transparent;"
            "font-size: 16px;")
        self.hint.adjustSize()
        self.hint.move(20, 20)

        self._pressed = set()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_keys)
        self._poll_timer.start(50)

        if IS_WIN:
            user32.GetAsyncKeyState(VK_ESCAPE)
            user32.GetAsyncKeyState(VK_Q)
            user32.GetAsyncKeyState(VK_S)

    def show_frame(self, qimg):
        pix = QPixmap.fromImage(qimg)
        pix = pix.scaled(self.size(), Qt.KeepAspectRatio,
                         Qt.FastTransformation)
        self.label.setPixmap(pix)
        self.label.setGeometry(0, 0, self.width(), self.height())

    def _poll_keys(self):
        if not IS_WIN:
            return
        for vk in (VK_Q, VK_ESCAPE):
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and vk not in self._pressed:
                self._pressed.add(vk)
                self.close()
                return
            elif not down:
                self._pressed.discard(vk)
        s_down = bool(user32.GetAsyncKeyState(VK_S) & 0x8000)
        if s_down and VK_S not in self._pressed:
            self._pressed.add(VK_S)
            self.snapshot.emit()
        elif not s_down:
            self._pressed.discard(VK_S)

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Q, Qt.Key_Escape):
            self.close()
        elif k == Qt.Key_S:
            self.snapshot.emit()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        self.closed.emit()
        super().closeEvent(e)


# ==================== 主模块 ====================
class HardwareModule(BaseModule):
    name = "采集卡"

    def __init__(self):
        self.cam = None
        self.grabber = None
        self.connected = False
        self._fullscreen = None
        self._last_frame = None
        self._buffer = None

        self.status_label = None
        self.retry_btn = None
        self.btn_fullscreen = None
        self.info_label = None

    def create_widget(self) -> QWidget:
        if FrameBuffer is not None:
            self._buffer = FrameBuffer.get_instance()

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        g = QGroupBox("连接状态")
        h = QHBoxLayout(g)
        self.status_label = QLabel("正在自动连接...")
        self.status_label.setStyleSheet("color: orange; font-size: 14px;")
        h.addWidget(self.status_label)

        self.retry_btn = QPushButton("重试连接")
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self.auto_connect)
        h.addWidget(self.retry_btn)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #666;")
        h.addWidget(self.info_label)
        h.addStretch()
        layout.addWidget(g)

        self.btn_fullscreen = QPushButton("全屏预览")
        self.btn_fullscreen.setMinimumHeight(80)
        self.btn_fullscreen.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                border: 1px solid #ccc; border-radius: 8px;
                background-color: #f0f0f0;
            }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:disabled { color: #aaa; }
        """)
        self.btn_fullscreen.setEnabled(False)
        self.btn_fullscreen.clicked.connect(self._show_fullscreen)
        layout.addWidget(self.btn_fullscreen)

        tip = QLabel("连接后自动持续读帧（供 OCR 使用）；\n"
                     "全屏预览：Q/Esc 退出，S 截图。")
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(tip)

        layout.addStretch()

        QTimer.singleShot(100, self.auto_connect)
        return w

    def auto_connect(self):
        if self.connected:
            return
        if CaptureCard is None:
            self._set_status("驱动加载失败", "red")
            self.retry_btn.setEnabled(True)
            return
        if self._buffer is None:
            self._set_status("帧缓存加载失败", "red")
            self.retry_btn.setEnabled(True)
            return

        self._set_status("正在连接...", "orange")
        self.retry_btn.setEnabled(False)

        try:
            self.cam = CaptureCard()
            self.cam.open()
            info = self.cam.get_actual()

            self.grabber = FrameGrabber(self.cam, self._buffer)
            self.grabber.frame_ready.connect(self._on_frame)
            self.grabber.error.connect(self._on_error)
            self.grabber.start()

            self.connected = True
            self._set_status("已连接（持续读帧）", "green")
            self.info_label.setText(
                f"  {info['width']}×{info['height']} @ {info['fps']:.1f}FPS")
            self.btn_fullscreen.setEnabled(True)
        except Exception as e:
            self.connected = False
            self.cam = None
            self._set_status(f"连接失败: {e}", "red")
            self.retry_btn.setEnabled(True)

    def _set_status(self, text, color):
        if self.status_label:
            self.status_label.setText(text)
            self.status_label.setStyleSheet(
                f"color: {color}; font-size: 14px;")

    def _on_frame(self, frame):
        self._last_frame = frame
        if self._fullscreen is not None:
            try:
                h, w, ch = frame.shape
                qimg = QImage(frame.data, w, h, ch * w,
                              QImage.Format_BGR888)
                self._fullscreen.show_frame(qimg)
            except Exception:
                pass

    def _on_error(self, msg):
        print(f"[采集卡] 错误: {msg}")

    def _show_fullscreen(self):
        if not self.connected:
            QMessageBox.warning(None, "提示", "采集卡未连接")
            return
        if self._fullscreen is not None:
            return

        self._fullscreen = FullscreenWindow()
        self._fullscreen.closed.connect(self._on_fs_closed)
        self._fullscreen.snapshot.connect(self._save_snapshot)
        self._fullscreen.showFullScreen()
        self._fullscreen.raise_()

    def _on_fs_closed(self):
        self._fullscreen = None

    def _save_snapshot(self):
        if self._last_frame is None:
            return
        # 保存到 月亮副驾/数据/截图/
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        save_dir = os.path.join(base, "数据", "截图")
        os.makedirs(save_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = os.path.join(save_dir, f"capture_{ts}.png")
        try:
            ok, buf = cv2.imencode(".png", self._last_frame)
            if ok:
                buf.tofile(path)
                print(f"✅ 截图已保存: {path}")
        except Exception as e:
            print(f"❌ 截图失败: {e}")

    def shutdown(self):
        if self._fullscreen is not None:
            try:
                self._fullscreen.close()
            except Exception:
                pass
            self._fullscreen = None
        if self.grabber is not None:
            try:
                self.grabber.stop()
            except Exception:
                pass
            self.grabber = None
        if self.cam is not None:
            try:
                self.cam.release()
            except Exception:
                pass
            self.cam = None
        if self._buffer is not None:
            try:
                self._buffer.clear()
            except Exception:
                pass
        self.connected = False

    def closeEvent(self, e):
        self.shutdown()
        e.accept()