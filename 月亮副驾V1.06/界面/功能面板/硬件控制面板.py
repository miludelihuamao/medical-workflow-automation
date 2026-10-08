# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 功能面板 / 硬件控制面板】

用途：
    硬件控制面板（与"键鼠接管面板"功能相近，但设计不同）。
    主要特性：
      - 键盘/鼠标共用同一 CH9329 串口
      - 键盘活动 150ms 内丢弃鼠标移动（打字时鼠标不乱动）
      - 鼠标点击/滚轮/释放永不被丢弃
      - 键盘钩子把本机按键实时转发到目标机，本机不响应
      - 文本注入：接管时用共享串口，非接管时临时开串口
      - 退出：Ctrl/Shift/Alt/Fn + Delete（Esc 不再退出，改为转发到目标机）

关键设计：
    - 钩子回调只更新 Python 内存变量，绝不写串口、绝不碰 Qt
    - 串口写入由独立线程完成
    - 退出检测走主线程定时器 + 内存标志，双保险
    - 工作线程 → 主线程的通知通过常驻定时器消费

被谁使用：
    - 界面/主窗口.py            （作为"开发面板"的一个标签页）

依赖：
    - 界面/功能面板/面板基类.py
    - 硬件/CH9329鼠标.py
    - 硬件/CH9329键盘.py
