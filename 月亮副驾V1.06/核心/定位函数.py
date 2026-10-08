# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 定位函数】

用途：
    图像模板匹配。在给定的"当前画面"里查找模板图片的位置。
    这是所有"图像定位"步骤的底层实现。

职责：
    1. 从模板文件读取图片（支持中文路径）
    2. 在 screenshot_func() 返回的画面里逐帧查找
    3. 达到置信度阈值就返回位置，超时返回 None

对外接口：
    locate(img_path, screenshot_func, confidence, timeout, region)
        img_path:        模板图片路径
        screenshot_func: 无参函数，返回当前画面 numpy 数组
        confidence:      匹配阈值 0~1
        timeout:         最长等待秒数
        region:          (rx, ry, rw, rh) 搜索区域，None 表示全图
        返回:            (x, y, w, h) 或 None

被谁使用：
    - 界面/执行面板.py          （注入给工作流引擎）
    - 核心/工作流引擎.py        （通过注入的 locate_func 调用）

注：
    这是"通用模板匹配"，不涉及具体字体。
    字体识别（OCR）在 核心/OCR引擎/ 下单独实现。
================================================================
"""
import cv2
import numpy as np
import time
import os


def imread_chinese(path):
    """支持中文路径读取图片"""
    try:
        with open(path, 'rb') as f:
            data = np.frombuffer(f.read(), np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"读取图片失败: {path} - {e}")
        return None


def locate(img_path, screenshot_func, confidence=0.95, timeout=10, region=None):
    """
    基础模板匹配

    参数:
        img_path: 模板图片路径（支持中文）
        screenshot_func: 无参函数，返回当前画面 (H, W, 3) 的 numpy 数组，失败返回 None
        confidence: 匹配阈值 0~1
        timeout: 最大等待秒数
        region: (rx, ry, rw, rh) 搜索区域，None 表示全图

    返回:
        (x, y, w, h) 匹配框左上角坐标和模板尺寸；失败返回 None
    """
    name = os.path.basename(img_path)
    tpl = imread_chinese(img_path)
    if tpl is None:
        print(f"❌ 模板读取失败: {name}")
        return None
    h_tpl, w_tpl = tpl.shape[:2]

    start = time.time()
    max_val = 0.0
    while time.time() - start < timeout:
        frame = screenshot_func()
        if frame is None:
            time.sleep(0.5)
            continue

        rx, ry = 0, 0
        if region:
            rx, ry, rw, rh = region
            if ry + rh > frame.shape[0] or rx + rw > frame.shape[1]:
                time.sleep(0.5)
                continue
            search = frame[ry:ry + rh, rx:rx + rw]
        else:
            search = frame

        if w_tpl > search.shape[1] or h_tpl > search.shape[0]:
            time.sleep(0.5)
            continue

        res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= confidence:
            x, y = max_loc[0] + rx, max_loc[1] + ry
            print(f"✅ {name} 匹配成功，匹配度:{max_val:.3f}，坐标({x},{y})")
            return (x, y, w_tpl, h_tpl)

        time.sleep(0.5)

    print(f"❌ {name} 匹配超时，未找到，最高匹配度:{max_val:.3f}")
    return None