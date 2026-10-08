# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR引擎 / 12像素助手-检验结果】

用途：
    识别 HIS 检验结果页面表格的 16 像素字体。
    不限制 ROI，直接在整图上操作。

行检测策略（像素级遍历）：
    1. 对整图做颜色掩码得到前景。
    2. 遍历每一个 y 位置（y = 0 ~ H-16）：
        - 该 16 像素窗口内无前景 → 跳过
        - 有前景 → 计算 x 范围，识别一次
        - 识别出内容 → 记入命中列表 (y, text, chars_rel, wx1, wx2)
    3. 合并相邻且文本相同的命中为同一"真实行"：
        - 若当前命中的 text 与上一组相同，且 y 差 ≤ 16 → 并入上一组
        - 否则开一个新组
    4. 每组取中间那个命中作为代表，组装成最终行。

对外接口：
    recognize(source, log=None, declared_type=None)
        → OCR结果 dict
        page 里多一个 "foreground" 字段（无 ROI 偏移）：
            {
                "y_offset": 0,
                "x_offset": 0,
                "h": ..., "w": ...,
                "packed_b64": ...,
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
    """把 (N, n_bytes) 的 uint8 打包数组转成 (N,) 的 uint64 keys，用于二分查找。"""
    n, n_bytes = packed.shape
    n_parts = (n_bytes + 7) // 8
    padded = np.zeros((n, n_parts * 8), dtype=np.uint8)
    padded[:, :n_bytes] = packed
    dtype = np.dtype([(f"p{i}", "<u8") for i in range(n_parts)])
    return padded.view(dtype).reshape(-1)


class OCR12ScanEngine(BaseOcrEngine):       # ← 类名改
    name = "12像素OCR"                       # ← name 改成唯一的
    description = "整图扫描，像素级遍历识别"
    default_declared_type = "12像素扫描"
    processor = "12像素扫描"                  # ← processor 改成"12像素扫描"

    # ---------------- 字库缓存 ----------------
    CACHE_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "数据", "字库缓存", "16像素宋体", "font_hash_cache.pkl")

    # ---------------- 通用参数 ----------------
    TEMPLATE_HEIGHT = 16        # 模板高度（字高）
    EXPAND_X = 6                # 行段左右扩展的安全边距
    BLACKLIST = {"丨", "|"}     # 屏蔽的噪声字符

    # ---------------- 颜色掩码（页面文字可能的颜色） ----------------
    TARGET_COLORS_BGR = [
        (1, 1, 255), (53, 31, 32), (1, 128, 128), (60, 51, 11),
        (1, 1, 1), (255, 1, 1), (128, 1, 155),
        (52, 30, 31),   # 采集卡漂移后的深灰
    ]

    DEBUG_MODE = False

    def __init__(self):
        super().__init__()
        self.width_to_hash = None
        self.possible_widths = None

    # ================================================================
    # 加载字库缓存
    # ================================================================
    def load(self, log=None):
        """
        加载 16 像素宋体字库。
        缓存结构（16像素格式）：
            ( width_to_hash_dict,  possible_widths )
        其中 width_to_hash_dict[w] = (keys, chars, priorities, bold)
        本引擎只使用 keys 和 chars，priorities/bold 忽略。
        """
        if self._loaded:
            return
        if not os.path.exists(self.CACHE_FILE):
            raise FileNotFoundError(f"缓存文件不存在：{self.CACHE_FILE}")
        if log: log(f"加载缓存：{self.CACHE_FILE}")
        t0 = time.perf_counter()
        with open(self.CACHE_FILE, "rb") as f:
            raw_cache = pickle.load(f)

        # 16 像素字库外层是 (dict, possible_widths) 元组
        raw_dict = raw_cache[0] if isinstance(raw_cache, tuple) else raw_cache

        self.width_to_hash = {}
        for w, entry in raw_dict.items():
            # entry = (keys, chars, priorities, bold)，只取前两个
            str_keys = np.asarray(entry[0])
            if str_keys.size == 0:
                continue
            chars = np.asarray(entry[1])

            # S{n_bytes} → uint8 → uint64 keys
            n_bytes = str_keys.dtype.itemsize
            packed = str_keys.view(np.uint8).reshape(-1, n_bytes)
            keys = packed_to_uint64_keys(packed)

            # 排序并对齐 chars
            order = np.argsort(keys, kind="stable")
            self.width_to_hash[w] = (keys[order], chars[order])

        self.possible_widths = sorted(self.width_to_hash.keys())
        if log:
            log(f"缓存加载完成，共 {len(self.width_to_hash)} 种宽度，"
                f"耗时 {time.perf_counter()-t0:.3f}s")
        self._loaded = True

    # ================================================================
    # 图片 IO
    # ================================================================
    @staticmethod
    def _imread_unicode(path):
        """支持中文路径的图片读取。"""
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    def _load_image(self, source):
        if isinstance(source, np.ndarray):
            return source
        return self._imread_unicode(source)

    # ================================================================
    # 颜色掩码
    # ================================================================
    def _create_color_mask(self, img_bgr):
        """
        按 TARGET_COLORS_BGR 逐色 inRange 后取并集。
        返回 uint8 数组（前景 = 1，背景 = 0），形状 (H, W)。
        """
        mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
        for b, g, r in self.TARGET_COLORS_BGR:
            mask |= cv2.inRange(img_bgr, (b, g, r), (b, g, r))
        return (mask > 0).astype(np.uint8)

    # ================================================================
    # 单行识别（哈希匹配）
    # ================================================================
    def _recognize_line(self, binary_line):
        """
        输入：高度恰好 16 的二值行图（前景=1）。
        输出：(text, chars_rel)，chars_rel 是相对行图左边缘的字符列表。
        实现：对所有可能的字宽 w 做滑动窗口，打包成 bit 串后二分查表。
        """
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
            # 只考察与前景有交集的起始位置
            lo = max(0, cols[0] - w + 1)
            hi = min(n_starts - 1, cols[-1])
            if lo > hi:
                continue
            starts_ok = np.zeros(n_starts, dtype=bool)
            starts_ok[lo:hi + 1] = True

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

            # bit 串 → uint64 keys，批量二分查表
            packed = np.packbits(valid_windows, axis=1)
            keys = packed_to_uint64_keys(packed)
            sorted_keys, sorted_chars = self.width_to_hash[w]
            idx = np.searchsorted(sorted_keys, keys)
            valid_idx = idx < len(sorted_keys)
            found = np.zeros(len(keys), dtype=bool)
            found[valid_idx] = sorted_keys[idx[valid_idx]] == keys[valid_idx]

            # 同一 x 位置：优先宽字（信息更多）
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

        # 按 x 排序，合并重叠命中（相邻位置同字只保留较宽者）
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

    # ================================================================
    # 对外接口
    # ================================================================
    def recognize(self, source, log=None, declared_type=None):
        if not self._loaded:
            self.load(log=log)
        if declared_type is None:
            declared_type = self.default_declared_type
        src_desc = source if isinstance(source, str) else "采集卡"

        t0 = time.perf_counter()
        img = self._load_image(source)
        if img is None:
            raise ValueError("无法读取图像")

        H, W = img.shape[:2]
        TH = self.TEMPLATE_HEIGHT

        # ---- 1. 整图前景掩码（无 ROI）----
        fg = self._create_color_mask(img)

        # ---- 2. 遍历每一个 y 位置（像素级），窗口内有前景才识别 ----
        raw_hits = []   # [(y, text, chars_rel, wx1, wx2)]
        for y in range(0, H - TH + 1):
            band = fg[y:y + TH]
            if not band.any():
                continue
            cols = np.flatnonzero(band.any(axis=0))
            if cols.size == 0:
                continue
            wx1 = max(0, cols[0] - self.EXPAND_X)
            wx2 = min(W - 1, cols[-1] + self.EXPAND_X)

            line_img = np.ascontiguousarray(fg[y:y + TH, wx1:wx2 + 1])
            text, chars_rel = self._recognize_line(line_img)
            if text:
                raw_hits.append((y, text, chars_rel, wx1, wx2))

        if log:
            log(f"像素级遍历：共 {H - TH + 1} 个 y 位置，"
                f"命中 {len(raw_hits)} 个")

        # ---- 3. 合并相邻且文本相同的命中为同一"真实行" ----
        groups = []   # 每个组：{"text": str, "hits": [(y, text, chars, wx1, wx2), ...]}
        for hit in raw_hits:
            y, text = hit[0], hit[1]
            if groups:
                last = groups[-1]
                # 文本相同 + y 距离 ≤ 一个字高 → 视为同一行
                if last["text"] == text and \
                   (y - last["hits"][-1][0]) <= TH:
                    last["hits"].append(hit)
                    continue
            groups.append({"text": text, "hits": [hit]})

        if log:
            log(f"合并后真实行数：{len(groups)}")

        # ---- 4. 每组取中间那个命中作为代表，组装成行 ----
        lines = []
        for gi, g in enumerate(groups, 1):
            rep = g["hits"][len(g["hits"]) // 2]
            y, text, chars_rel, wx1, wx2 = rep
            y1, y2 = y, y + TH - 1

            chars = [make_char(c["ch"], wx1 + c["x1"], wx1 + c["x2"])
                     for c in chars_rel]
            y_mid = (y1 + y2) // 2
            lines.append(make_line(text, y_mid, y1, y2, wx1, wx2, chars))

            if log:
                log(f"  行 {gi:02d} (y={y1}-{y2}, 命中 {len(g['hits'])} 次): {text}")

        # ---- 5. 前景掩码压缩（供表格分析器查询）----
        packed = np.packbits(fg.flatten())
        packed_b64 = base64.b64encode(packed.tobytes()).decode("ascii")
        foreground = {
            "y_offset": 0,
            "x_offset": 0,
            "h": int(fg.shape[0]),
            "w": int(fg.shape[1]),
            "packed_b64": packed_b64,
        }

        page = make_page(0, W, H, lines)
        page["foreground"] = foreground

        result = make_result(src_desc, self.name, declared_type, [page],
                             processor=self.processor)
        if log:
            log(f"识别完成，总耗时 {time.perf_counter()-t0:.3f}s")
        return result