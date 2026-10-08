# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 文本处理 / 处理调度器】

用途：
    统一处理入口。
    1. 优先看 OCR 结果里的 processor 名字 → 找注册过的处理器
    2. 找不到处理器 → 显示提示，不做处理

架构：
    每个引擎在 OCR 结果里声明 processor 名字（如"检验结果"），
    对应的处理器文件末尾调用 注册("检验结果", 处理) 自己登记。
    调度器按名字找人。
================================================================
"""
from 核心.文本处理 import 处理器注册表


def 处理(ocr结果, 配置=None):
    if 配置 is None:
        配置 = {}

    # 拿 processor 名字
    processor_name = 配置.get("processor") or ocr结果.get("processor")

    if processor_name:
        fn = 处理器注册表.获取(processor_name)
        if fn is not None:
            try:
                return fn(ocr结果, 配置)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"[处理调度器] 处理器 {processor_name} 执行失败: {e}\n{tb}")
                return {
                    "declared_type": processor_name,
                    "final_text": f"（处理器执行失败：{e}）",
                    "paragraphs": [],
                    "table": [],
                    "table_output": [],
                    "table_final": [],
                    "items": [],
                    "lines": [],
                }
        else:
            print(f"[处理调度器] 未找到处理器: {processor_name}")
            return {
                "declared_type": processor_name,
                "final_text": f"（未找到处理器：{processor_name}）",
                "paragraphs": [],
                "table": [],
                "table_output": [],
                "table_final": [],
                "items": [],
                "lines": [],
            }

    # 没有 processor 字段 → 什么也不做
    print("[处理调度器] OCR 结果没有 processor 字段，跳过处理")
    return {
        "declared_type": "未指定",
        "final_text": "",
        "paragraphs": [],
        "table": [],
        "table_output": [],
        "table_final": [],
        "items": [],
        "lines": [],
    }