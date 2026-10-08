# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 工作流引擎】

用途：
    执行单个原子工作流（一个 xxx.json），按顺序跑完所有 steps。
    这是整个自动化系统的"最小执行单元"。

职责：
    1. 加载 JSON 工作流文件
    2. 逐个执行 steps（键盘 / 鼠标 / 图像定位）
    3. 维护运行时状态（上次定位坐标、全局变量表）
    4. 通过 Qt 信号向界面汇报日志、进度、错误
    5. 支持 暂停 / 继续 / 停止

被谁使用：
    - 界面/执行面板.py       （单工作流执行）
    - 核心/编排引擎.py       （编排中的每个节点）

不依赖任何界面代码，纯业务逻辑。
================================================================
"""
import os
import json
import time
import traceback

from PyQt5.QtCore import QThread, pyqtSignal


# ============================================================
# VK → CH9329 HID 键码表
# ============================================================
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

MOD_LCTRL  = 0x01
MOD_LSHIFT = 0x02
MOD_LALT   = 0x04
MOD_LWIN   = 0x08
MOD_RCTRL  = 0x10
MOD_RSHIFT = 0x20
MOD_RALT   = 0x40
MOD_RWIN   = 0x80

HID_ENTER = "28"


# ============================================================
# 步骤名生成
# ============================================================
def gen_step_name(step):
    t = step.get("type", "?")
    a = step.get("action", "")

    if t == "keyboard":
        if a == "type_text":
            txt = step.get("text", "")
            suffix = " + 回车" if step.get("press_enter") else ""
            return f"键盘输入: {txt!r}{suffix}"
        if a == "press_keys":
            keys = step.get("keys", [])
            parts = []
            for k in keys:
                mods = []
                if k.get("ctrl"):  mods.append("Ctrl")
                if k.get("shift"): mods.append("Shift")
                if k.get("alt"):   mods.append("Alt")
                if k.get("meta"):  mods.append("Win")
                parts.append("+".join(mods + [k.get("text", "?")]))
            return f"键盘组合键: {' '.join(parts)}"

    elif t == "mouse":
        action_map = {
            "click": "单击", "double_click": "双击", "move": "移动",
            "drag": "拖动", "scroll_up": "滚轮上滚", "scroll_down": "滚轮下滚",
        }
        label = action_map.get(a, a)
        if step.get("use_last_location"):
            return f"鼠标{label} (上次定位)"
        return f"鼠标{label} ({step.get('x', 0)},{step.get('y', 0)})"

    elif t == "locate":
        templates = step.get("additional_templates", [])
        if not templates and step.get("template"):
            templates = [step["template"]]
        if templates:
            return f"图像定位: {os.path.basename(templates[0])}"
        return "图像定位"

    return t


class WorkflowError(Exception):
    pass


# ============================================================
# 单步执行器
# ============================================================
class StepExecutor:
    """
    单步执行器 + 全局变量表
    一次编排执行期间，同一个实例贯穿所有原子工作流
    """

    def __init__(self, mouse, keyboard, screenshot_func,
                 locate_func, log_cb, is_stopped_cb=None,
                 pause_event=None, variables=None):
        self.mouse = mouse
        self.keyboard = keyboard
        self.screenshot_func = screenshot_func
        self.locate_func = locate_func
        self.log = log_cb
        self.is_stopped_cb = is_stopped_cb
        self.pause_event = pause_event

        self.variables = variables if variables is not None else {}

        self.last_locate_center = None
        self.last_locate_rect = None
        self._indent = 0

    def _log(self, msg):
        prefix = "  " * self._indent
        self.log(prefix + msg)

    # ==================== 主入口 ====================
    def execute(self, step):
        step_type = step.get("type", "")
        if step_type == "keyboard":
            self._exec_keyboard(step)
        elif step_type == "mouse":
            self._exec_mouse(step)
        elif step_type == "locate":
            self._exec_locate(step)
        else:
            raise WorkflowError(f"未知的步骤类型: {step_type}")

    # ==================== keyboard ====================
    def _exec_keyboard(self, step):
        action = step.get("action", "")
        self._interruptible_sleep(float(step.get("delay_before", 0.0)))

        if action == "type_text":
            self._do_type_text(step)
        elif action == "press_keys":
            self._do_press_keys(step)
        else:
            raise WorkflowError(f"未知的键盘动作: {action}")

        self._interruptible_sleep(float(step.get("delay_after", 0.0)))

    def _do_type_text(self, step):
        text = step.get("text", "")
        press_enter = bool(step.get("press_enter", False))
        enter_times = int(step.get("enter_times", 1))

        if text:
            self._log(f"⌨️  输入文本: {text!r}  ({len(text)} 字符)")
            self.keyboard.send_text(text)
            time.sleep(0.15)

        if press_enter:
            n = max(1, enter_times)
            self._log(f"⏎  按回车 {n} 次")
            for _ in range(n):
                self._press_enter()
                time.sleep(0.1)

    def _do_press_keys(self, step):
        keys = step.get("keys", [])
        if not keys:
            raise WorkflowError("press_keys 未提供 keys")

        for k in keys:
            modifier = 0
            if k.get("ctrl"):  modifier |= MOD_LCTRL
            if k.get("shift"): modifier |= MOD_LSHIFT
            if k.get("alt"):   modifier |= MOD_LALT
            if k.get("meta"):  modifier |= MOD_LWIN

            vk = int(k.get("key", 0))
            hid = VK_TO_HID.get(vk)
            if hid is None:
                raise WorkflowError(f"不支持的 VK 码: {vk}")

            self._log(f"⌨️  组合键 modifier=0x{modifier:02X}, hid={hid}")
            self.keyboard._send_cmd(modifier, [hid])
            time.sleep(0.05)
            self.keyboard._send_cmd(0x00, [])
            time.sleep(0.05)

    def _press_enter(self):
        self.keyboard._send_cmd(0x00, [HID_ENTER])
        time.sleep(0.05)
        self.keyboard._send_cmd(0x00, [])
        time.sleep(0.05)

    # ==================== mouse ====================
    def _exec_mouse(self, step):
        action = step.get("action", "")
        self._interruptible_sleep(float(step.get("delay_before", 0.0)))

        x, y = self._resolve_mouse_target(step)

        if action == "click":
            button = step.get("button", "left")
            self._log(f"🖱️  单击 ({x}, {y}) button={button}")
            self.mouse.click(x, y, button=button)

        elif action == "double_click":
            button = step.get("button", "left")
            self._log(f"🖱️  双击 ({x}, {y}) button={button}")
            self.mouse.double_click(x, y, button=button)

        elif action == "move":
            self._log(f"🖱️  移动 ({x}, {y})")
            self.mouse.move(x, y)

        elif action == "drag":
            tx = int(step.get("drag_to_x", 0))
            ty = int(step.get("drag_to_y", 0))
            duration = float(step.get("drag_duration", 0.5))
            self._log(f"🖱️  拖动 ({x}, {y}) → ({tx}, {ty})")
            self.mouse.drag(x, y, tx - x, ty - y, duration=duration)

        elif action == "scroll_up":
            amount = int(step.get("scroll_amount", 1))
            self._log(f"🖱️  滚轮上滚 {amount}")
            self.mouse.scroll(x, y, amount)

        elif action == "scroll_down":
            amount = int(step.get("scroll_amount", 1))
            self._log(f"🖱️  滚轮下滚 {amount}")
            self.mouse.scroll(x, y, -amount)

        else:
            raise WorkflowError(f"未知的鼠标动作: {action}")

        self._interruptible_sleep(float(step.get("delay_after", 0.0)))

    def _resolve_mouse_target(self, step):
        use_last = bool(step.get("use_last_location", False))
        offset_x = int(step.get("offset_x", 0))
        offset_y = int(step.get("offset_y", 0))

        if use_last:
            if self.last_locate_center is None:
                raise WorkflowError(
                    "use_last_location=true，但此前没有成功定位过")
            base_x, base_y = self.last_locate_center
        else:
            base_x = int(step.get("x", 0))
            base_y = int(step.get("y", 0))

        return base_x + offset_x, base_y + offset_y

    # ==================== locate ====================
    def _exec_locate(self, step):
        template = step.get("template", "")
        additional = step.get("additional_templates", [])
        if not template and additional:
            template = additional[0]
        if not template:
            raise WorkflowError("locate 未提供模板路径")

        confidence = float(step.get("threshold", 0.95))
        timeout = float(step.get("timeout", 10.0))

        use_region = bool(step.get("use_region", False))
        if use_region:
            region = (
                int(step.get("region_x", 0)),
                int(step.get("region_y", 0)),
                int(step.get("region_width", 0)),
                int(step.get("region_height", 0)),
            )
        else:
            region = None

        self._log(f"🔍 定位: {os.path.basename(template)}")

        result = self.locate_func(
            template, self.screenshot_func,
            confidence=confidence, timeout=timeout, region=region,
        )

        if result is None:
            self.variables["_last_locate_success"] = False
            on_fail = step.get("on_fail", "stop")
            if on_fail == "continue":
                self._log("⚠️ 定位失败，on_fail=continue")
                return
            if on_fail == "skip":
                self._log("⚠️ 定位失败，on_fail=skip")
                return
            raise WorkflowError(f"定位失败: {os.path.basename(template)}")

        x, y, w, h = result
        self.last_locate_rect = (x, y, w, h)
        if step.get("use_center", True):
            self.last_locate_center = (x + w // 2, y + h // 2)
        else:
            self.last_locate_center = (x, y)

        self.variables["_last_locate_success"] = True
        self.variables["_last_locate_center"] = self.last_locate_center
        self.variables["_last_locate_rect"] = self.last_locate_rect

        save_var = step.get("save_to_variable", "")
        if save_var:
            self.variables[save_var] = {
                "x": x, "y": y, "w": w, "h": h,
                "center": self.last_locate_center,
            }
            self._log(f"   ↳ 已保存到变量: {save_var}")

        cx, cy = self.last_locate_center
        self._log(f"✅ 定位 ({x}, {y}, {w}, {h})，中心 ({cx}, {cy})")

    # ==================== 辅助 ====================
    def _interruptible_sleep(self, seconds):
        if seconds <= 0:
            return
        end = time.time() + seconds
        while time.time() < end:
            if self.is_stopped_cb and self.is_stopped_cb():
                return
            time.sleep(0.05)

    def _wait_if_paused(self):
        if self.pause_event is not None:
            self.pause_event.wait()


# ============================================================
# 单工作流执行线程（保留，用于单独测试一个 JSON）
# ============================================================
class WorkflowWorker(QThread):
    log_signal      = pyqtSignal(str)
    step_started    = pyqtSignal(int, dict)
    step_finished   = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)
    error_signal    = pyqtSignal(str)

    def __init__(self, workflow_path,
                 mouse, keyboard,
                 screenshot_func, locate_func,
                 variables=None, parent=None):
        super().__init__(parent)
        self.workflow_path = workflow_path
        self.mouse = mouse
        self.keyboard = keyboard
        self.screenshot_func = screenshot_func
        self.locate_func = locate_func
        self.variables = variables if variables is not None else {}

        self._stop_flag = False
        self._pause_event = __import__("threading").Event()
        self._pause_event.set()

        with open(workflow_path, "r", encoding="utf-8") as f:
            self.workflow = json.load(f)

    def pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.log_signal.emit("⏸️  已暂停")

    def resume(self):
        if not self._pause_event.is_set():
            self._pause_event.set()
            self.log_signal.emit("▶️  已继续")

    def stop(self):
        self._stop_flag = True
        self._pause_event.set()
        self.log_signal.emit("⏹️  请求停止...")

    def run(self):
        try:
            name = self.workflow.get("name", "未命名工作流")
            steps = self.workflow.get("steps", [])
            total = len(steps)

            self.log_signal.emit(f"=== 开始执行: {name} ===")
            self.log_signal.emit(f"共 {total} 个步骤")

            executor = StepExecutor(
                mouse=self.mouse,
                keyboard=self.keyboard,
                screenshot_func=self.screenshot_func,
                locate_func=self.locate_func,
                log_cb=self.log_signal.emit,
                is_stopped_cb=lambda: self._stop_flag,
                pause_event=self._pause_event,
                variables=self.variables,
            )

            for idx, step in enumerate(steps):
                if not self._wait_if_paused_or_stop():
                    self.finished_signal.emit(False)
                    return
                if not step.get("enabled", True):
                    self.log_signal.emit(
                        f"--- 步骤 {idx+1}/{total} 已禁用，跳过 ---")
                    continue

                step_name = step.get("name") or gen_step_name(step)
                self.log_signal.emit(
                    f"--- 步骤 {idx+1}/{total}: {step_name} ---")
                self.step_started.emit(idx, step)

                try:
                    executor.execute(step)
                except Exception as e:
                    tb = traceback.format_exc()
                    self.log_signal.emit(f"❌ 步骤 {idx+1} 失败: {e}")
                    self.error_signal.emit(
                        f"步骤 {idx+1} 失败: {e}\n{tb}")
                    self.finished_signal.emit(False)
                    return

                self.step_finished.emit(idx)

            self.log_signal.emit(f"✅ 工作流执行完成（共 {total} 步）")
            self.finished_signal.emit(True)

        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"❌ 工作流异常: {e}")
            self.error_signal.emit(f"工作流异常: {e}\n{tb}")
            self.finished_signal.emit(False)

    def _wait_if_paused_or_stop(self):
        self._pause_event.wait()
        if self._stop_flag:
            self.log_signal.emit("⏹️  执行已停止")
            return False
        return True