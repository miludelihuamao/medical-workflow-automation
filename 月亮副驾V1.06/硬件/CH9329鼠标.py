"""
硬件绝对鼠标驱动（整理版）
通过串口发送 HID 绝对鼠标数据包
支持独立串口和共享串口两种模式
[优化] 时间参数集中配置，增加边界检查，串口连接管理参考键盘部分
"""

import serial
import serial.tools.list_ports
import time


class HardwareMouse:
    # ==================== 串口连接配置（自动匹配 CH340） ====================
    DEFAULT_PORT = None                    # 默认串口（None 表示自动扫描）
    AUTO_MATCH_NAME = "USB-SERIAL CH340"   # 设备名称关键词
    AUTO_MATCH_VID = "1A86"                # CH340 厂商 ID
    AUTO_MATCH_PID = "7523"                # CH340 产品 ID

    # ==================== 时间参数（可在此集中调整） ====================
    SEND_DELAY = 0.01          # 每次发送数据后的延时（秒）
    CLICK_DELAY = 0.05         # 单击时按下与释放之间的延时（秒）
    DOUBLE_CLICK_INTERVAL = 0.05  # 双击两次点击之间的间隔（秒）
    DRAG_STEPS_PER_SECOND = 50     # 拖动时每秒步数
    MIN_DRAG_STEPS = 2             # 拖动最少步数

    # ==================== 鼠标按键映射 ====================
    BUTTON_MAP = {
        'left':   0x01,   # 左键
        'right':  0x02,   # 右键
        'middle': 0x04,   # 中键
    }

    # ==================== 内部坐标范围 ====================
    MAX_ABS_COORD = 4095

    def __init__(self, port_or_serial=None, baudrate=115200, screen_w=1920, screen_h=1080):
        """
        初始化硬件鼠标

        Args:
            port_or_serial:
                - 字符串：串口号（如 "COM17"），强制使用该端口
                - serial.Serial 对象：共享串口，直接使用
                - None：自动扫描匹配 "USB-SERIAL CH340" 的设备
            baudrate: 波特率（默认 115200，一般无需修改）
            screen_w: 屏幕宽度（像素）
            screen_h: 屏幕高度（像素）
        """
        # 自动识别串口
        if port_or_serial is None:
            if self.DEFAULT_PORT is not None:
                port_or_serial = self.DEFAULT_PORT
            else:
                detected_port = self._auto_detect_ch340()
                if detected_port is None:
                    raise RuntimeError(
                        f"未找到匹配的 {self.AUTO_MATCH_NAME} 设备，"
                        "请检查连接或手动传入串口号。"
                    )
                port_or_serial = detected_port
                print(f"✅ 自动检测到设备: {port_or_serial}")

        if baudrate is None:
            baudrate = 115200

        # 打开串口（超时固定 0.1 秒，可内部调整）
        if isinstance(port_or_serial, str):
            try:
                self.ser = serial.Serial(port_or_serial, baudrate, timeout=0.1)
                self._own_serial = True
            except (serial.SerialException, OSError) as e:
                raise RuntimeError(f"无法打开串口 {port_or_serial}: {e}")
        else:
            self.ser = port_or_serial
            self._own_serial = False

        # 屏幕尺寸与内部坐标记录
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._last_x = 0   # 记录最后一次发送的坐标（用于 release）
        self._last_y = 0

    # ==================== 自动扫描器 ====================
    @classmethod
    def _auto_detect_ch340(cls):
        """
        遍历当前系统所有串口，尝试匹配 CH340 设备。
        匹配策略：优先按设备名称匹配，备用按 VID:PID 匹配。
        Returns: 串口号（如 "COM3"） 或 None
        """
        try:
            ports = serial.tools.list_ports.comports()
        except Exception as e:
            print(f"⚠ 扫描串口失败: {e}")
            return None

        for port in ports:
            # 策略一：按设备描述匹配
            if port.description and cls.AUTO_MATCH_NAME.lower() in port.description.lower():
                return port.device

            # 策略二：按硬件 ID（VID:PID）匹配
            if port.vid is not None and port.pid is not None:
                vid_hex = f"{port.vid:04X}".upper()
                pid_hex = f"{port.pid:04X}".upper()
                if vid_hex == cls.AUTO_MATCH_VID and pid_hex == cls.AUTO_MATCH_PID:
                    return port.device

        return None

    # ==================== 底层数据发送 ====================
    def _send(self, x, y, buttons=0x00, wheel=0x00):
        """
        通过串口发送绝对鼠标数据包

        协议格式 (12字节 + 1字节校验和):
            帧头:   0x57 0xAB
            地址:   0x00
            命令:   0x04 (绝对鼠标数据)
            长度:   0x07
            数据1:  0x02 (固定值)
            数据2:  buttons (bit0=左键, bit1=右键, bit2=中键)
            数据3:  X坐标低字节
            数据4:  X坐标高字节
            数据5:  Y坐标低字节
            数据6:  Y坐标高字节
            数据7:  wheel (滚轮)
            校验和: 所有字节累加取低8位

        Args:
            x, y: 目标坐标（像素值，相对于屏幕左上角）
            buttons: 按键值（位掩码）
            wheel: 滚轮值
        """
        # 边界检查：将坐标钳位到屏幕范围内
        x = max(0, min(int(x), self.screen_w - 1))
        y = max(0, min(int(y), self.screen_h - 1))

        # 记录当前坐标（用于 release）
        self._last_x = x
        self._last_y = y

        # 坐标转换：像素 → 4096×4096 内部坐标系
        x_abs = (self.MAX_ABS_COORD * x) // max(1, self.screen_w - 1)
        y_abs = (self.MAX_ABS_COORD * y) // max(1, self.screen_h - 1)

        # 拆分高低字节
        x_low  = x_abs & 0xFF
        x_high = (x_abs >> 8) & 0xFF
        y_low  = y_abs & 0xFF
        y_high = (y_abs >> 8) & 0xFF

        # 构造数据包
        packet = bytes([
            0x57, 0xAB,     # 帧头
            0x00,           # 地址码
            0x04,           # 命令码：绝对鼠标数据
            0x07,           # 后续数据长度
            0x02,           # 固定值
            buttons,        # 按键值
            x_low,          # X低字节
            x_high,         # X高字节
            y_low,          # Y低字节
            y_high,         # Y高字节
            wheel           # 滚轮值
        ])

        # 计算校验和
        checksum = sum(packet) & 0xFF

        # 发送（带异常保护）
        try:
            self.ser.write(packet + bytes([checksum]))
        except (serial.SerialException, serial.SerialTimeoutException, OSError) as e:
            print(f"⚠ 串口写入失败: {e}")
            raise   # 可选择抛出或仅记录，此处选择抛出以便上层处理

        # 发送后短暂延时
        time.sleep(self.SEND_DELAY)

    # ==================== 鼠标操作 ====================
    def move(self, x, y):
        """
        移动鼠标到指定坐标（不点击）

        Args:
            x, y: 目标坐标（像素）
        """
        self._send(x, y, buttons=0x00)

    def click(self, x, y, button='left'):
        """
        单击鼠标

        Args:
            x, y: 目标坐标
            button: 'left'(左键), 'right'(右键), 'middle'(中键)
        """
        btn = self.BUTTON_MAP.get(button, 0x01)

        # 按下
        self._send(x, y, buttons=btn)
        time.sleep(self.CLICK_DELAY)
        # 释放
        self._send(x, y, buttons=0x00)

    def double_click(self, x, y, button='left'):
        """
        双击鼠标

        Args:
            x, y: 目标坐标
            button: 按键类型
        """
        self.click(x, y, button)
        time.sleep(self.DOUBLE_CLICK_INTERVAL)
        self.click(x, y, button)

    def press(self, x, y, button='left'):
        """
        按下鼠标不放

        Args:
            x, y: 目标坐标
            button: 按键类型
        """
        btn = self.BUTTON_MAP.get(button, 0x01)
        self._send(x, y, buttons=btn)

    def release(self, x=None, y=None):
        """
        释放所有鼠标按键
        如果不传坐标，则使用最后一次发送的坐标（保持光标位置）

        Args:
            x, y: 可选，指定释放时的坐标
        """
        if x is None:
            x = self._last_x
        if y is None:
            y = self._last_y
        self._send(x, y, buttons=0x00)

    def drag(self, x, y, dx, dy, duration=1):
        """
        从 (x, y) 拖动到 (x+dx, y+dy)

        Args:
            x, y: 起始坐标
            dx, dy: 拖动偏移量（像素）
            duration: 拖动持续时间（秒）
        """
        steps = max(self.MIN_DRAG_STEPS, int(duration * self.DRAG_STEPS_PER_SECOND))
        self.move(x, y)                       # 先移动到起点，不带按键
        t0 = time.perf_counter()
        for i in range(steps + 1):
            cx = x + int(dx * i / steps)
            cy = y + int(dy * i / steps)
            self._send(cx, cy, buttons=0x01 if i < steps else 0x00)
            wait = t0 + duration * (i + 1) / steps - time.perf_counter()
            if wait > 0:
                time.sleep(wait) 

    def scroll(self, x, y, amount):
        """
        滚轮操作

        Args:
            x, y: 鼠标位置
            amount: 滚动量
                    正数 = 向上滚动 (0x01~0x7F)
                    负数 = 向下滚动 (0x81~0xFF)
                    0    = 无动作
        """
        if amount > 0:
            wheel = min(amount, 0x7F)
        elif amount < 0:
            wheel = 0x100 - min(-amount, 0x7F)
        else:
            wheel = 0x00

        self._send(x, y, buttons=0x00, wheel=wheel)

    # ==================== 资源管理 ====================
    def close(self):
        """
        关闭串口连接
        只有在自己创建的串口时才真正关闭，共享串口由外部管理
        """
        if self._own_serial and self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except (serial.SerialException, OSError) as e:
                print(f"⚠ 关闭串口失败: {e}")

    def __del__(self):
        """析构函数：自动关闭串口"""
        try:
            if self.ser and self.ser.is_open:
                self._send(self._last_x, self._last_y, buttons=0x00)
        except Exception:
            pass
        try:
            self.close()
        except Exception:
            pass