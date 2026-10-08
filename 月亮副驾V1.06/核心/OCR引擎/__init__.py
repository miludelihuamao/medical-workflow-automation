# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR引擎 / 注册表】

用途：
    OCR 引擎的注册表。负责加载所有具体引擎类，
    并对外暴露 create_engines() 供界面调用。

职责：
    1. 用 importlib 动态加载 3 个引擎类
       （因为文件名以数字开头，不能用普通 import）
    2. 组装 ENGINES 列表
    3. create_engines() 返回 {名称: 实例}

被谁使用：
    - 界面/功能面板/OCR面板.py

注：
    引擎文件名：
        16像素宋体.py
        12像素助手.py
        12像素HIS特化.py
    类名：
        FontHashOcrEngine
        OCR12HelperEngine
        OCRHIS12Engine
================================================================
"""
import os
import importlib.util

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_engine(file_name, class_name):
    """从当前目录动态加载一个 .py 文件，取出里面的引擎类"""
    path = os.path.join(_THIS_DIR, file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"引擎文件不存在: {path}")
    spec = importlib.util.spec_from_file_location(class_name, path)
    if spec is None:
        raise ImportError(f"无法加载模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)


# ---- 加载所有引擎 ----
_ENGINE_CLASSES = []

try:
    FontHashOcrEngine = _load_engine("16像素宋体.py", "FontHashOcrEngine")
    _ENGINE_CLASSES.append(FontHashOcrEngine)
except Exception as e:
    print(f"⚠ OCR 引擎【16像素宋体】加载失败: {e}")

try:
    OCR12HelperEngine = _load_engine("12像素助手-检验结果.py", "OCR12HelperEngine")
    _ENGINE_CLASSES.append(OCR12HelperEngine)
except Exception as e:
    print(f"⚠ OCR 引擎【12像素助手】加载失败: {e}")

try:
    OCR12ProjectNameEngine = _load_engine(
        "12像素助手-检验结果-项目名称.py", "OCR12HelperProjectNameEngine")
    _ENGINE_CLASSES.append(OCR12ProjectNameEngine)
except Exception as e:
    print(f"⚠ OCR 引擎【12像素助手-检验结果-项目名称】加载失败: {e}")

try:
    OCR16CheckResultEngine = _load_engine(
        "16像素助手-检查结果.py", "OCR16CheckResultEngine")
    _ENGINE_CLASSES.append(OCR16CheckResultEngine)
except Exception as e:
    print(f"⚠ OCR 引擎【16像素助手-检查结果】加载失败: {e}")

try:
    OCR12OrderExtractEngine = _load_engine(
        "12像素助手-医嘱提取.py", "OCR12OrderExtractEngine")
    _ENGINE_CLASSES.append(OCR12OrderExtractEngine)
except Exception as e:
    print(f"⚠ OCR 引擎【12像素助手-医嘱提取】加载失败: {e}")

try:
    OCRHIS12Engine = _load_engine("12像素HIS特化.py", "OCRHIS12Engine")
    _ENGINE_CLASSES.append(OCRHIS12Engine)
except Exception as e:
    print(f"⚠ OCR 引擎【12像素HIS特化】加载失败: {e}")

try:
    OCR12ScanEngine = _load_engine("12像素OCR.py", "OCR12ScanEngine")
    _ENGINE_CLASSES.append(OCR12ScanEngine)
except Exception as e:
    print(f"⚠ OCR 引擎【12像素OCR】加载失败: {e}")

def create_engines():
    """创建所有引擎实例，返回 {名称: 实例}"""
    return {cls.name: cls() for cls in _ENGINE_CLASSES}