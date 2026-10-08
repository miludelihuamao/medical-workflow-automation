# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 硬件管理器】

用途：
    全局单例，负责统一管理键鼠串口和采集卡。
    主界面启动时调用一次 connect_all()，
    之后所有需要硬件的模块都从这里取，避免重复打开串口。

职责：
    1. 连接/断开 CH9329 键鼠（共享一个串口）
    2. 连接/断开采集卡（默认不读帧，按需读）
    3. 提供截图函数 screenshot_func() 给工作流引擎
    4. 通过 status_changed 信号汇报连接结果

★ 闲置优化：
    连接采集卡后不再自动启动读帧线程，
    只有调用 acquire_frames() 时才启动。
    不再需要时调用 release_frames()，引用计数归零时自动停。
================================================================
"""
import os
import time
import threading
import importlib.util

from PyQt5.QtCore import QObject, pyqtSignal, QThread


# ============================================================
# 加载 硬件 包下的中文驱动
# ============================================================
HARDWARE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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
    print(f"[HardwareManager] 鼠标驱动加载失败: {e}")

try:
    CH9329 = _load_module("CH9329键盘", "CH9329键盘.py").CH9329
except Exception as e:
    CH9329 = None
    print(f"[HardwareManager] 键盘驱动加载失败: {e}")

try:
    _cam_mod = _load_module("采集卡驱动", "采集卡.py")
    CaptureCard = _cam_mod.CaptureCard
except Exception as e:
    CaptureCard = None
    print(f"[HardwareManager] 采集卡驱动加载失败: {e}")

try:
    from 硬件 import FrameBuffer
except Exception as e:
    FrameBuffer = None
    print(f"[HardwareManager] 帧缓存加载失败: {e}")


# ============================================================
# 采集卡读帧线程
# ============================================================
class _FrameGrabber(QThread):
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
            time.sleep(0.003)

    def stop(self):
        self._run = False
        self.wait(1500)


# ============================================================
# 硬件管理器
# ============================================================
class HardwareManager(QObject):
    _instance = None

    # 状态信号
    status_changed = pyqtSignal(str, bool, str)   # (设备名, 是否成功, 消息)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HardwareManager()
        return cls._instance

    def __init__(self):
        super().__init__()

        # 键鼠
        self.ser = None
        self.mouse = None
        self.keyboard = None
        self.hid_connected = False

        # 采集卡
        self.cam = None
        self.grabber = None
        self.cam_connected = False

        # 锁
        self._lock = threading.Lock()
        self._cam_lock = threading.Lock()       # ★ 保护 cam.read()
        self._count_lock = threading.Lock()     # ★ 保护引用计数

        # ★ 读帧控制
        self._grabber_running = False
        self._consumer_count = 0

    # ==================== 键鼠 ====================
    def connect_hid(self, screen_w=1920, screen_h=1080):
        """连接键鼠（同步）"""
        with self._lock:
            if self.hid_connected:
                return True

            if HardwareMouse is None or CH9329 is None:
                self.status_changed.emit("键鼠", False, "驱动加载失败")
                return False

            try:
                import serial
                port = HardwareMouse._auto_detect_ch340()
                if port is None:
                    raise RuntimeError("未找到 CH340 串口设备")

                self.ser = serial.Serial(port, 115200, timeout=0.05,
                                         write_timeout=0.2)

                try:
                    self.mouse = HardwareMouse(
                        port_or_serial=self.ser,
                        screen_w=screen_w, screen_h=screen_h)
                except TypeError:
                    self.mouse = HardwareMouse(port_or_serial=self.ser)
                self.mouse.SEND_DELAY = 0.0

                try:
                    self.keyboard = CH9329(port_or_serial=self.ser)
                except TypeError:
                    self.keyboard = CH9329()

                self.hid_connected = True
                self.status_changed.emit("键鼠", True, f"串口 {port} 已连接")
                return True
            except Exception as e:
                self._cleanup_hid()
                self.status_changed.emit("键鼠", False, str(e))
                return False

    def _cleanup_hid(self):
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
        self.hid_connected = False

    def disconnect_hid(self):
        with self._lock:
            self._cleanup_hid()

    # ==================== 采集卡 ====================
    def connect_camera(self):
        """连接采集卡（同步）——只打开设备，不启动读帧线程"""
        with self._lock:
            if self.cam_connected:
                return True

            if CaptureCard is None:
                self.status_changed.emit("采集卡", False, "驱动加载失败")
                return False
            if FrameBuffer is None:
                self.status_changed.emit("采集卡", False, "帧缓存不可用")
                return False

            try:
                self.cam = CaptureCard()
                self.cam.open()
                info = self.cam.get_actual()

                # ★ 不再自动启动 _FrameGrabber

                self.cam_connected = True
                msg = (f"{info['width']}×{info['height']} "
                       f"@{info['fps']:.1f}FPS")
                self.status_changed.emit("采集卡", True, msg)
                return True
            except Exception as e:
                self._cleanup_camera()
                self.status_changed.emit("采集卡", False, str(e))
                return False

    def _cleanup_camera(self):
        if self.grabber is not None:
            try:
                self.grabber.stop()
            except Exception:
                pass
            self.grabber = None
        self._grabber_running = False       # ★ 同步复位标记
        if self.cam is not None:
            try:
                self.cam.release()
            except Exception:
                pass
            self.cam = None
        self.cam_connected = False

    def disconnect_camera(self):
        with self._lock:
            self._cleanup_camera()

    # ==================== ★ 读帧控制 ====================
    def start_frame_grabber(self):
        """启动持续读帧线程（幂等）"""
        if self._grabber_running:
            return
        if self.cam is None or FrameBuffer is None:
            return
        self.grabber = _FrameGrabber(
            self.cam, FrameBuffer.get_instance())
        self.grabber.start()
        self._grabber_running = True

    def stop_frame_grabber(self):
        """停止持续读帧线程"""
        if not self._grabber_running:
            return
        if self.grabber is not None:
            try:
                self.grabber.stop()
            except Exception:
                pass
            self.grabber = None
        self._grabber_running = False

    def acquire_frames(self):
        """需要持续画面时调用（引用计数 +1）"""
        with self._count_lock:
            self._consumer_count += 1
        self.start_frame_grabber()

    def release_frames(self):
        """不再需要持续画面时调用（引用计数 -1，归零则停）"""
        with self._count_lock:
            self._consumer_count -= 1
            if self._consumer_count <= 0:
                self._consumer_count = 0
                should_stop = True
            else:
                should_stop = False
        if should_stop:
            self.stop_frame_grabber()

    # ==================== 全局 ====================
    def connect_all(self, screen_w=1920, screen_h=1080):
        """按顺序连接全部硬件（同步）"""
        self.connect_camera()
        self.connect_hid(screen_w, screen_h)

    def disconnect_all(self):
        self.disconnect_hid()
        self.disconnect_camera()

    # ==================== 截图函数 ====================
    def screenshot_func(self):
        """
        供引擎使用：返回采集卡最新帧。
        - 有持续读帧线程时：用缓存
        - 没有时：按需读一帧
        """
        # 优先用缓存
        if self._grabber_running and FrameBuffer is not None:
            try:
                frame, _age = FrameBuffer.get_instance().get_frame()
                if frame is not None:
                    return frame
            except Exception:
                pass

        # 按需读一帧
        if self.cam is None:
            return None
        with self._cam_lock:
            try:
                return self.cam.read()
            except Exception:
                return None