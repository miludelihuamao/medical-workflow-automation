# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 检验结果处理器】
================================================================
"""
import re
import base64
import numpy as np
from 核心.文本处理.处理器注册表 import 注册


# ==================== ★★★ 规则配置区 ★★★ ====================

# 【A1】项目名黑名单
规则_项目名黑名单 = [
    "结果解释",
    "尿素:肌酐",
    "渗透压",
]

# 【A2】项目名特殊替换
规则_项目名替换 = {
    "正常菌群": "正常菌群；",
    "未见真菌": "未见真菌；",
    "无菌生长": "无菌生长；",
}

# 【A3】项目名跳过（专家评语）
规则_项目名跳过 = ["专家评语"]

# 【A4】项目名 + 结果 组合跳过
#   （项目名匹配时去空格，结果匹配时去空格 + 大写）
规则_组合跳过 = [
    # 颜色 + 含"黄"
    {"项目": "颜色",     "结果包含": ["黄"]},
    # 浊度 + CLEAR
    {"项目": "浊度",     "结果等于": ["CLEAR"]},
    # 大便颜色 + 含"黄"或"绿"
    {"项目": "大便颜色", "结果包含": ["黄", "绿"]},
    # 大便性状 + 含"软"、"稀"、"糊"
    {"项目": "大便性状", "结果包含": ["软", "稀", "糊"]},
    # 小圆上皮细胞 / 类酵母菌 / 结晶 + "无"
    {"项目": "小圆上皮细胞", "结果等于": ["无"]},
    {"项目": "类酵母菌",     "结果等于": ["无"]},
    {"项目": "结晶",         "结果等于": ["无"]},
]

# 【A5】结果无条件的跳过
规则_结果跳过词 = ["未见"]          # 结果含"未见" → 跳过
规则_结果跳过值_单个 = ["无"]       # 结果去空格后恰好是"无" → 跳过

# 【B】带菌药敏
带菌项目特征 = "菌"
药敏结果值 = ["S", "I", "R"]
药敏提示文字 = "（自行查看检验结果页面耐药性）"

# 【C】阴阳
规则_阴性词 = ["阴性", "-", "(-)", "阴"]
规则_阳性词 = ["阳性", "+", "++", "+++", "++++", "±"]

# 【D】结果为空时替换
规则_结果为空替换 = "正常结果；"

列线默认 = [514, 1030, 1220, 1403, 1669, 1720]
备注列默认 = [1669, 1720]

# ==================== 规则配置区结束 ====================


# ==================== 工具 ====================
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


def _规范化(s):
    """去所有空格 + 大写"""
    return str(s).replace(" ", "").replace("　", "").upper()


def _解析数值(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    s2 = re.sub(r"[^\d.\-+]", "", s)
    try:
        return float(s2)
    except Exception:
        return None


def _解析参考范围(ref_str):
    if not ref_str:
        return None
    s = str(ref_str).strip()
    m = re.match(r"^[>≥]\s*(-?\d+\.?\d*)", s)
    if m:
        return (_解析数值(m.group(1)), None)
    m = re.match(r"^[<≤]\s*(-?\d+\.?\d*)", s)
    if m:
        return (None, _解析数值(m.group(1)))
    m = re.match(r"^(-?\d+\.?\d*)\s*[-~至]\s*(-?\d+\.?\d*)", s)
    if m:
        return (_解析数值(m.group(1)), _解析数值(m.group(2)))
    v = _解析数值(s)
    if v is not None:
        return (v, v)
    return None


def _清理参考范围(s):
    if not s:
        return s
    s = str(s).strip()
    s = s.replace('－', '-').replace('＞', '>').replace('＜', '<')
    s = s.replace('（', '(').replace('）', ')')
    s = s.replace('(-)', '§NEG§')
    if '-' in s and ('>' in s or '<' in s):
        s = s.replace('-', '')
    s = re.sub(r'[><]\s*-', '', s)
    s = re.sub(r'-\s*[><]', '', s)
    s = re.sub(r'(\d)-(\d)', r'\1§DASH§\2', s)
    s = s.replace('-', '')
    s = s.replace('§DASH§', '-')
    s = s.replace('§NEG§', '(-)')
    return s


def _获取掩码(foreground):
    if foreground is None:
        return None
    if "_mask" in foreground:
        return foreground["_mask"]
    try:
        h = foreground["h"]
        w = foreground["w"]
        packed = np.frombuffer(
            base64.b64decode(foreground["packed_b64"]), dtype=np.uint8)
        mask = np.unpackbits(packed)[: h * w].reshape(h, w)
        foreground["_mask"] = mask
        return mask
    except Exception:
        return None


def _有像素(y_abs, x1_abs, x2_abs, foreground):
    mask = _获取掩码(foreground)
    if mask is None:
        return False
    y = y_abs - foreground["y_offset"]
    x1 = x1_abs - foreground["x_offset"]
    x2 = x2_abs - foreground["x_offset"]
    h, w = mask.shape
    if y < 0 or y >= h:
        return False
    x1 = max(0, x1)
    x2 = min(w - 1, x2)
    if x1 > x2:
        return False
    y1 = max(0, y - 3)
    y2 = min(h - 1, y + 3)
    return bool(mask[y1:y2+1, x1:x2+1].any())


def _参考是阴性(参考):
    s = str(参考).strip().replace('（', '(').replace('）', ')')
    if not s:
        return False
    if s in 规则_阴性词:
        return True
    if '阴性' in s:
        return True
    s2 = _清理参考范围(s)
    if s2 in 规则_阴性词:
        return True
    return False


def _结果是阴性(结果):
    s = str(结果).strip()
    if s in 规则_阴性词:
        return True
    if '阴性' in s:
        return True
    return False


def _结果是阳性(结果):
    s = str(结果).strip()
    for kw in 规则_阳性词:
        if kw == "+":
            if s in ("+", "++", "+++", "++++"):
                return True
        elif kw in s:
            return True
    return False


def _含汉字(s):
    return bool(re.search(r'[\u4e00-\u9fff]', str(s)))


# ==================== ★ 组合跳过判断 ====================
def _命中组合跳过(项目, 结果):
    """
    规范化匹配：项目名去空格后比较，结果去空格+大写后比较。
    """
    项目n = _规范化(项目)
    结果n = _规范化(结果)

    for 规则 in 规则_组合跳过:
        目标项目 = _规范化(规则["项目"])
        if 项目n != 目标项目:
            continue
        # 结果包含某个词
        for kw in 规则.get("结果包含", []):
            if kw in str(结果):
                return True
        # 结果等于某个值（规范化比较）
        for kw in 规则.get("结果等于", []):
            if 结果n == _规范化(kw):
                return True
    return False


# ==================== 核心：分析单行 ====================
def _分析一行(项目, 结果, 单位, 参考, y_mid, foreground, mark_range,
             药敏已输出):

    # ==================== E 组：备注像素标记 ====================
    if foreground is not None:
        if _有像素(y_mid, mark_range[0], mark_range[1], foreground):
            return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": "标记"}

    # ==================== A1 组：项目名黑名单 ====================
    for kw in 规则_项目名黑名单:
        if kw in 项目:
            return None

    # ==================== A3 组：项目名跳过 ====================
    for kw in 规则_项目名跳过:
        if kw in 项目:
            return None

    # ==================== A4 组：项目名 + 结果 组合跳过 ====================
    if _命中组合跳过(项目, 结果):
        return None

    # ==================== A5 组：结果无条件跳过 ====================
    # 含"未见"
    for kw in 规则_结果跳过词:
        if kw in str(结果):
            return None
    # 恰好是"无"
    if str(结果).strip() in 规则_结果跳过值_单个:
        return None

    # ==================== A2 组：项目名特殊替换 ====================
    for kw, 替换值 in 规则_项目名替换.items():
        if kw in 项目:
            return {"项目": 项目, "结果": 替换值, "单位": 单位, "状态": ""}

    # ==================== B 组：带菌药敏 ====================
    结果_清理 = str(结果).strip().upper()
    if 带菌项目特征 in 项目 and 结果_清理 in 药敏结果值:
        if 项目 in 药敏已输出:
            return None
        药敏已输出.add(项目)
        return {"项目": 项目 + 药敏提示文字, "结果": "", "单位": "",
                "状态": "有菌"}

    # ==================== D1 组：参考为空 ====================
    if not 参考 or not 参考.strip():
        if 结果 and 结果.strip():
            return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": ""}
        return None

    # ==================== C2 组：双阴性 ====================
    if _参考是阴性(参考) and _结果是阴性(结果):
        return None

    # ==================== C3 组：阳性 ====================
    if _结果是阳性(结果):
        return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": "阳性"}

    # ==================== D2 组：数值型 ====================
    参考清理 = _清理参考范围(参考)
    数值 = _解析数值(结果)
    if 数值 is not None:
        范围 = _解析参考范围(参考清理)
        if 范围 is not None:
            low, high = 范围
            if low is not None and 数值 < low:
                return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": "↓"}
            if high is not None and 数值 > high:
                return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": "↑"}
            return None
        return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": ""}

    # ==================== D3 组：汉字对比 ====================
    if _含汉字(结果):
        if str(结果).strip() != str(参考清理).strip():
            return {"项目": 项目, "结果": 结果, "单位": 单位, "状态": "异常"}

    return None


# ==================== 主入口 ====================
def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}

    列线 = 配置.get("lines", 列线默认)
    备注区间 = 配置.get("mark_range", 备注列默认)

    foreground = None
    for page in ocr结果.get("pages", []):
        if "foreground" in page:
            foreground = page["foreground"]
            break

    表 = _切表格(ocr结果, 列线)

    有效行 = []
    for row in 表:
        cells = row["cells"]
        if len(cells) < 5:
            continue
        项目 = cells[0].strip()
        结果 = cells[1].strip()
        单位 = cells[2].strip()
        参考 = cells[3].strip()
        if not 项目 or 项目 in ("项目名称", "项目"):
            continue
        if not 结果:
            continue
        有效行.append((项目, 结果, 单位, 参考, row["y_mid"]))

    只有1行 = (len(有效行) == 1)

    药敏已输出 = set()
    分析输出 = []
    for 项目, 结果, 单位, 参考, y_mid in 有效行:
        输出 = _分析一行(项目, 结果, 单位, 参考, y_mid,
                         foreground, 备注区间, 药敏已输出)
        if 输出 is not None:
            分析输出.append(输出)

    过滤后 = 分析输出

    parts = []
    for it in 过滤后:
        项目 = it["项目"]
        结果 = it["结果"]
        单位 = it["单位"]
        状态 = it.get("状态", "")

        if not 结果 and 状态 != "有菌":
            结果 = 规则_结果为空替换

        if 只有1行 and 状态 != "有菌":
            text = f"{结果}{单位}".strip()
        else:
            text = f"{项目} {结果}{单位}".strip()

        if text:
            parts.append(text)

    final_text = "，".join(parts)

    return {
        "declared_type": "检验结果",
        "raw_text": "",
        "final_text": final_text,
        "paragraphs": [],
        "table": 表,
        "table_output": 分析输出,
        "table_final": 过滤后,
        "items": 过滤后,
    }


# 自动注册
注册("检验结果", 处理)