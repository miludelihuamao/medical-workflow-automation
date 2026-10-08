# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 检验结果项目名称处理器】

用途：
    处理"12像素助手-检验结果-项目名称"引擎的输出。
    自包含：列线切分 + 名称括号过滤。

列线：
    [91, 208, 360] → 两列
        时间 [91, 208)
        名称 [208, 360)

过滤规则：
    - 无（或( → 返回原样
    - 有（ 无） → 去（及其后
    - 有（ ））后无中文字符 → 去（及其后
    - 有（ ））后有中文字符 → 返回原样
================================================================
"""
import re
from 核心.文本处理.处理器注册表 import 注册


列线默认 = [91, 208, 360]


# ==================== 工具：列线切分（本地版，不依赖外部）====================
def _展平行(ocr结果):
    所有行 = []
    for page in ocr结果.get("pages", []):
        for line in page.get("lines", []):
            所有行.append(line)
    所有行.sort(key=lambda x: x.get("y_mid", 0))
    return 所有行


def _找区间(cx, 列线):
    for i in range(len(列线) - 1):
        if 列线[i] <= cx < 列线[i + 1]:
            return i
    return -1


def _切表格(ocr结果, 列线):
    列数 = len(列线) - 1
    表 = []
    for line in _展平行(ocr结果):
        分桶 = [[] for _ in range(列数)]
        for c in line.get("chars", []):
            cx = (c.get("x1", 0) + c.get("x2", 0)) // 2
            idx = _找区间(cx, 列线)
            if idx >= 0:
                分桶[idx].append(c)
        cells = []
        for bucket in 分桶:
            bucket.sort(key=lambda c: c.get("x1", 0))
            cells.append("".join(c.get("ch", "") for c in bucket))
        表.append({"y_mid": line.get("y_mid", 0), "cells": cells})
    return 表


# ==================== 名称过滤 ====================
def _过滤名称(name):
    name = name.strip()
    if not name:
        return name

    # 找全角或半角左括号
    idx = -1
    for ch in ("（", "("):
        p = name.find(ch)
        if p >= 0 and (idx < 0 or p < idx):
            idx = p
    if idx < 0:
        return name

    # 找右括号（与左括号同类型）
    left = name[idx]
    right = "）" if left == "（" else ")"
    r_idx = name.find(right, idx)
    if r_idx < 0:
        return name[:idx].strip()

    after = name[r_idx + 1:]
    if re.search(r'[\u4e00-\u9fff]', after):
        return name
    return name[:idx].strip()


# ==================== 主入口 ====================
def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}
    列线 = 配置.get("lines", 列线默认)

    表 = _切表格(ocr结果, 列线)
    items = []

    for row in 表:
        cells = row["cells"]
        if len(cells) < 2:
            continue
        时间 = cells[0].strip()
        名称 = cells[1].strip()
        if not 名称:
            continue
        名称 = _过滤名称(名称)
        if not 名称:
            continue
        items.append({"时间": 时间, "名称": 名称})

    final_text = "，".join(f"{it['时间']} {it['名称']}" for it in items)

    return {
        "declared_type": "项目名称表",
        "raw_text": "",
        "final_text": final_text,
        "paragraphs": [],
        "table": 表,
        "table_output": [],
        "table_final": [],
        "items": items,
    }


# 自动注册
注册("检验结果项目名称", 处理)