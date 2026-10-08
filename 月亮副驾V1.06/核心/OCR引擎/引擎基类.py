# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR引擎 / 引擎基类】

用途：
    OCR 引擎的抽象基类。所有具体的 OCR 引擎（16像素宋体、
    12像素助手、HIS特化）都继承它，保证接口一致。

职责：
    1. 定义统一的引擎接口（name / load / recognize）
    2. 提供 is_loaded() 供外部查询加载状态
    3. recognize() 是抽象方法，子类必须实现

对外接口（子类必须实现）：
    name                 类属性，显示在 UI 下拉框里的名称
    description          类属性，简要说明
    load(log=None)       加载模型/缓存
    recognize(source)    执行识别
                         source: 图片路径(str) 或 numpy 数组(BGR)
                         返回: 由引擎自定义（一般是 list）

被谁使用：
    - 核心/OCR引擎/16像素宋体.py
    - 核心/OCR引擎/12像素助手.py
    - 核心/OCR引擎/12像素HIS特化.py
    - 界面/功能面板/OCR面板.py      （通过 create_engines() 动态加载）
================================================================
"""


class BaseOcrEngine:
    name = "未命名引擎"
    description = ""

    # ★ 默认内容类型（整段 / 分段 / 表格）
    # 子类按需覆盖
    default_declared_type = "整段"
    processor = None    # 处理器名字；None 表示按 declared_type 走默认

    def __init__(self):
        self._loaded = False

    def load(self, log=None):
        self._loaded = True

    def is_loaded(self):
        return self._loaded

    def recognize(self, source, log=None, declared_type=None):
        """
        source: 图片路径(str) 或 numpy 数组(BGR)
        declared_type: 可选，覆盖默认类型
        返回: OCR结果 dict（详见 核心/OCR结果.py）
        """
        raise NotImplementedError