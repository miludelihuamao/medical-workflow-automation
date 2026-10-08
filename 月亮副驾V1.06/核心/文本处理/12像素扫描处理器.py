# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 12像素扫描处理器】

用途：
    处理"12像素OCR"引擎的输出。
    直接把识别到的所有行按 y 坐标从上到下输出，不做任何列切分或过滤。

输入：
    OCR 结果（12像素OCR 引擎产出）
    page.lines = [{text, y_mid, y1, y2, x1, x2, chars}, ...]

输出：
    {
        "declared_type": "12像素扫描",
        "lines": [原始行],
        "final_text": "每行一行文本",
        ...
    }

对外接口：
    处理(ocr结果, 配置=None)
================================================================
"""
from 核心.文本处理.处理器注册表 import 注册


# ==================== 注册名（要和引擎的 processor 一致）====================
处理器名 = "12像素扫描"


def _展平行(ocr结果):
    """把所有页的所有行展平，按 y_mid 升序排序"""
    所有行 = []
    for page in ocr结果.get("pages", []):
        for line in page.get("lines", []):
            所有行.append(line)
    所有行.sort(key=lambda x: x.get("y_mid", 0))
    return 所有行


def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}

    # 1. 拿所有行
    所有行 = _展平行(ocr结果)

    # 2. 过滤空行（可选：如果你想保留空行，注释掉这段）
    有效行 = [l for l in 所有行 if l.get("text", "").strip()]

    # 3. 拼接为整体文本（每行一行）
    文本列表 = [l.get("text", "") for l in 有效行]
    final_text = "\n".join(文本列表)

    return {
        "declared_type": "12像素扫描",
        "raw_text": "",
        "final_text": final_text,
        "paragraphs": [],
        "table": [],
        "table_output": [],
        "table_final": [],
        "items": [],
        "lines": 有效行,        # ★ 保留行列表，供界面渲染
    }


# 自动注册（名字要和引擎的 processor 一致）
注册(处理器名, 处理)