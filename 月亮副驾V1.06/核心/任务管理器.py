# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 任务管理器】

用途：
    读写任务配置文件（数据/任务配置.json），
    提供任务的增删改查接口。
    "任务"是主界面上显示的按钮，每个按钮指向一个工作流或编排。

职责：
    1. 从 JSON 加载任务列表
    2. 保存任务列表回 JSON
    3. 提供 添加 / 更新 / 删除 / 上移 / 下移 接口

任务数据结构：
    {
        "name":        "进入**系统",                      # 按钮显示名
        "description": "登录**系统",                  # 按钮副标题（可选）
        "workflow":    "数据/工作流/1.进入**.json"    # 指向工作流或编排
    }

被谁使用：
    - 界面/主窗口.py            （渲染任务按钮）
    - 界面/任务配置窗口.py       （编辑任务列表）
================================================================
"""
import os
import json


# 任务配置文件路径：月亮副驾/数据/任务配置.json
TASKS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "数据", "任务配置.json")


class TaskManager:
    def __init__(self):
        self.tasks = []
        self.load()

    # ==================== 读写 ====================
    def load(self):
        """加载任务配置；文件不存在则视为空列表"""
        if not os.path.exists(TASKS_FILE):
            self.tasks = []
            return
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = data.get("tasks", [])
        except Exception as e:
            print(f"[TaskManager] 加载失败: {e}")
            self.tasks = []

    def save(self):
        """保存任务配置"""
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        data = {"tasks": self.tasks}
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ==================== 增删改 ====================
    def get_all(self):
        return list(self.tasks)

    def add(self, name, description, workflow):
        self.tasks.append({
            "name": name,
            "description": description,
            "workflow": workflow,
        })

    def update(self, index, name, description, workflow):
        if 0 <= index < len(self.tasks):
            self.tasks[index] = {
                "name": name,
                "description": description,
                "workflow": workflow,
            }

    def remove(self, index):
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)

    def move_up(self, index):
        if 0 < index < len(self.tasks):
            self.tasks[index], self.tasks[index - 1] = \
                self.tasks[index - 1], self.tasks[index]

    def move_down(self, index):
        if 0 <= index < len(self.tasks) - 1:
            self.tasks[index], self.tasks[index + 1] = \
                self.tasks[index + 1], self.tasks[index]