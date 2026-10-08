# -*- coding: utf-8 -*-
"""
硬件包初始化
动态加载中文文件名模块，并导出常用类
"""
import os
import importlib.util


def _load_module(file_name, module_alias):
    """从当前包目录加载一个 .py 文件为模块对象"""
    path = os.path.join(os.path.dirname(__file__), file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"模块文件不存在: {path}")
    spec = importlib.util.spec_from_file_location(module_alias, path)
    if spec is None:
        raise ImportError(f"无法加载模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- 采集卡全局帧缓存 ----
try:
    _fb_mod = _load_module("采集卡帧缓存.py", "采集卡帧缓存")
    FrameBuffer = _fb_mod.FrameBuffer
except Exception as e:
    FrameBuffer = None
    print(f"⚠ 硬件包加载 采集卡帧缓存 失败: {e}")