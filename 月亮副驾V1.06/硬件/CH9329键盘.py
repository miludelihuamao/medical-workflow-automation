"""
CH9329 硬件键盘模拟器驱动（无外部依赖版，加速发送）
支持 GBK 中文输入（Alt+数字小键盘）和 ASCII 字符直接发送
支持独立串口和共享串口两种模式
[新增] 自动扫描 USB-SERIAL CH340 设备，无需手动填写 COM 号
[优化] 时序参数已优化：key_hold=0.001, char_gap=0.003（更快）
[修改] 删除 press_enter/press_tab，发送文本前自动确认 CapsLock
[新增] 增加 Windows 定时器精度（timeBeginPeriod(1)），大幅降低 sleep 实际延时
"""

import serial
import serial.tools.list_ports
import time
import sys
import ctypes      # [新增] 用于调用 Windows 多媒体定时器 API


# ==================== [新增] 提高 Windows 定时器精度的辅助函数 ====================
_TIMER_ACCURACY_SET = False   # 全局标志，只设置一次

def _set_windows_timer_resolution():
    """将 Windows 系统时钟分辨率设为 1ms，仅当运行在 Windows 上"""
    global _TIMER_ACCURACY_SET
    if _TIMER_ACCURACY_SET:
        return True
    if sys.platform == 'win32':
        try:
            winmm = ctypes.windll.winmm
            winmm.timeBeginPeriod(1)   # 设置最小定时器间隔为 1ms
            _TIMER_ACCURACY_SET = True
            return True
        except Exception as e:
            print(f"⚠ 无法设置定时器精度 (非致命): {e}")
            return False
    return False
# ========================================================================


