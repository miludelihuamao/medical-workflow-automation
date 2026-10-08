# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 检查结果处理器】

用途：
    处理"16像素助手-检查结果"引擎的输出。
    自包含：空行判断 + 最后一行去括号 + 拼接。

流程：
    1. 空行判断：有则只取最后一个空行之后的内容
    2. 最后一行去掉（...）或(...)
    3. 拼接：行末有标点直接连，无标点加"；"
================================================================
"""
import re
from 核心.文本处理.处理器注册表 import 注册


标点集合 = set("。！？；：，、,.!?;:")


def _展平行(ocr结果):
    所有行 = []
    for page in ocr结果.get("pages", []):
        for line in page.get("lines", []):
            所有行.append(line)
    所有行.sort(key=lambda x: x.get("y_mid", 0))
    return 所有行


def _处理空行(行列表, 倍数=1.8):
    if len(行列表) < 2:
        return 行列表
    间距列表 = []
    for i in range(1, len(行列表)):
        gap = 行列表[i].get("y1", 0) - 行列表[i-1].get("y2", 0)
        间距列表.append(gap)
    sorted_gaps = sorted(间距列表)
    中位数 = sorted_gaps[len(sorted_gaps) // 2]
    阈值 = 中位数 * 倍数
    最后空行索引 = -1
    for i, gap in enumerate(间距列表, start=1):
        if gap > 阈值:
            最后空行索引 = i
    if 最后空行索引 > 0:
        return 行列表[最后空行索引:]
    return 行列表


def _去掉括号内容(text):
    # 完整括号对
    text2 = re.sub(r'[（(][^（()）]*[）)]', '', text)
    # 孤立左括号
    text2 = re.sub(r'[（(][^（()）]*$', '', text2)
    return text2


def _处理最后一行(行列表):
    if not 行列表:
        return 行列表
    最后 = dict(行列表[-1])
    原 = 最后.get("text", "")
    新 = _去掉括号内容(原).strip()
    最后["text"] = 新
    if not 新:
        return 行列表[:-1]
    return 行列表[:-1] + [最后]


def _拼接(行列表):
    parts = []
    for line in 行列表:
        text = line.get("text", "").strip()
        if not text:
            continue
        if text[-1] in 标点集合:
            parts.append(text)
        else:
            parts.append(text + "；")
    return "".join(parts)


def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}
    所有行 = _展平行(ocr结果)
    if not 所有行:
        return {
            "declared_type": "检查结果",
            "raw_text": "", "final_text": "",
            "paragraphs": [], "table": [],
            "table_output": [], "table_final": [],
            "lines": [],
        }
    处理后行 = _处理空行(所有行, 配置.get("blank_ratio", 1.8))
    处理后行 = _处理最后一行(处理后行)
    拼接结果 = _拼接(处理后行)
    return {
        "declared_type": "检查结果",
        "raw_text": "",
        "final_text": 拼接结果,
        "lines": 处理后行,
        "paragraphs": [],
        "table": [],
        "table_output": [],
        "table_final": [],
    }


注册("检查结果", 处理)