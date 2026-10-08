# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 功能面板 / 键鼠接管面板】

用途：
    键鼠接管功能面板。
      - 全屏透明覆盖层接收鼠标事件，映射到目标机
      - 键盘钩子把本机按键实时转发到目标机
      - 采集卡画面显示在透明覆盖层下方
      - 退出热键：Fn/Ctrl/Shift + Delete 或 Esc
      - 附带"全屏预览"按钮，可单独查看采集卡画面并截图

职责：
    1. 打开共享串口（键鼠共用一个 CH9329）
    2. 安装键盘钩子，转发按键
    3. 启用鼠标透明覆盖层，转发鼠标事件
    4. 采集卡读帧 → 显示在覆盖层下方

被谁使用：
    - 界面/主窗口.py            （作为"开发面板"的一个标签页）

依赖：
    - 界面/功能面板/面板基类.py
    - 硬件/CH9329鼠标.py
    - 硬件/CH9329键盘.py
    - 硬件/采集卡.py
    - 硬件/采集卡帧缓存.py        （FrameBuffer）
================================================================
"""
import sys
import os
import time
import ctypes
import importlib.util
import threading
from datetime import datetime

# 把项目根目录（月亮副驾/）加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QMessageBox, QTextEdit, QLineEdit, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap
import cv2

from 界面.功能面板.面板基类 import BaseModule
from 硬件 import FrameBuffer


# ========================================================
# Windows API
# ========================================================
IS_WIN = hasattr(ctypes, "windll")
if IS_WIN:
    user32 = ctypes.windll.user32
else:
    user32 = None

VK_ESCAPE = 0x1B
VK_DELETE = 0x2E
VK_FN = 0xFF
VK_Q = 0x51
VK_S = 0x53
VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1
VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
VK_LMENU, VK_RMENU = 0xA4, 0xA5
VK_LWIN, VK_RWIN = 0x5B, 0x5C


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_ulong),
                ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


def lock_cursor(x, y, w, h):
    if IS_WIN:
        r = RECT(int(x), int(y), int(x + w), int(y + h))
        user32.ClipCursor(ctypes.byref(r))


def unlock_cursor():
    if IS_WIN:
        user32.ClipCursor(None)


# ========================================================
# 加载硬件驱动（从 硬件/ 下动态加载）
# ========================================================
HARDWARE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "硬件")


def _load_module(module_alias, file_name):
    path = os.path.join(HARDWARE_DIR, file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    spec = importlib.util.spec_from_file_location(module_alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    HardwareMouse = _load_module("CH9329鼠标", "CH9329鼠标.py").HardwareMouse
except Exception as e:
    HardwareMouse = None
    print(f"鼠标驱动加载失败: {e}")

try:
    CH9329 = _load_module("CH9329键盘", "CH9329键盘.py").CH9329
except Exception as e:
    CH9329 = None
    print(f"键盘驱动加载失败: {e}")

try:
    _cam_mod = _load_module("采集卡驱动", "采集卡.py")
    CaptureCard = _cam_mod.CaptureCard
except Exception as e:
    CaptureCard = None
    print(f"采集卡驱动加载失败: {e}")


# ========================================================
# VK → CH9329 HID 键码表
# ========================================================
VK_TO_HID = {
    **{0x41 + i: f"{0x04 + i:02X}" for i in range(26)},
    0x31: "1E", 0x32: "1F", 0x33: "20", 0x34: "21", 0x35: "22",
    0x36: "23", 0x37: "24", 0x38: "25", 0x39: "26", 0x30: "27",
    0x0D: "28", 0x1B: "29", 0x08: "2A", 0x09: "2B", 0x20: "2C",
    0xBD: "2D", 0xBB: "2E", 0xDB: "2F", 0xDD: "30", 0xDC: "31",
    0xBA: "33", 0xDE: "34", 0xC0: "35", 0xBC: "36", 0xBE: "37", 0xBF: "38",
    0x14: "39",
    0x70: "3A", 0x71: "3B", 0x72: "3C", 0x73: "3D", 0x74: "3E", 0x75: "3F",
    0x76: "40", 0x77: "41", 0x78: "42", 0x79: "43", 0x7A: "44", 0x7B: "45",
    0x2D: "49", 0x24: "4A", 0x21: "4B", 0x2E: "4C", 0x23: "4D", 0x22: "4E",
    0x27: "4F", 0x25: "50", 0x28: "51", 0x26: "52",
    0x60: "62", 0x61: "59", 0x62: "5A", 0x63: "5B",
    0x64: "5C", 0x65: "5D", 0x66: "5E", 0x67: "5F",
    0x68: "60", 0x69: "61",
    0x6A: "55", 0x6B: "57", 0x6D: "56", 0x6E: "63", 0x6F: "54",
}

VK_MODIFIER = {
    VK_LSHIFT: 0x02, VK_RSHIFT: 0x20,
    VK_LCONTROL: 0x01, VK_RCONTROL: 0x10,
    VK_LMENU: 0x04, VK_RMENU: 0x40,
    VK_LWIN: 0x08, VK_RWIN: 0x80,
}


class KeyboardHook:
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104

    def __init__(self, callback):
        self.callback = callback
        self.hook_id = None
        self._proc = None

    def install(self):
        if not IS_WIN:
            return False
        self._proc = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p)(self._hook_proc)
        self.hook_id = user32.SetWindowsHookExW(
            self.WH_KEYBOARD_LL, self._proc, None, 0)
        return bool(self.hook_id)

    def uninstall(self):
        if self.hook_id:
            try:
                user32.UnhookWindowsHookEx(self.hook_id)
            except Exception:
                pass
            self.hook_id = None
            self._proc = None

    def _hook_proc(self, ncode, wparam, lparam):
        if ncode >= 0:
            try:
                kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                is_down = wparam in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN)
                if self.callback(kb.vkCode, is_down):
                    return 1
            except Exception:
                pass
        return user32.CallNextHookEx(self.hook_id, ncode, wparam, lparam)


# ========================================================
# 鼠标接管覆盖层
# ========================================================
class MouseOverlay(QWidget):
    signal_move = pyqtSignal(int, int)
    signal_press = pyqtSignal(int, int, str)
    signal_release = pyqtSignal(int, int, str)
    signal_wheel = pyqtSignal(int, int, int)

    def __init__(self, tw, th, region):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint |
                            Qt.Window)
        self.setWindowOpacity(0.01)
        self.setStyleSheet("background-color: black;")
        self.setCursor(Qt.BlankCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.tw = max(2, int(tw))
        self.th = max(2, int(th))
        self.region = region

    def _map(self, pos):
        x, y, w, h = self.region
        rx = max(0.0, min(1.0, (pos.x() - x) / max(1, w)))
        ry = max(0.0, min(1.0, (pos.y() - y) / max(1, h)))
        return int(rx * (self.tw - 1)), int(ry * (self.th - 1))

    def mouseMoveEvent(self, e):
        tx, ty = self._map(e.pos())
        self.signal_move.emit(tx, ty)

    def mousePressEvent(self, e):
        tx, ty = self._map(e.pos())
        b = {Qt.LeftButton: "left", Qt.RightButton: "right",
             Qt.MiddleButton: "middle"}.get(e.button())
        if b:
            self.signal_press.emit(tx, ty, b)

    def mouseReleaseEvent(self, e):
        tx, ty = self._map(e.pos())
        b = {Qt.LeftButton: "left", Qt.RightButton: "right",
             Qt.MiddleButton: "middle"}.get(e.button())
        if b:
            self.signal_release.emit(tx, ty, b)

    def wheelEvent(self, e):
        tx, ty = self._map(e.pos())
        amt = e.angleDelta().y() // 120
        if amt:
            self.signal_wheel.emit(tx, ty, amt)


# ========================================================
# 采集卡画面全屏窗口（位于覆盖层下方，不接收鼠标事件）
# ========================================================
class CaptureDisplayWindow(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint |
                            Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: black;")
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: black;")
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def resizeEvent(self, e):
        self.label.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(e)

    def show_frame(self, qimg):
        pix = QPixmap.fromImage(qimg)
        pix = pix.scaled(self.size(), Qt.KeepAspectRatio,
                         Qt.FastTransformation)
        self.label.setPixmap(pix)


# ========================================================
# 采集卡读帧线程
# ========================================================
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


# ========================================================
# 采集卡独立全屏预览（S 截图、Q/Esc 退出）
# ========================================================
class FullscreenPreview(QWidget):
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


# ========================================================
# 主模块
# ========================================================
class HardwareModule(BaseModule):
    name = "接管"

    def __init__(self):
        # 键鼠
        self.ser = None
        self.mouse = None
        self.keyboard = None

        # 覆盖层
        self.overlay = None
        self.display = None  # 采集卡画面窗口

        # 采集卡
        self.cam = None
        self.grabber = None
        self._buffer = FrameBuffer.get_instance() if FrameBuffer else None
        self.cam_connected = False
        self._fullscreen_preview = None
        self._last_frame = None

        # 鼠标队列
        self._tx_queue = []
        self._tx_lock = threading.Lock()
        self._tx_event = threading.Event()
        self._tx_thread = None
        self._stop_flag = False
        self.current_button = None
        self._pending_ui = None

        # 键盘
        self.hook = None
        self._mod_state = 0
        self._pressed_keys = set()
        self._kb_send_lock = threading.Lock()

        # 退出请求（钩子线程设置，主线程读取）
        self._exit_requested = False

        # 定时器
        self._tick_timer = None
        self._tick_count = 0

        # 状态
        self.capturing = False
        self.rw, self.rh = 1920, 1080
        self._cx = self._cy = 0
        self._cw = self._ch = 1920

        # UI
        self.status_label = None
        self.edit_w = None
        self.edit_h = None
        self.btn_start = None
        self.btn_send = None
        self.txt_input = None
        self.coord_label = None
        self.txt_log = None
        self.cam_status_label = None
        self.cam_retry_btn = None
        self.cam_info_label = None
        self.cam_btn_fullscreen = None

    # ================== UI ==================
    def create_widget(self) -> QWidget:
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # ========== 键鼠接管面板 ==========
        hid_group = QGroupBox("键鼠接管")
        hid_layout = QVBoxLayout(hid_group)

        tip = QLabel("文本发送：临时打开串口。\n"
                     "鼠标接管：透明覆盖层接收鼠标 + 键盘钩子转发按键。\n"
                     "退出：Fn/Ctrl/Shift + Delete  或  Esc")
        tip.setStyleSheet("color: #555; font-size: 11px;")
        tip.setWordWrap(True)
        hid_layout.addWidget(tip)

        # 文本发送
        ig = QGroupBox("文本发送")
        il = QVBoxLayout(ig)
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("要发送的文本...")
        self.txt_input.setMaximumHeight(50)
        il.addWidget(self.txt_input)
        self.btn_send = QPushButton("发送文本")
        self.btn_send.clicked.connect(self._send_text)
        il.addWidget(self.btn_send)
        hid_layout.addWidget(ig)

        # 目标机设置
        cg = QGroupBox("目标机设置")
        cl = QHBoxLayout(cg)
        cl.addWidget(QLabel("分辨率:"))
        self.edit_w = QLineEdit("1920")
        self.edit_w.setFixedWidth(60)
        cl.addWidget(self.edit_w)
        cl.addWidget(QLabel("×"))
        self.edit_h = QLineEdit("1080")
        self.edit_h.setFixedWidth(60)
        cl.addWidget(self.edit_h)
        cl.addStretch()
        hid_layout.addWidget(cg)

        # 状态 + 接管按钮
        row = QHBoxLayout()
        self.status_label = QLabel("未接管")
        self.status_label.setStyleSheet(
            "color: gray; font-weight: bold; font-size: 13px;")
        row.addWidget(self.status_label)
        row.addStretch()
        self.coord_label = QLabel("目标坐标: -")
        self.coord_label.setStyleSheet("color: #666;")
        row.addWidget(self.coord_label)
        hid_layout.addLayout(row)

        self.btn_start = QPushButton("开始接管（键鼠 + 采集卡画面）")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #a5d6a7;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #d4ecd5; }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #bdbdbd;
            }
        """)
        self.btn_start.clicked.connect(self.start_capture)
        hid_layout.addWidget(self.btn_start)

        # 日志
        lg = QGroupBox("操作日志")
        ll = QVBoxLayout(lg)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(80)
        ll.addWidget(self.txt_log)
        hid_layout.addWidget(lg)

        layout.addWidget(hid_group)

        # ========== 采集卡面板 ==========
        cam_group = QGroupBox("采集卡")
        cam_layout = QVBoxLayout(cam_group)

        ch = QHBoxLayout()
        self.cam_status_label = QLabel("正在自动连接...")
        self.cam_status_label.setStyleSheet(
            "color: orange; font-size: 13px;")
        ch.addWidget(self.cam_status_label)

        self.cam_retry_btn = QPushButton("重试连接")
        self.cam_retry_btn.setEnabled(False)
        self.cam_retry_btn.clicked.connect(self._auto_connect_camera)
        ch.addWidget(self.cam_retry_btn)

        self.cam_info_label = QLabel("")
        self.cam_info_label.setStyleSheet("color: #666;")
        ch.addWidget(self.cam_info_label)
        ch.addStretch()
        cam_layout.addLayout(ch)

        self.cam_btn_fullscreen = QPushButton(
            "全屏预览（Q/Esc 退出，S 截图）")
        self.cam_btn_fullscreen.setMinimumHeight(45)
        self.cam_btn_fullscreen.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                border: 1px solid #ccc; border-radius: 6px;
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QPushButton:hover { background-color: #d2e9fd; }
            QPushButton:disabled { color: #aaa; background-color: #f5f5f5; }
        """)
        self.cam_btn_fullscreen.setEnabled(False)
        self.cam_btn_fullscreen.clicked.connect(self._show_fullscreen_preview)
        cam_layout.addWidget(self.cam_btn_fullscreen)

        layout.addWidget(cam_group)
        layout.addStretch()

        QTimer.singleShot(100, self._auto_connect_camera)
        return outer

    def _log(self, msg):
        try:
            if self.txt_log:
                self.txt_log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        except RuntimeError:
            pass

    def _log_async(self, msg):
        QTimer.singleShot(0, lambda: self._log(msg))

    def _set_status(self, text, color):
        if self.status_label:
            self.status_label.setText(text)
            self.status_label.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 13px;")

    def _set_cam_status(self, text, color):
        if self.cam_status_label:
            self.cam_status_label.setText(text)
            self.cam_status_label.setStyleSheet(
                f"color: {color}; font-size: 13px;")

    # ==================== 文本发送 ====================
    def _send_text(self):
        if self.capturing:
            QMessageBox.information(None, "提示", "接管期间不能发送文本")
            return
        if CH9329 is None:
            QMessageBox.warning(None, "提示", "键盘驱动加载失败")
            return
        text = self.txt_input.toPlainText()
        if not text.strip():
            QMessageBox.information(None, "提示", "请输入要发送的文本")
            return

        self.btn_send.setEnabled(False)
        self._log("正在发送文本（临时打开串口）...")
        threading.Thread(target=self._do_send_text, args=(text,),
                         daemon=True).start()

    def _do_send_text(self, text):
        kb = None
        try:
            kb = CH9329()
            kb.ensure_capslock_on(auto=True)
            t0 = time.time()
            kb.send_text(text)
            self._log_async(f"✅ 发送完成，耗时 {time.time() - t0:.2f}s")
        except Exception as e:
            self._log_async(f"❌ 发送失败: {e}")
        finally:
            if kb is not None:
                try:
                    kb.close()
                except Exception:
                    pass
            QTimer.singleShot(0, lambda: self.btn_send.setEnabled(True))

    # ==================== 采集卡 ====================
    def _auto_connect_camera(self):
        if self.cam_connected:
            return
        if CaptureCard is None:
            self._set_cam_status("驱动加载失败", "red")
            self.cam_retry_btn.setEnabled(True)
            return
        if self._buffer is None:
            self._set_cam_status("帧缓存加载失败", "red")
            self.cam_retry_btn.setEnabled(True)
            return

        self._set_cam_status("正在连接...", "orange")
        self.cam_retry_btn.setEnabled(False)

        try:
            self.cam = CaptureCard()
            self.cam.open()
            info = self.cam.get_actual()

            self.grabber = FrameGrabber(self.cam, self._buffer)
            self.grabber.frame_ready.connect(self._on_cam_frame)
            self.grabber.error.connect(self._on_cam_error)
            self.grabber.start()

            self.cam_connected = True
            self._set_cam_status("已连接（持续读帧）", "green")
            self.cam_info_label.setText(
                f"  {info['width']}×{info['height']} @ {info['fps']:.1f}FPS")
            self.cam_btn_fullscreen.setEnabled(True)
        except Exception as e:
            self.cam_connected = False
            self.cam = None
            self._set_cam_status(f"连接失败: {e}", "red")
            self.cam_retry_btn.setEnabled(True)

    def _on_cam_frame(self, frame):
        """采集卡每帧回调"""
        self._last_frame = frame

        # 独立全屏预览
        if self._fullscreen_preview is not None:
            try:
                h, w, ch = frame.shape
                qimg = QImage(frame.data, w, h, ch * w,
                              QImage.Format_BGR888)
                self._fullscreen_preview.show_frame(qimg)
            except Exception:
                pass

        # 接管中显示在画面窗口
        if self.capturing and self.display is not None:
            try:
                h, w, ch = frame.shape
                qimg = QImage(frame.data, w, h, ch * w,
                              QImage.Format_BGR888)
                self.display.show_frame(qimg)
            except Exception:
                pass

    def _on_cam_error(self, msg):
        print(f"[采集卡] 错误: {msg}")

    def _show_fullscreen_preview(self):
        if not self.cam_connected:
            QMessageBox.warning(None, "提示", "采集卡未连接")
            return
        if self._fullscreen_preview is not None:
            return

        self._fullscreen_preview = FullscreenPreview()
        self._fullscreen_preview.closed.connect(self._on_preview_closed)
        self._fullscreen_preview.snapshot.connect(self._save_snapshot)
        self._fullscreen_preview.showFullScreen()
        self._fullscreen_preview.raise_()

    def _on_preview_closed(self):
        self._fullscreen_preview = None

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
                self._log(f"✅ 截图已保存: {path}")
        except Exception as e:
            self._log(f"❌ 截图失败: {e}")

    def _stop_camera(self):
        if self._fullscreen_preview is not None:
            try:
                self._fullscreen_preview.close()
            except Exception:
                pass
            self._fullscreen_preview = None
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
        self.cam_connected = False

    # ==================== 接管 ====================
    def start_capture(self):
        if self.capturing:
            return
        if HardwareMouse is None or CH9329 is None:
            QMessageBox.warning(None, "提示", "驱动加载失败")
            return

        try:
            self.rw = max(2, int(self.edit_w.text()))
            self.rh = max(2, int(self.edit_h.text()))
        except ValueError:
            QMessageBox.warning(None, "提示", "分辨率必须是整数")
            return

        # 打开共享串口
        self._log("正在打开串口...")
        try:
            import serial
            port = HardwareMouse._auto_detect_ch340()
            if port is None:
                raise RuntimeError("未找到 CH340 串口")
            self.ser = serial.Serial(port, 115200, timeout=0.05,
                                     write_timeout=0.2)

            try:
                self.mouse = HardwareMouse(
                    port_or_serial=self.ser,
                    screen_w=self.rw, screen_h=self.rh)
            except TypeError:
                self.mouse = HardwareMouse(port_or_serial=self.ser)
            self.mouse.SEND_DELAY = 0.0

            try:
                self.keyboard = CH9329(port_or_serial=self.ser)
            except TypeError:
                self.keyboard = CH9329()

            self._log(f"✅ 串口 {port} 已打开（键鼠共享）")
        except Exception as e:
            self._log(f"❌ 打开串口失败: {e}")
            self._cleanup_serial()
            return

        # 确保采集卡已连接
        if not self.cam_connected:
            self._auto_connect_camera()

        # 鼠标队列线程
        self._tx_queue = []
        self._tx_lock = threading.Lock()
        self._tx_event = threading.Event()
        self._stop_flag = False
        self._tx_thread = threading.Thread(
            target=self._sender_loop, daemon=True)
        self._tx_thread.start()

        # 计算中央 16:9 区域
        screen = QApplication.instance().primaryScreen()
        sw = screen.size().width()
        sh = screen.size().height()
        ar = self.rw / self.rh
        if sw / sh >= ar:
            cw, ch = int(sh * ar), sh
        else:
            cw, ch = sw, int(sw / ar)
        self._cx = (sw - cw) // 2
        self._cy = (sh - ch) // 2
        self._cw, self._ch = cw, ch

        # ★ 1. 先创建采集卡画面窗口（下层）
        self.display = CaptureDisplayWindow()
        self.display.setGeometry(0, 0, sw, sh)
        self.display.showFullScreen()

        # ★ 2. 再创建透明鼠标覆盖层（上层，接收事件）
        self.overlay = MouseOverlay(self.rw, self.rh,
                                    (self._cx, self._cy, cw, ch))
        self.overlay.setGeometry(0, 0, sw, sh)
        self.overlay.signal_move.connect(self._on_move)
        self.overlay.signal_press.connect(self._on_press)
        self.overlay.signal_release.connect(self._on_release)
        self.overlay.signal_wheel.connect(self._on_wheel)
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.overlay.setFocus()

        if IS_WIN:
            lock_cursor(self._cx, self._cy, cw, ch)

        # 键盘钩子
        self._mod_state = 0
        self._pressed_keys.clear()
        self._exit_requested = False
        self.hook = KeyboardHook(self._on_key_event)
        if self.hook.install():
            self._log("✅ 键盘钩子已安装")
        else:
            self._log("⚠ 键盘钩子安装失败")

        # 主线程定时器
        self._tick_count = 0
        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(50)

        self.capturing = True
        self.current_button = None
        self.btn_start.setEnabled(False)
        self._set_status("接管中", "green")
        self._log(f"✅ 接管已开启：目标机 {self.rw}×{self.rh}")
        self._log("   退出：Fn/Ctrl/Shift + Delete  或  Esc")
        self._log("   【应急】Ctrl+Alt+Del 打开任务管理器")

        self._submit("move", self.rw // 2, self.rh // 2)

    def stop_capture(self):
        if not self.capturing:
            return
        self.capturing = False

        # 1) 解锁鼠标（最高优先级）
        if IS_WIN:
            unlock_cursor()

        # 2) 停定时器
        if self._tick_timer is not None:
            try:
                self._tick_timer.stop()
            except Exception:
                pass
            self._tick_timer = None

        # 3) 卸载钩子
        if self.hook is not None:
            try:
                self.hook.uninstall()
            except Exception:
                pass
            self.hook = None

        # 4) 关闭鼠标覆盖层（先关上层）
        if self.overlay is not None:
            for sig in (self.overlay.signal_move, self.overlay.signal_press,
                        self.overlay.signal_release, self.overlay.signal_wheel):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            try:
                self.overlay.close()
                self.overlay.deleteLater()
            except Exception:
                pass
            self.overlay = None

        # 5) 关闭采集卡画面窗口
        if self.display is not None:
            try:
                self.display.close()
                self.display.deleteLater()
            except Exception:
                pass
            self.display = None

        # 6) 停鼠标发送线程
        self._stop_flag = True
        self._tx_event.set()
        if self._tx_thread is not None and self._tx_thread.is_alive():
            self._tx_thread.join(timeout=1.0)
        self._tx_thread = None

        self._cleanup_serial()
        self.current_button = None
        self.btn_start.setEnabled(True)
        self._set_status("未接管", "gray")
        if self.coord_label:
            try:
                self.coord_label.setText("目标坐标: -")
            except RuntimeError:
                pass
        self._log("✅ 接管已释放，本机鼠标键盘已恢复")

    # ==================== 主线程定时器 ====================
    def _on_tick(self):
        if not self.capturing:
            return

        # 1. 检查退出请求（钩子线程设置）
        if self._exit_requested:
            self._exit_requested = False
            self._log("检测到退出热键，停止接管")
            self.stop_capture()
            return

        # 2. 每 10 次（500ms）保持覆盖层置顶
        self._tick_count += 1
        if self._tick_count >= 10:
            self._tick_count = 0
            if self.overlay is not None:
                try:
                    self.overlay.raise_()
                except Exception:
                    pass

        # 3. 坐标刷新
        if self._pending_ui is not None:
            tx, ty = self._pending_ui
            self._pending_ui = None
            try:
                if self.coord_label:
                    self.coord_label.setText(f"目标坐标: ({tx}, {ty})")
            except RuntimeError:
                pass

    # ==================== 键盘钩子回调 ====================
    def _on_key_event(self, vk, is_down):
        """
        钩子线程回调：只做轻量操作。
        退出检测直接设置标志，主线程轮询触发。
        """
        # 1. 退出热键检测
        if is_down:
            if vk == VK_ESCAPE:
                self._exit_requested = True
                return True
            if vk == VK_DELETE:
                m = self._mod_state
                if (m & 0x01) or (m & 0x10):  # Ctrl
                    self._exit_requested = True
                    return True
                if (m & 0x02) or (m & 0x20):  # Shift
                    self._exit_requested = True
                    return True
                if (m & 0x04) or (m & 0x40):  # Alt
                    self._exit_requested = True
                    return True

        # Fn
        if vk == VK_FN and is_down:
            return True

        # 修饰键
        if vk in VK_MODIFIER:
            bit = VK_MODIFIER[vk]
            if is_down:
                self._mod_state |= bit
            else:
                self._mod_state &= ~bit
            self._send_kb_state()
            return True

        # 普通键
        hid = VK_TO_HID.get(vk)
        if hid is None:
            return False

        if is_down:
            if vk in self._pressed_keys:
                return True
            self._pressed_keys.add(vk)
        else:
            self._pressed_keys.discard(vk)
        self._send_kb_state()
        return True

    def _send_kb_state(self):
        kb = self.keyboard
        if kb is None:
            return
        keys = list(self._pressed_keys)[:6]
        key_codes = [VK_TO_HID[vk] for vk in keys if vk in VK_TO_HID]
        try:
            with self._kb_send_lock:
                kb._send_cmd(self._mod_state, key_codes)
        except Exception:
            pass

    # ==================== 鼠标队列 ====================
    def _submit(self, kind, *args):
        with self._tx_lock:
            if kind == "move":
                self._tx_queue = [it for it in self._tx_queue if it[0] != "move"]
            self._tx_queue.append((kind, args))
        self._tx_event.set()

    def _sender_loop(self):
        current_btn = None
        while not self._stop_flag:
            with self._tx_lock:
                batch = self._tx_queue
                self._tx_queue = []
            if not batch:
                self._tx_event.wait(0.1)
                self._tx_event.clear()
                continue
            m = self.mouse
            if m is None:
                continue
            for kind, args in batch:
                try:
                    if kind == "move":
                        if current_btn:
                            m.press(args[0], args[1], current_btn)
                        else:
                            m.move(args[0], args[1])
                    elif kind == "press":
                        current_btn = args[2]
                        m.press(args[0], args[1], args[2])
                    elif kind == "release":
                        current_btn = None
                        m.release()
                    elif kind == "scroll":
                        m.scroll(args[0], args[1], args[2])
                except Exception:
                    pass

    def _on_move(self, tx, ty):
        self._pending_ui = (tx, ty)
        if self.capturing:
            self._submit("move", tx, ty)

    def _on_press(self, tx, ty, btn):
        self.current_button = btn
        self._submit("press", tx, ty, btn)

    def _on_release(self, tx, ty, btn):
        self.current_button = None
        self._submit("release")

    def _on_wheel(self, tx, ty, amount):
        self._submit("scroll", tx, ty, amount)

    # ==================== 清理 ====================
    def _cleanup_serial(self):
        if self.mouse is not None:
            try:
                self.mouse.release()
            except Exception:
                pass
        if self.keyboard is not None:
            try:
                with self._kb_send_lock:
                    self.keyboard._send_cmd(0x00, [])
            except Exception:
                pass
        for d in (self.mouse, self.keyboard):
            if d is not None:
                try:
                    d.close()
                except Exception:
                    pass
        self.mouse = None
        self.keyboard = None
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def shutdown(self):
        try:
            self.stop_capture()
        except Exception:
            pass
        try:
            self._stop_camera()
        except Exception:
            pass

    def closeEvent(self, e):
        self.shutdown()
        e.accept()