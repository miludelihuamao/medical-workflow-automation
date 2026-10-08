# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR缓存】

用途：
    全局 OCR 结果缓存。
      - 内存缓存：始终开启，程序关闭时自动消失
      - 落盘：默认关闭，可在后续 GUI 中打开
      - 清理：删除超过 3 天的落盘文件（程序启动 + 每次落盘时扫）

对外接口：
    OCR缓存.get_instance()         单例
    store.set(result)              写入内存
    store.get()                    读取内存
    store.set_disk_enabled(bool)   打开/关闭落盘
    store.save_to_disk(result)     落盘（若开关开）
    store.scan_and_clean()         清理过期文件
================================================================
"""
import os
import json
import time
import threading


# 过期时间：3 天
EXPIRE_SECONDS = 3 * 24 * 3600


class OCR缓存:
    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = OCR缓存()
        return cls._instance

    def __init__(self):
        self._lock = threading.Lock()
        self._last_result = None

        # 数据/OCR结果/ 目录
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._save_dir = os.path.join(base, "数据", "OCR结果")

        # 落盘开关（默认关闭）
        self._disk_enabled = False

    # ==================== 内存缓存 ====================
    def set(self, result):
        with self._lock:
            self._last_result = result

    def get(self):
        with self._lock:
            return self._last_result

    def clear(self):
        with self._lock:
            self._last_result = None

    # ==================== 落盘 ====================
    def set_disk_enabled(self, enabled):
        self._disk_enabled = bool(enabled)

    def is_disk_enabled(self):
        return self._disk_enabled

    def save_to_disk(self, result):
        if not self._disk_enabled:
            return
        try:
            os.makedirs(self._save_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            path = os.path.join(self._save_dir, f"{ts}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            # 顺手清理一次
            self.scan_and_clean()
        except Exception as e:
            print(f"[OCR缓存] 落盘失败: {e}")

    # ==================== 清理 ====================
    def scan_and_clean(self):
        """删除 数据/OCR结果/ 下超过 3 天的文件"""
        if not os.path.isdir(self._save_dir):
            return
        now = time.time()
        for fname in os.listdir(self._save_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._save_dir, fname)
            try:
                mtime = os.path.getmtime(path)
                if now - mtime > EXPIRE_SECONDS:
                    os.remove(path)
                    print(f"[OCR缓存] 已清理过期文件: {fname}")
            except Exception as e:
                print(f"[OCR缓存] 清理失败 {fname}: {e}")