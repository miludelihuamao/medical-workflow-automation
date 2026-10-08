# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR引擎 / 16像素助手-检查结果】

用途：
    识别检查结果页面（16像素宋体）。
    直接用 ROI 裁剪，跳过绿色边框提取步骤。

行检测策略：
    逻辑1：若 ROI 中存在 16 像素高的行
        → 以最上面的 16 像素行为锚点，
          按 [16 文字 + 4 空白] = 20 像素的步长向上下网格化枚举，
          每个 16 像素窗口若有黑色像素(1,1,1)则作为候选。

    逻辑2：若 ROI 中不存在 16 像素高的行
        → 对每个不满 16 像素的行，向上拓展 4 像素、向下拓展 4 像素，
          在扩展后的区域上【像素级】枚举所有可能的 16 像素窗口作为候选，
          每个候选都送去识别，取识别字符数最多者作为该行结果。

    识别阶段：
        - 逻辑1 每组只有 1 个候选；
        - 逻辑2 每组有 (扩展高度 − 15) 个候选；
        - 每组内遍历所有候选，用 "识别字符数" 作为对齐质量度量，
          选最优者作为该行最终结果。

ROI 范围：
    x ∈ [402, 1911]
    y ∈ [204, 1030]

输出：
    OCR 结果 dict，processor = "检查结果"