class CH9329:
    # ==================== 串口连接配置（自动匹配 CH340） ====================
    DEFAULT_PORT = None
    AUTO_MATCH_NAME = "USB-SERIAL CH340"  # 设备名称关键词（不区分大小写）
    AUTO_MATCH_VID = "1A86"               # CH340 的 USB 厂商 ID
    AUTO_MATCH_PID = "7523"               # CH340 的产品 ID

    # ==================== 时序参数（已加速） ====================
    TIMING_DEFAULTS = {
        'key_hold': 0.0005,            # 按下按键后的保持时间（秒）
        'char_gap': 0.002,            # 字符间隔时间（秒）
        'led_query_wait': 0.05,       # 查询指示灯等待时间
        'lock_key_wait': 0.1,         # 锁定键切换后等待时间
        'capslock_wait': 0.15,        # CapsLock 切换后等待时间
        'gbk_altcode_padding': 5,     # GBK Alt 码补零位数
    }

    def __init__(self, port_or_serial=None, baudrate=115200):
        """
        初始化 CH9329 键盘

        Args:
            port_or_serial:
                - 字符串：串口号（如 "COM17"），强制使用该端口
                - serial.Serial 对象：共享串口，直接使用
                - None：自动扫描匹配 "USB-SERIAL CH340" 的设备
            baudrate: 波特率（默认 115200，一般无需修改）
        """
        # [新增] 在实例化时提升 Windows 定时器精度（仅一次）
        _set_windows_timer_resolution()

        self.timing = self.TIMING_DEFAULTS.copy()

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

        if isinstance(port_or_serial, str):
            try:
                self.ser = serial.Serial(port_or_serial, baudrate, timeout=0.2)
                self._own_serial = True
            except (serial.SerialException, OSError) as e:
                raise RuntimeError(f"无法打开串口 {port_or_serial}: {e}")
        else:
            self.ser = port_or_serial
            self._own_serial = False

        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        self.capslock_mode = False

        # 自动开启 CapsLock
        try:
            self.set_capslock_mode(True)
        except Exception as e:
            print(f"⚠ 自动开启 CapsLock 失败: {e}")

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
            if port.description and cls.AUTO_MATCH_NAME.lower() in port.description.lower():
                return port.device

            if port.vid is not None and port.pid is not None:
                vid_hex = f"{port.vid:04X}".upper()
                pid_hex = f"{port.pid:04X}".upper()
                if vid_hex == cls.AUTO_MATCH_VID and pid_hex == cls.AUTO_MATCH_PID:
                    return port.device

        return None

    # ==================== CH9329 键码表（HID Page 07） ====================
    KEYCODE_TABLE = {
        # 字母
        'A':'04','B':'05','C':'06','D':'07','E':'08','F':'09','G':'0A',
        'H':'0B','I':'0C','J':'0D','K':'0E','L':'0F','M':'10','N':'11',
        'O':'12','P':'13','Q':'14','R':'15','S':'16','T':'17','U':'18',
        'V':'19','W':'1A','X':'1B','Y':'1C','Z':'1D',
        # 数字行（未按 Shift 时的数字）
        '1':'1E','2':'1F','3':'20','4':'21','5':'22','6':'23','7':'24',
        '8':'25','9':'26','0':'27',
        # 功能/控制键
        'ENTER_L':'28',   # 主键盘区 Enter
        'ESC':'29',
        'BACKSPACE':'2A',
        'TAB':'2B',
        'SPACE':'2C',
        'MINUS':'2D',       # - _
        'EQUAL':'2E',       # = +
        'LBRACKET':'2F',    # [ {
        'RBRACKET':'30',    # ] }
        'BACKSLASH':'31',   # \ |
        'SEMICOLON':'33',   # ; :
        'QUOTE':'34',       # ' "
        'GRAVE':'35',       # ` ~
        'COMMA':'36',       # , <
        'PERIOD':'37',      # . >
        'SLASH':'38',       # / ?
        'CAPSLOCK':'39',
        # 功能键 F1-F12
        'F1':'3A','F2':'3B','F3':'3C','F4':'3D','F5':'3E','F6':'3F',
        'F7':'40','F8':'41','F9':'42','F10':'43','F11':'44','F12':'45',
        'PRINTSCREEN':'46',
        'SCROLLLOCK':'47',
        'PAUSE':'48',
        'INSERT':'49',
        'HOME':'4A',
        'PGUP':'4B',
        'DELETE':'4C',
        'END':'4D',
        'PGDN':'4E',
        'RIGHT':'4F',
        'LEFT':'50',
        'DOWN':'51',
        'UP':'52',
        'NUMLOCK':'53',
        # 小键盘
        'NUMPAD_SLASH':'54',
        'NUMPAD_ASTERISK':'55',
        'NUMPAD_MINUS':'56',
        'NUMPAD_PLUS':'57',
        'NUMPAD_ENTER':'58',
        'NUMPAD_1':'59','NUMPAD_2':'5A','NUMPAD_3':'5B',
        'NUMPAD_4':'5C','NUMPAD_5':'5D','NUMPAD_6':'5E',
        'NUMPAD_7':'5F','NUMPAD_8':'60','NUMPAD_9':'61',
        'NUMPAD_0':'62',
        'NUMPAD_PERIOD':'63',
    }

    # 修饰键位掩码（与协议第1字节对应）
    MOD_LCTRL  = 0x01
    MOD_LSHIFT = 0x02
    MOD_LALT   = 0x04
    MOD_LWIN   = 0x08
    MOD_RCTRL  = 0x10
    MOD_RSHIFT = 0x20
    MOD_RALT   = 0x40
    MOD_RWIN   = 0x80

    # ==================== 底层 HID 报告发送 ====================
    def _send_cmd(self, modifier, key_codes):
        """
        发送 14 字节键盘 HID 报告（CMD_SEND_KB_GENERAL_DATA, 0x02）
        协议格式:
            帧头:   0x57 0xAB
            地址:   0x00
            命令:   0x02 (键盘数据)
            长度:   0x08
            修饰键: 1字节
            保留:   0x00
            按键码: 6字节 (最多6个)
            校验和: 1字节 (累加和低8位)
        """
        header = ['57', 'AB', '00', '02', '08']
        mod_hex = format(modifier, '02X')
        reserved = '00'
        keys = key_codes[:6] + ['00'] * (6 - len(key_codes))
        data_bytes = header + [mod_hex, reserved] + keys

        checksum = sum(int(b, 16) for b in data_bytes) & 0xFF
        cmd_hex = ''.join(data_bytes) + format(checksum, '02X')

        try:
            self.ser.write(bytes.fromhex(cmd_hex))
        except (serial.SerialException, serial.SerialTimeoutException, OSError) as e:
            print(f"⚠ 串口写入失败: {e}")

    # ==================== 键盘指示灯查询 ====================
    def get_keyboard_led_status(self):
        """
        查询键盘指示灯状态（CMD_GET_INFO, 0x01）
        Returns: dict 或 None
        """
        try:
            self.ser.reset_input_buffer()
            cmd_bytes = bytes.fromhex('57 AB 00 01 00 03')
            self.ser.write(cmd_bytes)
            time.sleep(self.timing['led_query_wait'])
            response = self.ser.read(14)
        except (serial.SerialException, serial.SerialTimeoutException, OSError) as e:
            print(f"⚠ 查询指示灯失败: {e}")
            return None

        if len(response) < 6 or response[0] != 0x57 or response[1] != 0xAB or response[3] != 0x81:
            return None

        data_len = response[4]
        if data_len != 8:
            return None

        data = response[5:5+8]
        if len(data) < 3:
            return None

        return {
            'numlock':   bool(data[2] & 0x01),
            'capslock':  bool(data[2] & 0x02),
            'scrolllock':bool(data[2] & 0x04),
            'version':   f"V{data[0] >> 4}.{data[0] & 0x0F}",
            'usb_connected': data[1] == 0x01
        }

    # ==================== 锁定键辅助方法 ====================
    def _toggle_lock_key(self, key_code, wait_after):
        """通用切换锁定键（按下 → 保持 → 释放 → 等待）"""
        try:
            self._send_cmd(0x00, [key_code])
            time.sleep(self.timing['key_hold'])
        finally:
            self._send_cmd(0x00, [])
            time.sleep(wait_after)

    def _ensure_lock_on(self, lock_name, key_code, led_bit, attempts):
        """
        确保指定锁定键处于点亮状态
        lock_name: 用于打印的名称
        key_code: 锁定键键码
        led_bit: LED 状态位名称（如 'capslock'）
        attempts: 最大尝试次数
        """
        status = self.get_keyboard_led_status()
        if status is None:
            print(f"⚠ 无法读取指示灯状态，{lock_name} 状态未知")
            return False

        if status.get(led_bit):
            return True

        for attempt in range(attempts):
            print(f"⚠ {lock_name} 当前为灭，尝试开启（第 {attempt+1} 次）...")
            self._toggle_lock_key(key_code, self.timing['lock_key_wait'])
            time.sleep(self.timing['lock_key_wait'])
            status = self.get_keyboard_led_status()
            if status and status.get(led_bit):
                print(f"✅ {lock_name} 已成功开启！")
                return True

        print(f"❌ 自动开启 {lock_name} 失败，请手动按下对应按键")
        return False

    def toggle_capslock(self):
        """切换 CapsLock 状态"""
        self._toggle_lock_key(self.KEYCODE_TABLE['CAPSLOCK'], self.timing['capslock_wait'])

    def toggle_numlock(self):
        """切换 NumLock 状态"""
        self._toggle_lock_key(self.KEYCODE_TABLE['NUMLOCK'], self.timing['lock_key_wait'])

    def ensure_capslock_on(self, auto=True):
        """确保 CapsLock 点亮"""
        if not auto:
            status = self.get_keyboard_led_status()
            return bool(status and status.get('capslock'))
        return self._ensure_lock_on('CapsLock', self.KEYCODE_TABLE['CAPSLOCK'], 'capslock', attempts=2)

    def ensure_numlock_on(self, auto=True):
        """确保 NumLock 点亮"""
        if not auto:
            status = self.get_keyboard_led_status()
            return bool(status and status.get('numlock'))
        return self._ensure_lock_on('NumLock', self.KEYCODE_TABLE['NUMLOCK'], 'numlock', attempts=1)

    def get_numlock_status(self):
        """获取 NumLock 状态"""
        result = self.get_keyboard_led_status()
        return result.get('numlock') if result else None

    def set_capslock_mode(self, enable):
        """
        设置强制 CapsLock 模式
        启用后会尝试开启 CapsLock，后续字符发送将利用该状态处理大小写
        """
        self.capslock_mode = bool(enable)
        if self.capslock_mode:
            success = self.ensure_capslock_on(auto=True)
            if not success:
                print("⚠ 警告：CapsLock 未能确认开启，大小写输出可能不准确。")
        print(f"🔀 CapsLock 模式已{'启用' if self.capslock_mode else '禁用'}")

    # ==================== 基础按键操作 ====================
    def press_key(self, key_code, modifier=0x00):
        """按下并释放单个按键（带 finally 保护）"""
        try:
            self._send_cmd(modifier, [key_code])
            time.sleep(self.timing['key_hold'])
        finally:
            self._send_cmd(0x00, [])
            time.sleep(self.timing['char_gap'])

    def hotkey(self, modifier, key_code):
        """发送组合键（如 Ctrl+C），与 press_key 等价"""
        self.press_key(key_code, modifier)

    def press_by_name(self, key_name):
        """根据键名（如 'F1', 'UP'）发送单个按键"""
        if key_name.upper() in self.KEYCODE_TABLE:
            self.press_key(self.KEYCODE_TABLE[key_name.upper()])
        else:
            print(f"⚠ 未知键名: {key_name}")

    def press_escape(self):
        """按 Esc 键"""
        self.press_key(self.KEYCODE_TABLE['ESC'])

    def press_arrow(self, direction):
        """按方向键"""
        arrow_map = {
            'up':    self.KEYCODE_TABLE['UP'],
            'down':  self.KEYCODE_TABLE['DOWN'],
            'left':  self.KEYCODE_TABLE['LEFT'],
            'right': self.KEYCODE_TABLE['RIGHT'],
        }
        key = arrow_map.get(direction.lower())
        if key:
            self.press_key(key)

    # ==================== GBK 中文输入 ====================
    _NUMPAD_MAP = {
        '0': KEYCODE_TABLE['NUMPAD_0'],
        '1': KEYCODE_TABLE['NUMPAD_1'],
        '2': KEYCODE_TABLE['NUMPAD_2'],
        '3': KEYCODE_TABLE['NUMPAD_3'],
        '4': KEYCODE_TABLE['NUMPAD_4'],
        '5': KEYCODE_TABLE['NUMPAD_5'],
        '6': KEYCODE_TABLE['NUMPAD_6'],
        '7': KEYCODE_TABLE['NUMPAD_7'],
        '8': KEYCODE_TABLE['NUMPAD_8'],
        '9': KEYCODE_TABLE['NUMPAD_9'],
    }

    def _char_to_gbk_altcode(self, ch):
        """将字符转换为 GBK Alt 码"""
        try:
            raw = ch.encode('gbk')
        except UnicodeEncodeError:
            return None
        if len(raw) != 2:
            return None
        return raw[0] * 256 + raw[1]

    def send_gbk_char(self, ch):
        """
        发送单个 GBK 中文字符（Alt+数字小键盘方式）
        返回是否发送成功
        """
        code = self._char_to_gbk_altcode(ch)
        if code is None:
            return False

        code_str = str(code).zfill(self.timing['gbk_altcode_padding'])

        try:
            self._send_cmd(self.MOD_LALT, [])
            for d in code_str:
                key = self._NUMPAD_MAP[d]
                try:
                    self._send_cmd(self.MOD_LALT, [key])
                    time.sleep(self.timing['key_hold'])
                finally:
                    self._send_cmd(self.MOD_LALT, [])
                    time.sleep(self.timing['char_gap'])
        finally:
            self._send_cmd(0x00, [])
            time.sleep(self.timing['char_gap'])
        return True

    def send_ascii_char(self, ch):
        """
        发送单个 ASCII 字符
        根据 capslock_mode 决定大小写是否需要 Shift
        """
        if ch not in self._ASCII_MAP:
            return False

        key = self._ASCII_MAP[ch]

        if ch.isalpha():
            if self.capslock_mode:
                need_shift = ch.islower()   # CapsLock 开启时，小写需 Shift
            else:
                need_shift = ch.isupper()   # 传统模式，大写需 Shift
        else:
            need_shift = ch in '!@#$%^&*()_+{}|:"<>?~'

        modifier = self.MOD_LSHIFT if need_shift else 0x00

        try:
            self._send_cmd(modifier, [key])
            time.sleep(self.timing['key_hold'])
        finally:
            self._send_cmd(0x00, [])
            time.sleep(self.timing['char_gap'])
        return True

    # ==================== 智能字符发送 ====================
    def send_mixed_char(self, ch):
        """智能发送单个字符（自动判断中英文），返回是否成功"""
        self.stats['total'] += 1

        if ch == '\n':
            self.press_key(self.KEYCODE_TABLE['ENTER_L'])
            self.stats['success'] += 1
            return True
        if ch == '\r':
            self.stats['success'] += 1
            return True
        if ch == '\t':
            self.press_key(self.KEYCODE_TABLE['TAB'])
            self.stats['success'] += 1
            return True

        # 优先尝试 GBK 中文
        if self._char_to_gbk_altcode(ch) is not None:
            if self.send_gbk_char(ch):
                self.stats['success'] += 1
                return True
            self.stats['failed'] += 1
            return False

        # 尝试 ASCII
        if self.send_ascii_char(ch):
            self.stats['success'] += 1
            return True
        self.stats['failed'] += 1
        return False

    def send_text(self, text):
        """发送完整文本，并输出统计信息"""
        # 发送前强制确保 CapsLock 开启
        print("🔍 检查 CapsLock 状态...")
        if not self.ensure_capslock_on(auto=True):
            print("⚠ 警告：CapsLock 未能确认开启，可能影响大小写输出。")
        else:
            print("✅ CapsLock 已开启。")

        self.stats = {'total': 0, 'success': 0, 'failed': 0}

        print(f"\n开始发送，共 {len(text)} 个字符...")
        start = time.time()

        for ch in text:
            self.send_mixed_char(ch)

        elapsed = time.time() - start
        print("-" * 40)
        print("发送完成！")
        print(f"  总字符: {self.stats['total']}")
        print(f"  成功: {self.stats['success']}")
        print(f"  失败: {self.stats['failed']}")
        print(f"  耗时: {elapsed:.2f} 秒")
        if elapsed > 0:
            print(f"  速度: {len(text)/elapsed:.2f} 字符/秒")

    # ==================== 资源管理 ====================
    def close(self):
        """关闭串口连接（仅当串口由本类打开时）"""
        if self._own_serial and self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except (serial.SerialException, OSError) as e:
                print(f"⚠ 关闭串口失败: {e}")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ==================== 类定义结束后构建 _ASCII_MAP ====================