================================================================
"""
import sys
import os
import ctypes
import importlib.util
import threading
import time

# 把项目根目录（月亮副驾/）加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QLineEdit, QTextEdit,
                             QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from 界面.功能面板.面板基类 import BaseModule

try:
    import serial
except ImportError:
    serial = None


# ==================== 动态加载驱动 ====================
def _load_driver(file_name, class_name):
    # 月亮副驾/硬件/
    hardware_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "硬件")
    driver_path = os.path.join(hardware_dir, file_name)
    if not os.path.exists(driver_path):
        raise FileNotFoundError(f"驱动文件不存在: {driver_path}")
    spec = importlib.util.spec_from_file_location(class_name, driver_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


try:
    HardwareMouse = _load_driver("CH9329鼠标.py", "HardwareMouse")
except Exception as e:
    HardwareMouse = None
    print(f"鼠标驱动加载失败: {e}")

try:
    CH9329 = _load_driver("CH9329键盘.py", "CH9329")
except Exception as e:
    CH9329 = None
    print(f"键盘驱动加载失败: {e}")


# ==================== Windows API ====================
IS_WIN = hasattr(ctypes, "windll")
if IS_WIN:
    user32 = ctypes.windll.user32
    VK_DELETE = 0x2E
    VK_FN     = 0xFF
    VK_LSHIFT, VK_RSHIFT     = 0xA0, 0xA1
    VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
    VK_LMENU, VK_RMENU       = 0xA4, 0xA5
else:
    user32 = None

# 退出热键要检测的修饰键
EXIT_MODIFIERS = (VK_LCONTROL, VK_RCONTROL,
                  VK_LSHIFT, VK_RSHIFT,
                  VK_LMENU, VK_RMENU,
                  VK_FN) if IS_WIN else ()


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


# ==================== VK → CH9329 HID 键码表 ====================
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
    0x5B: 0x08, 0x5C: 0x80,
} if IS_WIN else {}


# ==================== 串口总线 ====================
class SerialBus:
    """键盘优先的共享串口封装：加锁 + 记录键盘活动时间"""
    KB_ACTIVE_WINDOW = 0.15

    def __init__(self, ser):
        self._ser = ser
        self._lock = threading.Lock()
        self._last_kb_activity = 0.0

    def write_kb(self, data):
        with self._lock:
            n = self._ser.write(data)
        self._last_kb_activity = time.time()
        return n

    def write_mouse(self, data):
        with self._lock:
            return self._ser.write(data)

    def kb_active_age(self):
        return time.time() - self._last_kb_activity

    def __getattr__(self, name):
        return getattr(self._ser, name)


class _SerialView:
    """给驱动的串口视图，write 走 bus 的加锁通道"""
    def __init__(self, bus, kind):
        self._bus = bus
        self._kind = kind

    def write(self, data):
        if self._kind == "kb":
            return self._bus.write_kb(data)
        return self._bus.write_mouse(data)

    def __getattr__(self, name):
        return getattr(self._bus, name)


# ==================== 键盘钩子 ====================
class KeyboardHook:
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
    WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105

    def __init__(self, callback):
        self.callback = callback
        self.hook_id = None
        self._proc = None

    def install(self):
        if not IS_WIN:
            return False
        try:
            self._proc = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_void_p)(self._hook_proc)
            self.hook_id = user32.SetWindowsHookExW(
                self.WH_KEYBOARD_LL, self._proc, None, 0)
            return bool(self.hook_id)
        except Exception as e:
            print(f"键盘钩子安装失败: {e}")
            return False

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


# ==================== 全屏透明覆盖层 ====================
class MouseOverlay(QWidget):
    signal_move    = pyqtSignal(int, int)
    signal_press   = pyqtSignal(int, int, str)
    signal_release = pyqtSignal(int, int, str)
    signal_wheel   = pyqtSignal(int, int, int)

    def __init__(self, tw, th, region, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint |
                            Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowOpacity(0.1)
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


# ==================== 主模块 ====================
class HardwareModule(BaseModule):
    name = "硬件控制"

    def __init__(self):
        # ---- 串口 / 驱动 ----
        self.ser = None
        self.bus = None
        self.mouse = None
        self.keyboard = None
        self.capturing = False
        self.hook = None

        # ---- 覆盖层 ----
        self.overlay = None
        self._widget = None

        # ---- 鼠标事件队列 ----
        self._mouse_queue = []
        self._mouse_lock = threading.Lock()
        self._mouse_event = threading.Event()
        self._mouse_thread = None
        self.current_button = None
        self._pending_ui = None

        # ---- 键盘状态 ----
        self._mod_state = 0
        self._pressed_keys = set()
        self._kb_dirty = False
        self._kb_event = threading.Event()
        self._kb_send_lock = threading.Lock()
        self._kb_thread = None

        # ---- 退出 / 线程控制 ----
        self._exit_requested = False
        self._stop_flag = False

        # ---- 文本注入 ----
        self.text_injecting = False
        self.sending = False

        # ---- 工作线程 → 主线程通知（不碰 Qt）----
        self._pending_logs = []
        self._pending_logs_lock = threading.Lock()
        self._send_done_pending = False

        # ---- 分辨率 ----
        self.rw, self.rh = 1920, 1080
        self._cx = self._cy = 0
        self._cw = self._ch = 1920

        # ---- 定时器 ----
        self.poll_timer = None
        self.raise_timer = None
        self._coord_timer = None
        self._idle_timer = None

        # ---- UI ----
        self.edit_w = None
        self.edit_h = None
        self.btn_start = None
        self.btn_send = None
        self.txt_input = None
        self.coord_label = None
        self.txt_log = None

    # ==================== UI ====================
    def create_widget(self) -> QWidget:
        widget = QWidget()
        self._widget = widget
        ml = QVBoxLayout(widget)

        tip = QLabel("点「开始接管」后：\n"
                     "  • 鼠标位置映射到目标机\n"
                     "  • 键盘按键实时转发（本机不响应）\n"
                     "  • 键盘打字时鼠标移动自动让路\n"
                     "退出：Ctrl/Shift/Alt/Fn + Delete\n"
                     "文本注入：任何时刻都可使用")
        tip.setStyleSheet("color: #555; font-size: 11px;")
        tip.setWordWrap(True)
        ml.addWidget(tip)

        # ---------- 文本注入 ----------
        ig = QGroupBox("文本注入")
        il = QVBoxLayout(ig)
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("输入要注入到目标机的文本（支持中文）...")
        self.txt_input.setMaximumHeight(80)
        il.addWidget(self.txt_input)
        self.btn_send = QPushButton("注入文本")
        self.btn_send.clicked.connect(self._send_text)
        il.addWidget(self.btn_send)
        ml.addWidget(ig)

        # ---------- 目标机设置 ----------
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
        ml.addWidget(cg)

        # ---------- 接管 ----------
        tg = QGroupBox("接管控制")
        tl = QVBoxLayout(tg)
        row = QHBoxLayout()
        self.btn_start = QPushButton("开始接管")
        self.btn_start.clicked.connect(self.start_capture)
        row.addWidget(self.btn_start)
        self.coord_label = QLabel("目标坐标: -")
        self.coord_label.setStyleSheet("color: #666;")
        row.addWidget(self.coord_label)
        row.addStretch()
        tl.addLayout(row)
        ml.addWidget(tg)

        # ---------- 日志 ----------
        lg = QGroupBox("操作日志")
        ll = QVBoxLayout(lg)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        ll.addWidget(self.txt_log)
        ml.addWidget(lg)

        # ★ 常驻定时器：主线程里消费工作线程的通知
        self._idle_timer = QTimer()
        self._idle_timer.timeout.connect(self._on_idle_tick)
        self._idle_timer.start(100)

        return widget

    def _log(self, msg):
        try:
            if self.txt_log:
                self.txt_log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        except RuntimeError:
            pass

    def _log_async(self, msg):
        """工作线程调用：只入队，不碰 Qt"""
        with self._pending_logs_lock:
            self._pending_logs.append(msg)

    def _on_idle_tick(self):
        """主线程定时器：处理工作线程的通知"""
        # 1) 挂起的日志
        with self._pending_logs_lock:
            logs = self._pending_logs
            self._pending_logs = []
        for msg in logs:
            self._log(msg)

        # 2) 文本注入完成标志
        if self._send_done_pending:
            self._send_done_pending = False
            self.text_injecting = False
            self.sending = False
            if self.btn_send:
                self.btn_send.setEnabled(True)
            if self.btn_start:
                self.btn_start.setEnabled(True)

    # ==================== 文本注入 ====================
    def _send_text(self):
        if self.sending:
            return
        if CH9329 is None:
            QMessageBox.warning(None, "提示", "键盘驱动加载失败")
            return
        text = self.txt_input.toPlainText()
        if not text.strip():
            QMessageBox.information(None, "提示", "请输入要注入的文本")
            return

        self.sending = True
        self.btn_send.setEnabled(False)
        self._log(f"开始注入文本（{len(text)} 字符）...")
        threading.Thread(target=self._do_send_text,
                         args=(text,), daemon=True).start()

    def _do_send_text(self, text):
        """工作线程：不碰 Qt，只更新 Python 变量"""
        kb = None
        standalone = False
        self.text_injecting = True
        try:
            if self.capturing and self.keyboard is not None:
                kb = self.keyboard
                self._log_async("使用共享串口注入文本...")
            else:
                kb = CH9329()
                standalone = True
                self._log_async("使用独立串口注入文本...")

            kb.ensure_capslock_on(auto=True)
            t0 = time.time()
            with self._kb_send_lock:
                kb.send_text(text)
            self._log_async(f"✅ 文本注入完成，耗时 {time.time() - t0:.2f}s")
        except Exception as e:
            self._log_async(f"❌ 注入失败: {e}")
        finally:
            if standalone and kb is not None:
                try:
                    kb.close()
                except Exception:
                    pass
            self._send_done_pending = True

    # ==================== 接管 ====================
    def start_capture(self):
        if self.capturing:
            return
        if self.sending:
            QMessageBox.information(None, "提示", "正在注入文本，请稍候...")
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
            port = HardwareMouse._auto_detect_ch340()
            if port is None:
                raise RuntimeError("未找到 CH340 串口")
            self.ser = serial.Serial(port, 115200, timeout=0.05,
                                     write_timeout=0.2)
            self.bus = SerialBus(self.ser)
            self._log(f"✅ 串口 {port} 已打开")
        except Exception as e:
            QMessageBox.critical(None, "打开串口失败", f"错误：{e}")
            self._cleanup()
            return

        # 用视图创建驱动
        try:
            self.mouse = HardwareMouse(
                port_or_serial=_SerialView(self.bus, "mouse"),
                screen_w=self.rw, screen_h=self.rh)
            self.mouse.SEND_DELAY = 0.0

            self.keyboard = CH9329(
                port_or_serial=_SerialView(self.bus, "kb"))
            self._log("✅ 键鼠驱动已初始化（共享串口）")
        except Exception as e:
            QMessageBox.critical(None, "驱动初始化失败", f"错误：{e}")
            self._cleanup()
            return

        # 重置状态
        self._mouse_queue = []
        self._mouse_lock = threading.Lock()
        self._mouse_event = threading.Event()
        self._mod_state = 0
        self._pressed_keys = set()
        self._kb_dirty = False
        self._kb_event = threading.Event()
        self._exit_requested = False
        self._stop_flag = False

        # 启动键鼠发送线程
        self._mouse_thread = threading.Thread(
            target=self._mouse_sender_loop, daemon=True)
        self._mouse_thread.start()

        self._kb_thread = threading.Thread(
            target=self._kb_sender_loop, daemon=True)
        self._kb_thread.start()

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

        # 覆盖层
        self.overlay = MouseOverlay(self.rw, self.rh,
                                    (self._cx, self._cy, cw, ch),
                                    parent=self._widget)
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
            # 清掉残留的键状态
            user32.GetAsyncKeyState(VK_DELETE)

        # 安装键盘钩子
        self.hook = KeyboardHook(self._on_key_event)
        if self.hook.install():
            self._log("✅ 键盘钩子已安装")
        else:
            self._log("⚠ 键盘钩子安装失败（键盘不会转发）")

        # 定时器
        self.raise_timer = QTimer()
        self.raise_timer.timeout.connect(self._keep_overlay_top)
        self.raise_timer.start(500)

        self._coord_timer = QTimer()
        self._coord_timer.timeout.connect(self._flush_coord_ui)
        self._coord_timer.start(100)

        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._poll_state)
        self.poll_timer.start(30)

        self.capturing = True
        self.current_button = None
        self.btn_start.setEnabled(False)
        self._log(f"接管已开启：目标机 {self.rw}×{self.rh}")
        self._log("退出方式：Ctrl/Shift/Alt/Fn + Delete")

        self._submit("move", self.rw // 2, self.rh // 2)

    def stop_capture(self):
        if not self.capturing:
            return
        self.capturing = False

        # 立刻解锁光标
        if IS_WIN:
            unlock_cursor()

        # 卸载键盘钩子
        if self.hook is not None:
            self.hook.uninstall()
            self.hook = None

        # 停定时器
        for t in (self.poll_timer, self.raise_timer, self._coord_timer):
            if t is not None:
                try:
                    t.stop()
                except Exception:
                    pass
        self.poll_timer = None
        self.raise_timer = None
        self._coord_timer = None

        # 关覆盖层
        if self.overlay is not None:
            for sig in (self.overlay.signal_move, self.overlay.signal_press,
                        self.overlay.signal_release, self.overlay.signal_wheel):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            try:
                self.overlay.hide()
                self.overlay.deleteLater()
            except Exception:
                pass
            self.overlay = None

        # 停线程
        self._stop_flag = True
        self._mouse_event.set()
        self._kb_event.set()
        for th in (self._mouse_thread, self._kb_thread):
            if th is not None and th.is_alive():
                th.join(timeout=1.0)
        self._mouse_thread = None
        self._kb_thread = None

        self._cleanup()

        self.current_button = None
        self._exit_requested = False
        if self.btn_start:
            self.btn_start.setEnabled(True)
        if self.coord_label:
            try:
                self.coord_label.setText("目标坐标: -")
            except RuntimeError:
                pass
        self._log("接管已释放，本机鼠标键盘已恢复")

    def _cleanup(self):
        if self.mouse is not None:
            try:
                self.mouse.release()
            except Exception:
                pass
            try:
                self.mouse.close()
            except Exception:
                pass
            self.mouse = None
        if self.keyboard is not None:
            try:
                with self._kb_send_lock:
                    self.keyboard._send_cmd(0x00, [])
            except Exception:
                pass
            try:
                self.keyboard.close()
            except Exception:
                pass
            self.keyboard = None
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.bus = None

    def _keep_overlay_top(self):
        if self.overlay is not None:
            try:
                self.overlay.raise_()
            except Exception:
                pass

    # ==================== 键盘钩子回调 ====================
    def _on_key_event(self, vk, is_down):
        """
        运行在系统钩子线程里。只做：
          1. 检测退出热键 → 设标志
          2. 更新 Python 内存状态
          3. 设 kb_dirty 标志，通知后台线程发串口
        绝不：写串口、调用 Qt、sleep、IO。
        """
        try:
            if not self.capturing:
                return False

            # 退出热键：Delete + 任意修饰键
            if vk == VK_DELETE and is_down:
                if self._mod_state != 0:
                    self._exit_requested = True
                    return True

            # 文本注入中：吞掉所有按键，避免干扰
            if self.text_injecting:
                return True

            if self.keyboard is None:
                return False

            changed = False
            if vk in VK_MODIFIER:
                bit = VK_MODIFIER[vk]
                if is_down:
                    if not (self._mod_state & bit):
                        self._mod_state |= bit
                        changed = True
                else:
                    if self._mod_state & bit:
                        self._mod_state &= ~bit
                        changed = True
            elif vk in VK_TO_HID:
                if is_down:
                    if vk not in self._pressed_keys:
                        self._pressed_keys.add(vk)
                        changed = True
                else:
                    if vk in self._pressed_keys:
                        self._pressed_keys.discard(vk)
                        changed = True
            else:
                return False

            if changed:
                self._kb_dirty = True
                self._kb_event.set()
            return True
        except Exception:
            return False

    # ==================== 键盘发送线程 ====================
    def _kb_sender_loop(self):
        while not self._stop_flag:
            self._kb_event.wait(0.1)
            self._kb_event.clear()
            if self._stop_flag:
                break
            if not self._kb_dirty:
                continue
            self._kb_dirty = False

            kb = self.keyboard
            if kb is None:
                continue
            try:
                mod = self._mod_state
                keys = list(self._pressed_keys)[:6]
                key_codes = [VK_TO_HID[vk] for vk in keys if vk in VK_TO_HID]
                with self._kb_send_lock:
                    kb._send_cmd(mod, key_codes)
            except Exception:
                pass

    # ==================== 鼠标发送线程 ====================
    def _submit(self, kind, *args):
        with self._mouse_lock:
            if kind == "move":
                self._mouse_queue = [it for it in self._mouse_queue
                                     if it[0] != "move"]
            self._mouse_queue.append((kind, args))
        self._mouse_event.set()

    def _mouse_sender_loop(self):
        current_btn = None
        while not self._stop_flag:
            with self._mouse_lock:
                batch = self._mouse_queue
                self._mouse_queue = []
            if not batch:
                self._mouse_event.wait(0.1)
                self._mouse_event.clear()
                continue
            m = self.mouse
            if m is None:
                continue
            for kind, args in batch:
                try:
                    if kind == "move":
                        # 键盘活动 / 文本注入期间丢弃鼠标移动
                        if self.text_injecting:
                            continue
                        if self.bus is not None and \
                           self.bus.kb_active_age() < SerialBus.KB_ACTIVE_WINDOW:
                            continue
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

    # ==================== 鼠标事件 ====================
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

    def _flush_coord_ui(self):
        if self._pending_ui is None:
            return
        tx, ty = self._pending_ui
        self._pending_ui = None
        try:
            if self.coord_label:
                self.coord_label.setText(f"目标坐标: ({tx}, {ty})")
        except RuntimeError:
            pass

    # ==================== 退出检测（主线程轮询，双保险）====================
    def _poll_state(self):
        if not self.capturing:
            return

        # ① 钩子线程设置的退出标志
        if self._exit_requested:
            self._exit_requested = False
            self._log("检测到退出请求（来自键盘钩子）")
            self.stop_capture()
            return

        if not IS_WIN:
            return

        # ② 备份：Delete + 修饰键（钩子失效也能退）
        if user32.GetAsyncKeyState(VK_DELETE) & 0x8000:
            for vk in EXIT_MODIFIERS:
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    self._log("检测到修饰键+Delete（轮询备份）")
                    self.stop_capture()
                    return

    # ==================== 清理 ====================
    def closeEvent(self, event):
        if self.sending:
            t0 = time.time()
            while self.sending and time.time() - t0 < 3:
                time.sleep(0.05)
        try:
            self.stop_capture()
        except Exception:
            pass
        event.accept()