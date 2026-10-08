# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR结果】

用途：
    定义 OCR 输出的统一数据结构（dict 形式），并提供读取工具。
    坐标永久保存在内存里，只在界面显示时才隐藏。

数据结构：

    OCR结果 = {
        "source": "文件路径 或 采集卡",
        "engine": "16像素宋体",
        "declared_type": "分段",            # 整段 / 分段 / 表格
        "timestamp": 1234567890.123,
        "pages": [OCR页面, ...],
    }

    OCR页面 = {
        "index": 0,
        "width": 1920, "height": 1080,
        "lines": [OCR行, ...],
    }

    OCR行 = {
        "text": "鉴别诊断：",
        "y_mid": 108,                       # 同一行字符共用
        "y1": 100, "y2": 116,
        "x1": 50, "x2": 200,
        "chars": [OCR字符, ...],
    }

    OCR字符 = {
        "ch": "鉴",
        "x1": 50, "x2": 66,
    }

被谁使用：
    - 核心/OCR缓存.py
    - 核心/OCR引擎/*.py
    - 核心/文本处理/*.py
    - 界面/功能面板/OCR面板.py
================================================================
"""
import time


def make_result(source, engine, declared_type, pages, processor=None):
    return {
        "source": source,
        "engine": engine,
        "declared_type": declared_type,
        "processor": processor,
        "timestamp": time.time(),
        "pages": pages,
    }


def make_page(index, width, height, lines):
    return {
        "index": index,
        "width": width,
        "height": height,
        "lines": lines,
    }


def make_line(text, y_mid, y1, y2, x1, x2, chars):
    return {
        "text": text,
        "y_mid": y_mid,
        "y1": y1, "y2": y2,
        "x1": x1, "x2": x2,
        "chars": chars,
    }


def make_char(ch, x1, x2):
    return {"ch": ch, "x1": x1, "x2": x2}


# ==================== 读取工具 ====================
def get_all_text(result):
    """把所有页所有行的文本拼起来（用于快速查看）"""
    parts = []
    for page in result.get("pages", []):
        for line in page.get("lines", []):
            parts.append(line.get("text", ""))
    return "\n".join(parts)


def get_all_lines(result):
    """展平所有页的行（用于分段器 / 表格解析器）"""
    lines = []
    for page in result.get("pages", []):
        lines.extend(page.get("lines", []))
    return lines