================================================================
"""
import cv2
import numpy as np
import time
import os
import pickle
from numpy.lib.stride_tricks import sliding_window_view

from 核心.OCR引擎.引擎基类 import BaseOcrEngine
from 核心.OCR结果 import make_result, make_page, make_line, make_char


class OCR16CheckResultEngine(BaseOcrEngine):
    # ---------------- 引擎元信息 ----------------
    name = "16像素助手-检查结果"
    description = "检查结果页面（16像素，限定 ROI，双逻辑行检测）"
    default_declared_type = "检查结果"
    processor = "检查结果"

    # ---------------- 字库缓存路径 ----------------
    BASE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "数据", "字库缓存", "16像素宋体")
    CACHE_FILE = os.path.join(BASE_DIR, "font_hash_cache.pkl")

    # ---------------- 通用参数 ----------------
    TEMPLATE_HEIGHT = 16
    TIMING_VERBOSE = True
    DEBUG_MODE = False

    # ---------------- 行段检测参数 ----------------
    DETECT_EXPAND_X = 6            # 左右扩展安全边距（像素）
    DETECT_MIN_ROW_PIXELS = 1      # 一行至少有这么多前景像素才认为有文字
    DETECT_MIN_GAP = 2             # 相邻行段合并的最大空隙
    DETECT_MIN_SEGMENT_HEIGHT = 4  # 原始行段最小高度（低于此视为噪声）

    # ---------------- 新版行布局常量 ----------------
    LINE_STEP = 20                 # 逻辑1：16 文字 + 4 空白
    LINE_PAD_TOP = 4               # 逻辑2：向上拓展像素
    LINE_PAD_BOTTOM = 4            # 逻辑2：向下拓展像素

    # ---------------- ROI 硬编码 ----------------
    ROI_Y1 = 204
    ROI_Y2 = 1030
    ROI_X1 = 402
    ROI_X2 = 1911

    def __init__(self):
        super().__init__()
        self.width_to_hash = None
        self.possible_widths = None

    # ================================================================
    # 加载字库缓存
    # ================================================================
    def load(self, log=None):
        """
        从 pkl 文件加载字库。
        self.width_to_hash[w] = (sorted_keys, sorted_chars,
                                 sorted_priorities, sorted_bold)
        sorted_keys 是 S{bytes} 数组，用于和滑窗打包后的 key 做二分查找。
        """
        if self._loaded:
            return
        if not os.path.exists(self.CACHE_FILE):
            raise FileNotFoundError(
                f"缓存文件不存在：{self.CACHE_FILE}\n请先运行构建哈希脚本生成缓存。"
            )
        if log: log(f"加载缓存：{self.CACHE_FILE}")
        t0 = time.time()
        with open(self.CACHE_FILE, 'rb') as f:
            self.width_to_hash, self.possible_widths = pickle.load(f)
        if log:
            log(f"缓存加载完成，共 {len(self.width_to_hash)} 种宽度，"
                f"耗时 {time.time()-t0:.3f} 秒")
        self._loaded = True

    # ================================================================
    # 图片 IO
    # ================================================================
    @staticmethod
    def _imread_unicode(path):
        """支持中文路径的图片读取。"""
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

    def _load_image(self, source):
        if isinstance(source, np.ndarray):
            return source
        return self._imread_unicode(source)

    # ================================================================
    # 前景掩码
    # ================================================================
    @staticmethod
    def _foreground_mask(img):
        """
        页面渲染的纯黑像素 (1,1,1) 视为前景。
        返回 bool 数组，形状 (H, W)。
        """
        return (img[:, :, 0] == 1) & (img[:, :, 1] == 1) & (img[:, :, 2] == 1)

    # ================================================================
    # 原始行段检测（只做合并 + 最小高度过滤）
    # ================================================================
    def _find_raw_segments(self, fg):
        """
        找出所有连续前景行段 (y1, y2)。
        - 合并间隔 ≤ DETECT_MIN_GAP 的相邻段；
        - 过滤高度 < DETECT_MIN_SEGMENT_HEIGHT 的噪声段。
        不做 14/15 像素的修补（修补由新版逻辑1/逻辑2接管）。
        """
        row_counts = fg.sum(axis=1)
        has_text = row_counts > self.DETECT_MIN_ROW_PIXELS

        # 用差分找连续 True 区间
        padded = np.concatenate(([False], has_text, [False]))
        diff = np.diff(padded.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0] - 1
        segments = list(zip(starts.tolist(), ends.tolist()))

        # 合并间隔很小的相邻段
        merged = []
        for seg in segments:
            if merged and seg[0] - merged[-1][1] - 1 <= self.DETECT_MIN_GAP:
                merged[-1][1] = seg[1]
            else:
                merged.append(list(seg))

        # 过滤太矮的噪声段
        result = []
        for y1, y2 in merged:
            if y2 - y1 + 1 >= self.DETECT_MIN_SEGMENT_HEIGHT:
                result.append((y1, y2))
        return result

    # ================================================================
    # 把任意高度区域规整为恰好 16 像素（仅用于 h < 16 的兜底）
    # ================================================================
    def _fit_to_16(self, y1, y2, H):
        """
        把任意高度的纵向区域规整为恰好 16 像素：
        - h < 16：优先向上补足，不够再向下补足；越界时贴边。
        - h > 16：从中心取 16 像素。
        返回 (ny1, ny2) 或 (None, None) 表示无法规整。
        """
        h = y2 - y1 + 1
        if h == 16:
            return y1, y2

        if h < 16:
            need = 16 - h
            up = min(y1, need)
            y1 -= up
            need -= up
            y2 += need
            if y2 >= H:
                y2 = H - 1
                y1 = y2 - 15
        else:
            center = (y1 + y2) // 2
            y1 = center - 8
            y2 = center + 7
            if y1 < 0:
                y1, y2 = 0, 15
            if y2 >= H:
                y2, y1 = H - 1, H - 16

        if y1 < 0 or y2 >= H or (y2 - y1 + 1) != 16:
            return None, None
        return y1, y2

    # ================================================================
    # 新版行布局构建：返回候选行组
    # ================================================================
    def _build_line_regions(self, roi, log):
        """
        返回 List[List[(y1, y2)]]：
            - 外层列表的每一项代表"一行"。
            - 内层列表是该行的所有 16px 候选窗口（每个高度恒为 16）。
        逻辑1：每组只有 1 个候选（那个网格点）。
        逻辑2：每组有 (扩展高度 − 15) 个候选（像素级枚举所有可能位置）。
        识别阶段对每组选质量最高者作为该行结果。
        """
        H, W = roi.shape[:2]
        fg = self._foreground_mask(roi)
        if not fg.any():
            return []

        raw = self._find_raw_segments(fg)
        if log:
            log(f"  原始行段数: {len(raw)}  (高度分布: "
                f"{[y2-y1+1 for y1, y2 in raw]})")

        groups = []
        has_16 = any((y2 - y1 + 1) == 16 for y1, y2 in raw)

        # ------------------------------------------------------------
        # 逻辑1：存在 16px 行 → 以最上面的 16px 行为锚点网格化
        # ------------------------------------------------------------
        if has_16:
            anchor_y1 = min(y1 for y1, y2 in raw if y2 - y1 + 1 == 16)
            if log:
                log(f"  逻辑1：锚点 y1={anchor_y1}，步长={self.LINE_STEP}")

            # 向下：anchor, anchor+20, anchor+40, ...
            y = anchor_y1
            while y + 16 <= H:
                if fg[y:y + 16, :].any():
                    groups.append([(y, y + 15)])
                y += self.LINE_STEP

            # 向上：anchor-20, anchor-40, ...
            y = anchor_y1 - self.LINE_STEP
            while y >= 0:
                if fg[y:y + 16, :].any():
                    groups.append([(y, y + 15)])
                y -= self.LINE_STEP

        # ------------------------------------------------------------
        # 逻辑2：无 16px 行 → 扩展区域像素级遍历所有可能的 16px 窗口
        # ------------------------------------------------------------
        else:
            if log:
                log(f"  逻辑2：未发现 16px 行 → 对每个扩展区域像素级遍历所有 16px 窗口")

            for y1, y2 in raw:
                ny1 = max(0, y1 - self.LINE_PAD_TOP)
                ny2 = min(H - 1, y2 + self.LINE_PAD_BOTTOM)
                h = ny2 - ny1 + 1

                group = []
                if h < 16:
                    # 扩展后仍不足 16 → 唯一补足方案，无别的可能
                    wy1, wy2 = self._fit_to_16(ny1, ny2, H)
                    if wy1 is not None and fg[wy1:wy2 + 1, :].any():
                        group.append((wy1, wy2))
                else:
                    # 扩展后 ≥16 → 枚举所有可能的 16px 起始（像素级，步长=1）
                    # 只要窗口内有前景就作为候选
                    for wy in range(ny1, ny2 - 15):
                        if fg[wy:wy + 16, :].any():
                            group.append((wy, wy + 15))

                if group:
                    groups.append(group)

        # 按 y 排序，保证输出行的顺序与页面从上到下一致
        groups.sort(key=lambda g: g[0][0])
        return groups

    # ================================================================
    # 单行识别（核心哈希匹配，保持不变）
    # ================================================================
    def _recognize_line(self, binary_line, log):
        """
        输入：一个高度恰好 16 的二值行图（前景=1）。
        输出：(text, chars_rel)，chars_rel 是相对行图左边缘的字符列表。
        实现：对所有可能的字宽 w 做滑动窗口，打包成 bit 串后二分查表。
        """
        h, w_line = binary_line.shape
        if h != self.TEMPLATE_HEIGHT:
            raise ValueError(f"行高应为 {self.TEMPLATE_HEIGHT}，实际 {h}")

        best_matches = {}

        for w in self.possible_widths:
            if w_line < w:
                continue

            # 滑出所有 (16, w) 的窗口，展平成 (N, 16*w)
            windows = sliding_window_view(
                binary_line, (self.TEMPLATE_HEIGHT, w)
            ).reshape(-1, self.TEMPLATE_HEIGHT * w)

            # 跳过全 0 窗口
            nonempty = windows.any(axis=1)
            if not nonempty.any():
                continue
            valid = windows[nonempty]

            # bit 串 → bytes，用 searchsorted 批量查表
            packed = np.packbits(valid, axis=1)
            keys = packed.view(f'S{packed.shape[1]}').reshape(-1)

            sorted_keys, sorted_chars, sorted_priorities, sorted_bold = \
                self.width_to_hash[w]
            idx = np.searchsorted(sorted_keys, keys)
            mask = (idx >= 0) & (idx < len(sorted_keys))
            found = np.zeros(len(keys), dtype=bool)
            found[mask] = (sorted_keys[idx[mask]] == keys[mask])
            if not found.any():
                continue

            matched_chars = sorted_chars[idx[found]]
            matched_priorities = sorted_priorities[idx[found]]
            matched_bold = sorted_bold[idx[found]]
            matched_x = np.nonzero(nonempty)[0][found]

            # 同一 x 位置多个命中 → 优先级低者优先，同优先级非粗体优先
            for char, x, prio, bold in zip(matched_chars, matched_x,
                                            matched_priorities, matched_bold):
                coord = int(x)
                if coord not in best_matches:
                    best_matches[coord] = (char, prio, bold, w)
                else:
                    old_prio = best_matches[coord][1]
                    old_bold = best_matches[coord][2]
                    if prio < old_prio or (prio == old_prio and not bold and old_bold):
                        best_matches[coord] = (char, prio, bold, w)

        if not best_matches:
            return "", []

        # 按 x 排序后合并相邻位置的重叠命中（间距 ≤ 2 视为同一个字）
        items = sorted(best_matches.items(), key=lambda x: x[0])
        merged = []
        last_x = -10
        for x, (char, prio, bold, w) in items:
            if merged and abs(x - last_x) <= 2:
                if prio < merged[-1][2]:
                    merged[-1] = (char, x, prio, bold, w)
                continue
            merged.append([char, x, prio, bold, w])
            last_x = x

        text = "".join(item[0] for item in merged)
        chars = [{"ch": item[0], "x1": item[1], "x2": item[1] + item[4]}
                 for item in merged]
        return text, chars

    # ================================================================
    # 对外接口
    # ================================================================
    def recognize(self, image_path, log=None, declared_type=None):
        if not self._loaded:
            self.load(log=log)
        if declared_type is None:
            declared_type = self.default_declared_type
        source = image_path if isinstance(image_path, str) else "采集卡"

        t0 = time.time()
        img = self._load_image(image_path)
        if img is None:
            raise ValueError("无法读取图像")

        h_page, w_page = img.shape[:2]

        # ---------------- ROI 裁剪 ----------------
        y1_roi = max(0, min(self.ROI_Y1, h_page))
        y2_roi = max(0, min(self.ROI_Y2, h_page))
        x1_roi = max(0, min(self.ROI_X1, w_page))
        x2_roi = max(0, min(self.ROI_X2, w_page))
        roi = img[y1_roi:y2_roi, x1_roi:x2_roi]

        if roi.size == 0:
            raise ValueError("ROI 裁剪后为空")
        if log:
            log(f"ROI 尺寸: {roi.shape[1]}×{roi.shape[0]}")

        # 预计算 ROI 的前景掩码（后面多处复用）
        fg_roi = self._foreground_mask(roi)

        # ---------------- 行组检测 ----------------
        groups = self._build_line_regions(roi, log)
        if log:
            log(f"  候选行组数: {len(groups)}，"
                f"每组候选数: {[len(g) for g in groups]}")

        # ---------------- 逐组识别：组内遍历所有候选，取识别质量最高者 ----------------
        lines = []
        for li, group in enumerate(groups, 1):
            # best 结构: (score, wy1, wy2, wx1, wx2, text, chars_rel, best_idx)
            best = None

            for gi, (wy1, wy2) in enumerate(group):
                # 该 16px 窗口内若无前景 → 跳过（逻辑1 已保证有，但保险起见）
                if not fg_roi[wy1:wy2 + 1, :].any():
                    continue

                # 计算该窗口内的 x 范围
                cols = np.where(fg_roi[wy1:wy2 + 1, :].sum(axis=0) > 0)[0]
                if len(cols) == 0:
                    continue
                wx1 = max(0, cols.min() - self.DETECT_EXPAND_X)
                wx2 = min(roi.shape[1] - 1,
                          cols.max() + self.DETECT_EXPAND_X)

                # 裁剪 → 灰度 → 二值化（前景=1）
                line_img = roi[wy1:wy2 + 1, wx1:wx2 + 1]
                gray = cv2.cvtColor(line_img, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 128, 1, cv2.THRESH_BINARY_INV)

                # 单次哈希匹配
                text, chars_rel = self._recognize_line(binary, log)

                # 用 "识别出的字符数" 作为对齐质量度量：
                # 对齐准了会一次匹配出一整行字；偏了则全灭。
                score = len(text)
                if best is None or score > best[0]:
                    best = (score, wy1, wy2, wx1, wx2, text, chars_rel, gi)

            # 该行所有候选都没识别出字符 → 跳过
            if best is None or best[0] == 0:
                if log:
                    log(f"  行 {li:02d}: 所有候选均未识别出字符，跳过")
                continue

            score, wy1, wy2, wx1, wx2, text, chars_rel, best_idx = best

            # 相对 ROI → 原图绝对坐标
            chars = [make_char(c["ch"],
                                x1_roi + wx1 + c["x1"],
                                x1_roi + wx1 + c["x2"])
                     for c in chars_rel]

            abs_y1 = y1_roi + wy1
            abs_y2 = y1_roi + wy2
            abs_x1 = x1_roi + wx1
            abs_x2 = x1_roi + wx2
            y_mid = (abs_y1 + abs_y2) // 2

            lines.append(make_line(text, y_mid, abs_y1, abs_y2,
                                    abs_x1, abs_x2, chars))

            if log:
                extra = (f"  (候选 {best_idx + 1}/{len(group)}，"
                         f"得分 {score})") if len(group) > 1 else ""
                log(f"  行 {li:02d} (y={abs_y1}-{abs_y2}){extra}: {text}")

        # ---------------- 组装结果 ----------------
        page = make_page(0, w_page, h_page, lines)
        result = make_result(source, self.name, declared_type, [page],
                             processor=self.processor)
        if log:
            log(f"识别完成，总耗时 {time.time()-t0:.3f}s")
        return result