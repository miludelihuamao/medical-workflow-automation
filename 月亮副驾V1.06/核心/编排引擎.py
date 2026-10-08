# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 编排引擎】

用途：
    执行"编排"（一个 xxx.编排.json）。
    编排本身不是具体动作，而是"多个原子工作流的组合"，
    按 on_success / on_fail 决定下一个跑哪个 JSON。

职责：
    1. 加载编排文件（nodes 列表）
    2. 从第一个节点开始，逐个执行原子工作流
    3. 每个节点跑完后，按成功/失败跳转到下一个节点
    4. 通过全局变量表让不同工作流之间传递数据
    5. 支持 暂停 / 继续 / 停止
    6. 检测循环引用（同一节点不能访问两次）

被谁使用：
    - 界面/执行面板.py       （识别到 *.编排.json 时使用）

依赖：
    - 核心/工作流引擎.py     （复用 StepExecutor / gen_step_name / WorkflowError）
================================================================
"""
import os
import json
import traceback
import threading

from PyQt5.QtCore import QThread, pyqtSignal

from 核心.工作流引擎 import StepExecutor, gen_step_name, WorkflowError


class FlowWorker(QThread):
    log_signal      = pyqtSignal(str)
    node_started    = pyqtSignal(int, str)
    node_finished   = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)
    error_signal    = pyqtSignal(str)

    def __init__(self, flow_path,
                 mouse, keyboard,
                 screenshot_func, locate_func,
                 parent=None):
        super().__init__(parent)
        self.flow_path = flow_path
        self.mouse = mouse
        self.keyboard = keyboard
        self.screenshot_func = screenshot_func
        self.locate_func = locate_func

        self._stop_flag = False
        self._pause_event = threading.Event()
        self._pause_event.set()

        with open(flow_path, "r", encoding="utf-8") as f:
            self.flow = json.load(f)

    # ---- 控制 ----
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

    # ---- 主循环 ----
    def run(self):
        try:
            name = self.flow.get("name", "未命名编排")
            nodes = self.flow.get("nodes", [])
            if not nodes:
                self.log_signal.emit("⚠️ 编排为空")
                self.finished_signal.emit(False)
                return

            self.log_signal.emit(f"=== 编排开始: {name} ===")
            self.log_signal.emit(f"共 {len(nodes)} 个节点")

            nodes_map = {n.get("id"): n for n in nodes}

            # 全局变量表
            variables = {}

            # 单一 executor
            executor = StepExecutor(
                mouse=self.mouse,
                keyboard=self.keyboard,
                screenshot_func=self.screenshot_func,
                locate_func=self.locate_func,
                log_cb=self.log_signal.emit,
                is_stopped_cb=lambda: self._stop_flag,
                pause_event=self._pause_event,
                variables=variables,
            )

            visited = set()          # 已访问节点
            current_id = nodes[0].get("id")
            seq = 0

            while current_id is not None:
                if not self._wait_if_paused_or_stop():
                    self.finished_signal.emit(False)
                    return

                # 树结构校验：节点不应被访问两次
                if current_id in visited:
                    raise WorkflowError(
                        f"检测到循环：节点 '{current_id}' 被重复访问\n"
                        f"这不符合树结构，请检查 on_success / on_fail 配置")
                visited.add(current_id)

                node = nodes_map.get(current_id)
                if node is None:
                    raise WorkflowError(f"节点不存在: {current_id}")

                seq += 1
                wf_path = node.get("workflow", "")
                wf_name = node.get("name") or os.path.basename(wf_path)

                self.log_signal.emit(
                    f"\n=== [{seq}] {wf_name} ===")
                self.node_started.emit(seq - 1, wf_name)

                # 执行节点，捕获成功/失败
                success = True
                try:
                    self._run_one_workflow(wf_path, executor)
                except WorkflowError as e:
                    success = False
                    self.log_signal.emit(f"⚠️ 节点失败: {e}")
                except Exception as e:
                    success = False
                    tb = traceback.format_exc()
                    self.log_signal.emit(f"⚠️ 节点异常: {e}")
                    self.log_signal.emit(tb)

                self.node_finished.emit(seq - 1)

                # 判断是否被用户停止
                if self._stop_flag:
                    self.finished_signal.emit(False)
                    return

                # 决定下一个节点
                current_id = self._next_node(
                    node, nodes, seq - 1, success)

            self.log_signal.emit(f"\n✅ 编排执行完成")
            self.finished_signal.emit(True)

        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"❌ 编排异常: {e}")
            self.error_signal.emit(f"编排异常: {e}\n{tb}")
            self.finished_signal.emit(False)

    def _next_node(self, node, nodes, index, success):
        """
        决定下一个节点 id：
        - 有 on_success/on_fail 字段 → 按字段走（null = 结束）
        - 都没有 → 兼容旧格式，按数组顺序
        """
        has_success = "on_success" in node
        has_fail = "on_fail" in node

        if not has_success and not has_fail:
            # 兼容旧格式：成功就下一个，失败就结束
            if success and index + 1 < len(nodes):
                return nodes[index + 1].get("id")
            return None

        if success:
            nxt = node.get("on_success")
            self.log_signal.emit(
                f"   ↳ 成功 → "
                f"{'结束' if nxt is None else self._node_label(nodes, nxt)}")
            return nxt
        else:
            nxt = node.get("on_fail")
            self.log_signal.emit(
                f"   ↳ 失败 → "
                f"{'结束' if nxt is None else self._node_label(nodes, nxt)}")
            return nxt

    @staticmethod
    def _node_label(nodes, node_id):
        for n in nodes:
            if n.get("id") == node_id:
                return f"[{node_id}] {n.get('name', '')}"
        return node_id

    # ---- 执行单个原子工作流 ----
    def _run_one_workflow(self, wf_path, executor):
        if not os.path.isabs(wf_path):
            # 相对项目根（月亮副驾/），从 核心/ 往上两层
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(base, wf_path)
        else:
            full_path = wf_path

        if not os.path.exists(full_path):
            raise WorkflowError(f"工作流文件不存在: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            wf = json.load(f)

        steps = wf.get("steps", [])
        total = len(steps)

        for idx, step in enumerate(steps):
            if not self._wait_if_paused_or_stop():
                raise WorkflowError("执行被用户停止")

            if not step.get("enabled", True):
                self.log_signal.emit(
                    f"    [{idx+1}/{total}] 已禁用，跳过")
                continue

            step_name = step.get("name") or gen_step_name(step)
            self.log_signal.emit(f"    [{idx+1}/{total}] {step_name}")

            executor.execute(step)   # 异常向上抛

    def _wait_if_paused_or_stop(self):
        self._pause_event.wait()
        return not self._stop_flag