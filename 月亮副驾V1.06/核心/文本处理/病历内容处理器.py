# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 病历内容处理器】

用途：
    处理"病历16像素宋体"引擎的输出。
    暂时不做分段等特殊处理，直接把所有行按 y 坐标从上到下输出。

输入：
    OCR 结果（病历16像素宋体 引擎产出）

输出：
    {
        "declared_type": "病历内容",
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
处理器名 = "病历内容"


def _展平行(ocr结果):
    """
    按页顺序遍历，每页内部按 y_mid 排序。
    不要跨页全局排序——两页的 y 坐标系不同。
    """
    所有行 = []
    for page in ocr结果.get("pages", []):
        page_lines = page.get("lines", [])
        page_lines = sorted(page_lines, key=lambda x: x.get("y_mid", 0))
        所有行.extend(page_lines)
    return 所有行


def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}

    # 1. 拿所有行
    所有行 = _展平行(ocr结果)

    # 2. 过滤空行
    有效行 = [l for l in 所有行 if l.get("text", "").strip()]

    # 3. 拼接为整体文本（每行一行）
    文本列表 = [l.get("text", "") for l in 有效行]
    final_text = "\n".join(文本列表)

    return {
        "declared_type": "病历内容",
        "raw_text": "",
        "final_text": final_text,
        "paragraphs": [],
        "table": [],
        "table_output": [],
        "table_final": [],
        "items": [],
        "lines": 有效行,        # ★ 保留行列表，供界面渲染
    }


# 自动注册
注册(处理器名, 处理)