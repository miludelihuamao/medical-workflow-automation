# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 医嘱提取处理器】

用途：
    处理"12像素助手-医嘱提取"引擎的输出。
    自包含：列线切分 + 拼接。

列线：
    [53, 134, 334, 409, 489, 564, 684, 804, 924,
     989, 1074, 1129, 1204, 1304, 1744]  → 14 列

拼接：
    行内空格分隔，行间中文逗号。
================================================================
"""
from 核心.文本处理.处理器注册表 import 注册


列线默认 = [
    53, 134, 334, 409, 489, 564, 684, 804, 924,
    989, 1074, 1129, 1204, 1304, 1744
]


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


def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}
    列线 = 配置.get("lines", 列线默认)

    表 = _切表格(ocr结果, 列线)

    parts = []
    for row in 表:
        cells = row.get("cells", [])
        text = " ".join(c for c in cells if c)
        if text.strip():
            parts.append(text)
    final_text = "，".join(parts)

    return {
        "declared_type": "医嘱提取",
        "raw_text": "",
        "final_text": final_text,
        "paragraphs": [],
        "table": 表,
        "table_output": [],
        "table_final": [],
    }


注册("医嘱提取", 处理)