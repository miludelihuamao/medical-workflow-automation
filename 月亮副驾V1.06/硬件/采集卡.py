# camera_driver.py
import cv2
import os
import sys
from datetime import datetime

# ==================== 可能需要更改的参数 ====================
DEVICE_INDEX = 0
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_FPS = 60
FOURCC = 'RGB3'
FLIP_MODE = 0
WINDOW_NAME = '采集卡预览'

# 采集卡在 Windows“照相机”目录下的名称
DEVICE_NAME = "UGREEN 65518"
DEVICE_NAME_KEYWORDS = ("UGREEN", "65518")
# ==========================================================


class CaptureOpenError(Exception):
    pass


class CaptureConfigError(Exception):
    pass


def detect_capture_device():
    """
    自动探测 DirectShow 视频设备，并尝试匹配 UGREEN 65518。
    返回 (matched_index, matched_name)，未匹配则返回 (None, None)。
    """
    devices = []

    try:
        from pygrabber.dshow_graph import FilterGraph
        devices = FilterGraph().get_input_devices()
    except Exception as e:
        print(f"⚠️ 无法使用 pygrabber 自动探测设备: {e}")
        print("   如需按名称探测，请安装: pip install pygrabber")

    print("=" * 60)
    print("DirectShow 视频设备探测结果：")
    if devices:
        for i, name in enumerate(devices):
            print(f"  [{i}] {name}")
    else:
        print("  (未探测到设备列表)")

    matched_index = None
    matched_name = None

    # 优先完整匹配 DEVICE_NAME
    for i, name in enumerate(devices):
        if DEVICE_NAME.lower() in name.lower():
            matched_index = i
            matched_name = name
            break

    # 再按关键词匹配
    if matched_index is None:
        for i, name in enumerate(devices):
            if all(k.lower() in name.lower() for k in DEVICE_NAME_KEYWORDS):
                matched_index = i
                matched_name = name
                break

    if matched_index is not None:
        print(f"✅ 匹配到采集卡: [{matched_index}] {matched_name}")
    else:
        print(f"⚠️ 未找到名称包含 '{DEVICE_NAME}' 的采集卡，将回退到 DEVICE_INDEX={DEVICE_INDEX}")

    print("=" * 60)
    return matched_index, matched_name


class CaptureCard:
    """
    采集卡驱动接口。
    支持两种使用方式：

    1. 只采集，不开窗口：
        with CaptureCard() as cam:
            while True:
                frame = cam.read()
                if frame is None:
                    break
                # 处理 frame

    2. GUI 预览：
        由 gui_preview.py 调用。
    """

    def __init__(
        self,
        device_index=None,
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        fps=TARGET_FPS,
        fourcc=FOURCC,
        flip_mode=FLIP_MODE,
    ):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.fourcc = fourcc
        self.flip_mode = flip_mode

        self.cap = None
        self.actual_w = None
        self.actual_h = None
        self.actual_fps = None

    def open(self):
        detected_index, detected_name = detect_capture_device()

        if self.device_index is None:
            if detected_index is not None:
                self.device_index = detected_index
            else:
                self.device_index = DEVICE_INDEX

        print(f"使用设备索引: {self.device_index}")

        self.cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise CaptureOpenError("无法打开采集卡")

        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 1)

        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.fourcc))
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        self.actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        if self.actual_w != self.width or self.actual_h != self.height:
            raise CaptureConfigError(
                f"分辨率设置失败，实际为 {self.actual_w}x{self.actual_h}，"
                f"请检查采集卡是否支持 {self.width}x{self.height}@{self.fps} 的 {self.fourcc} 输出。"
            )

        print(f"✅ 成功打开 {self.actual_w}x{self.actual_h} @ {self.actual_fps:.2f} FPS ({self.fourcc})")

    def read(self, apply_flip=True):
        """
        读取一帧。
        apply_flip=True 时，会按 FLIP_MODE 做翻转，保持原 GUI 行为。
        """
        if self.cap is None:
            raise CaptureOpenError("采集卡未打开")

        ret, frame = self.cap.read()
        if not ret:
            return None

        if apply_flip and self.flip_mode is not None:
            frame = cv2.flip(frame, self.flip_mode)

        return frame

    def get_actual(self):
        return {
            "width": self.actual_w,
            "height": self.actual_h,
            "fps": self.actual_fps,
            "fourcc": self.fourcc,
        }

    def save_snapshot(self, frame, directory=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"capture_{timestamp}.png"

        if directory:
            filepath = os.path.join(directory, filename)
        else:
            filepath = filename

        cv2.imwrite(filepath, frame)
        print(f"已保存截图: {filepath}")
        return filepath

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()