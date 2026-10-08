# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 处理器注册表】

用途：
    处理器的全局注册表。
    每个处理器放在 核心/文本处理/ 下，文件名以 "处理器.py" 结尾。
    文件末尾自己调用 注册("名字", 处理函数)。
    调度器按名字取。

    第一次使用时惰性扫描目录，把所有 *处理器.py 加载一遍。

对外接口：
    注册(name, fn)         处理器自己调用
    获取(name)             调度器调用
    列出所有()             调试用
================================================================
"""
import os
import importlib.util


_注册表 = {}
_已加载 = False


def 注册(name, fn):
    _注册表[name] = fn


def 列出所有():
    _确保已加载()
    return list(_注册表.keys())


def 获取(name):
    _确保已加载()
    return _注册表.get(name)


def _确保已加载():
    global _已加载
    if _已加载:
        return
    _已加载 = True
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in os.listdir(this_dir):
        if not fname.endswith("处理器.py"):
            continue
        if fname == "处理器注册表.py":
            continue
        path = os.path.join(this_dir, fname)
        try:
            mod_name = fname[:-3]   # 去掉 .py
            spec = importlib.util.spec_from_file_location(mod_name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # 模块末尾自己调用了 注册()
        except Exception as e:
            print(f"[处理器注册表] 加载 {fname} 失败: {e}")