CH9329._ASCII_MAP = {
    # 小写字母
    **{chr(97+i): CH9329.KEYCODE_TABLE[chr(65+i)] for i in range(26)},
    # 大写字母
    **{chr(65+i): CH9329.KEYCODE_TABLE[chr(65+i)] for i in range(26)},
    # 数字
    **{str(i): CH9329.KEYCODE_TABLE[str(i)] for i in range(10)},
    # 无 Shift 符号
    ' ':  CH9329.KEYCODE_TABLE['SPACE'],
    '-':  CH9329.KEYCODE_TABLE['MINUS'],
    '=':  CH9329.KEYCODE_TABLE['EQUAL'],
    '[':  CH9329.KEYCODE_TABLE['LBRACKET'],
    ']':  CH9329.KEYCODE_TABLE['RBRACKET'],
    '\\': CH9329.KEYCODE_TABLE['BACKSLASH'],
    ';':  CH9329.KEYCODE_TABLE['SEMICOLON'],
    "'":  CH9329.KEYCODE_TABLE['QUOTE'],
    '`':  CH9329.KEYCODE_TABLE['GRAVE'],
    ',':  CH9329.KEYCODE_TABLE['COMMA'],
    '.':  CH9329.KEYCODE_TABLE['PERIOD'],
    '/':  CH9329.KEYCODE_TABLE['SLASH'],
    # Shift 符号（需要加 Shift）
    '!':  CH9329.KEYCODE_TABLE['1'],
    '@':  CH9329.KEYCODE_TABLE['2'],
    '#':  CH9329.KEYCODE_TABLE['3'],
    '$':  CH9329.KEYCODE_TABLE['4'],
    '%':  CH9329.KEYCODE_TABLE['5'],
    '^':  CH9329.KEYCODE_TABLE['6'],
    '&':  CH9329.KEYCODE_TABLE['7'],
    '*':  CH9329.KEYCODE_TABLE['8'],
    '(':  CH9329.KEYCODE_TABLE['9'],
    ')':  CH9329.KEYCODE_TABLE['0'],
    '_':  CH9329.KEYCODE_TABLE['MINUS'],
    '+':  CH9329.KEYCODE_TABLE['EQUAL'],
    '{':  CH9329.KEYCODE_TABLE['LBRACKET'],
    '}':  CH9329.KEYCODE_TABLE['RBRACKET'],
    '|':  CH9329.KEYCODE_TABLE['BACKSLASH'],
    ':':  CH9329.KEYCODE_TABLE['SEMICOLON'],
    '"':  CH9329.KEYCODE_TABLE['QUOTE'],
    '~':  CH9329.KEYCODE_TABLE['GRAVE'],
    '<':  CH9329.KEYCODE_TABLE['COMMA'],
    '>':  CH9329.KEYCODE_TABLE['PERIOD'],
    '?':  CH9329.KEYCODE_TABLE['SLASH'],
}