# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR引擎 / 12像素助手-检验结果】

用途：
    识别 HIS 检验结果页面表格的 12 像素字体。
    只识别数据区域（不含表头），ROI 固定。

ROI 范围（硬编码）：
    y ∈ [146, 1031]
    x ∈ [514, 1720]

职责：
    1. 裁剪 ROI
    2. 颜色掩码（只保留 TARGET_COLORS_BGR 里定义的颜色像素）
    3. 行检测（高度严格 = 12）
    4. 逐行识别字符
    5. 输出 OCR 结果 dict，附带"前景掩码"（供表格分析器查像素）

对外接口：
    recognize(source, log=None, declared_type=None)
        → OCR结果 dict
        page 里多一个 "foreground" 字段：
            {
                "y_offset": 146,    # ROI 在原图里的偏移
                "x_offset": 514,
                "h": 885, "w": 1206,
                "packed_b64": "...",   # np.packbits 后 base64
            }

默认内容类型：表格
================================================================
"""
import cv2
import numpy as np
import time
import os
import pickle
import base64
from numpy.lib.stride_tricks import sliding_window_view

from 核心.OCR引擎.引擎基类 import BaseOcrEngine
from 核心.OCR结果 import make_result, make_page, make_line, make_char


def packed_to_uint64_keys(packed):
    n, n_bytes = packed.shape
    n_parts = (n_bytes + 7) // 8
    padded = np.zeros((n, n_parts * 8), dtype=np.uint8)
    padded[:, :n_bytes] = packed
    dtype = np.dtype([(f"p{i}", "<u8") for i in range(n_parts)])
    return padded.view(dtype).reshape(-1)


class OCR12HelperEngine(BaseOcrEngine):
    name = "12像素助手-检验结果"
    description = "HIS 检验结果表格（12像素，限定 ROI）"
    default_declared_type = "表格"
    processor = "检验结果"

    CACHE_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "数据", "字库缓存", "12像素宋体", "font_hash_cache_12x12.pkl")

    TEMPLATE_HEIGHT = 12
    EXPAND_X = 6
    MIN_ROW_PIXELS = 1
    LINE_HEIGHT_EXACT = 12
    TIGHT_TEMPLATES = False
    BLACKLIST = {"丨", "|"}

    TARGET_COLORS_BGR = [
        (1, 1, 255), (53, 31, 32), (1, 128, 128), (60, 51, 11),
        (1, 1, 1), (255, 1, 1), (128, 1, 155),
        (52, 30, 31),   # ★ 新增：采集卡漂移后的深灰
    ]

    # ★ ROI 范围（只识别这块区域）
    ROI_Y1 = 146
    ROI_Y2 = 1031
    ROI_X1 = 514
    ROI_X2 = 1720

    DEBUG_MODE = False

    def __init__(self):
        super().__init__()
        self.width_to_hash = None
        self.possible_widths = None

    # ==================== 加载缓存 ====================
    def load(self, log=None):
        if self._loaded:
            return
        if not os.path.exists(self.CACHE_FILE):
            raise FileNotFoundError(f"缓存文件不存在：{self.CACHE_FILE}")
        if log: log(f"加载缓存：{self.CACHE_FILE}")
        t0 = time.perf_counter()
        with open(self.CACHE_FILE, "rb") as f:
            raw_cache = pickle.load(f)
        self.width_to_hash = {}
        for w, (str_keys, chars) in raw_cache.items():
            str_keys = np.asarray(str_keys)
            if str_keys.size == 0:
                continue
            chars = np.asarray(chars)
            n_bytes = str_keys.dtype.itemsize
            packed = str_keys.view(np.uint8).reshape(-1, n_bytes)
            keys = packed_to_uint64_keys(packed)
            order = np.argsort(keys, kind="stable")
            self.width_to_hash[w] = (keys[order], chars[order])
        self.possible_widths = sorted(self.width_to_hash.keys())
        if log: log(f"缓存加载完成，耗时 {time.perf_counter()-t0:.3f}s")
        self._loaded = True

    # ==================== 图片IO ====================
    @staticmethod
    def _imread_unicode(path):
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    def _load_image(self, source):
        if isinstance(source, np.ndarray):
            return source
        return self._imread_unicode(source)

    # ==================== 颜色掩码 ====================
    def _create_color_mask(self, img_bgr):
        mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
        for b, g, r in self.TARGET_COLORS_BGR:
            mask |= cv2.inRange(img_bgr, (b, g, r), (b, g, r))
        return (mask > 0).astype(np.uint8)

    # ==================== 行检测 ====================
    def _detect_text_lines(self, fg, expand_x=None):
        if expand_x is None:
            expand_x = self.EXPAND_X
        H, W = fg.shape
        has_text = fg.sum(axis=1) > self.MIN_ROW_PIXELS
        if not has_text.any():
            return []
        padded = np.pad(has_text, (1, 1), constant_values=False)
        starts = np.flatnonzero(padded[1:] & ~padded[:-1])
        ends = np.flatnonzero(padded[:-1] & ~padded[1:]) - 1

        merged = []
        for y1, y2 in zip(starts, ends):
            if merged and y1 - merged[-1][1] - 1 <= 2:
                merged[-1][1] = y2
            else:
                merged.append([y1, y2])

        regions = []
        for y1, y2 in merged:
            if y2 - y1 + 1 != self.LINE_HEIGHT_EXACT:
                continue
            col_any = fg[y1:y2+1].any(axis=0)
            cols = np.flatnonzero(col_any)
            if cols.size == 0:
                continue
            x1 = max(0, cols[0] - expand_x)
            x2 = min(W-1, cols[-1] + expand_x)
            regions.append((y1, x1, y2, x2))
        return regions

    # ==================== 单行识别 ====================
    def _recognize_line(self, binary_line):
        h, w_line = binary_line.shape
        if h != self.TEMPLATE_HEIGHT:
            raise ValueError(f"行图像高度应为 {self.TEMPLATE_HEIGHT}，实际 {h}")

        best_matches = {}
        for w in self.possible_widths:
            if w_line < w:
                continue
            n_starts = w_line - w + 1
            col_any = binary_line.any(axis=0)
            cols = np.flatnonzero(col_any)
            if cols.size == 0:
                continue
            lo = max(0, cols[0] - w + 1)
            hi = min(n_starts - 1, cols[-1])
            if lo > hi:
                continue
            starts_ok = np.zeros(n_starts, dtype=bool)
            starts_ok[lo:hi+1] = True

            cand = np.flatnonzero(starts_ok)
            if cand.size == 0:
                continue

            windows = sliding_window_view(
                binary_line, (self.TEMPLATE_HEIGHT, w))[0][cand]
            windows = np.ascontiguousarray(windows.reshape(cand.size, -1))
            nonempty = windows.any(axis=1)
            if not nonempty.any():
                continue
            valid_windows = windows[nonempty]
            valid_x = cand[nonempty]

            packed = np.packbits(valid_windows, axis=1)
            keys = packed_to_uint64_keys(packed)
            sorted_keys, sorted_chars = self.width_to_hash[w]
            idx = np.searchsorted(sorted_keys, keys)
            valid_idx = idx < len(sorted_keys)
            found = np.zeros(len(keys), dtype=bool)
            found[valid_idx] = sorted_keys[idx[valid_idx]] == keys[valid_idx]

            for x, char_idx in zip(valid_x[found], idx[found]):
                char = sorted_chars[char_idx]
                if char in self.BLACKLIST:
                    continue
                coord = int(x)
                if coord not in best_matches:
                    best_matches[coord] = (char, w)
                else:
                    if w > best_matches[coord][1]:
                        best_matches[coord] = (char, w)

        if not best_matches:
            return "", []

        items = sorted(best_matches.items(), key=lambda x: x[0])
        merged = []
        last_x = -10
        last_w = 0
        for x, (char, w) in items:
            if not merged:
                merged.append([char, x, w])
                last_x = x
                last_w = w
                continue
            if x <= last_x + last_w - 2:
                if w > last_w:
                    merged.pop()
                    merged.append([char, x, w])
                    last_x = x
                    last_w = w
            else:
                merged.append([char, x, w])
                last_x = x
                last_w = w

        text = "".join(item[0] for item in merged)
        chars = [{"ch": item[0], "x1": item[1], "x2": item[1] + item[2]}
                 for item in merged]
        return text, chars

    # ==================== 对外接口 ====================
    def recognize(self, source, log=None, declared_type=None):
        if not self._loaded:
            self.load(log=log)
        if declared_type is None:
            declared_type = self.default_declared_type
        if isinstance(source, str):
            src_desc = source
        else:
            src_desc = "采集卡"

        t0 = time.perf_counter()
        img = self._load_image(source)
        if img is None:
            raise ValueError("无法读取图像")

        h_page, w_page = img.shape[:2]

        # ---- 1. 裁剪 ROI ----
        y1_roi = max(0, min(self.ROI_Y1, h_page))
        y2_roi = max(0, min(self.ROI_Y2, h_page))
        x1_roi = max(0, min(self.ROI_X1, w_page))
        x2_roi = max(0, min(self.ROI_X2, w_page))
        roi = img[y1_roi:y2_roi, x1_roi:x2_roi]

        if roi.size == 0:
            raise ValueError(f"ROI 裁剪后为空: y[{y1_roi},{y2_roi}] x[{x1_roi},{x2_roi}]")

        # ---- 2. 前景掩码 ----
        fg_roi = self._create_color_mask(roi)

        # ---- 3. 行检测 ----
        regions = self._detect_text_lines(fg_roi)
        if log: log(f"ROI内检测到行：{len(regions)} 行")

        # ---- 4. 逐行识别 ----
        lines = []
        for i, (y1, x1, y2, x2) in enumerate(regions):
            line_img = np.ascontiguousarray(fg_roi[y1:y2+1, x1:x2+1])
            text, chars_rel = self._recognize_line(line_img)

            chars = []
            for c in chars_rel:
                abs_x1 = x1_roi + x1 + c["x1"]
                abs_x2 = x1_roi + x1 + c["x2"]
                chars.append(make_char(c["ch"], abs_x1, abs_x2))

            abs_y1 = y1_roi + y1
            abs_y2 = y1_roi + y2
            abs_x1_line = x1_roi + x1
            abs_x2_line = x1_roi + x2
            y_mid = (abs_y1 + abs_y2) // 2

            lines.append(make_line(text, y_mid, abs_y1, abs_y2,
                                    abs_x1_line, abs_x2_line, chars))
            if log: log(f"  行 {i+1:02d}: {text}")

        # ---- 5. 前景掩码压缩（供表格分析器查询）----
        packed = np.packbits(fg_roi.flatten())
        packed_b64 = base64.b64encode(packed.tobytes()).decode("ascii")
        foreground = {
            "y_offset": y1_roi,
            "x_offset": x1_roi,
            "h": int(fg_roi.shape[0]),
            "w": int(fg_roi.shape[1]),
            "packed_b64": packed_b64,
        }

        page = make_page(0, w_page, h_page, lines)
        page["foreground"] = foreground

        result = make_result(src_desc, self.name, declared_type, [page],
                     processor=self.processor)
        if log: log(f"识别完成，总耗时 {time.perf_counter()-t0:.3f}s")
        return result