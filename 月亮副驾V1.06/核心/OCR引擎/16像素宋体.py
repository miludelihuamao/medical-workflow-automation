# -*- coding: utf-8 -*-
"""
================================================================
【核心 / OCR引擎 / 16像素宋体】

用途：
    识别病历页面上 16 像素宋体文字。
    基于预先构建的字库哈希缓存，做精确的模板匹配。

职责：
    1. 加载字库缓存（font_hash_cache.pkl）
    2. 从画面中提取"纸片"区域（绿色边框内）
    3. 检测每一行文字（高度 16 像素）
    4. 逐行做字符匹配，拼接成文本

缓存文件：
    数据/字库缓存/16像素宋体/font_hash_cache.pkl

对外接口：
    recognize(source, log=None)
        source: 图片路径(str) 或 numpy 数组(BGR)
        返回:   [[paper1行1, paper1行2, ...], [paper2行1, ...], ...]

被谁使用：
    - 界面/功能面板/OCR面板.py      （通过 create_engines() 动态加载）

用途：
    识别病历页面上 16 像素宋体文字。
    默认内容类型：病历内容（病历通常需要按段落切分）。

对外接口：
    recognize(source, log=None, declared_type=None)
        → OCR结果 dict（含字符坐标，详见 核心/OCR结果.py）
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


class FontHashOcrEngine(BaseOcrEngine):
    name = "病历16像素宋体"
    description = "基于 16 像素宋体字库的精确匹配，需要预构建缓存"
    default_declared_type = "病历内容"      # ★
    processor = "病历内容"                   # ★

    # ---- 配置 ----
    BASE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "数据", "字库缓存", "16像素宋体")
    CACHE_FILE = os.path.join(BASE_DIR, "font_hash_cache.pkl")
    TEMPLATE_HEIGHT = 16

    TIMING_VERBOSE = True
    DEBUG_MODE = False

    EXTRACT_MIN_WIDTH = 730
    DETECT_EXPAND_X = 6
    DETECT_MIN_ROW_PIXELS = 1
    DETECT_MIN_GAP = 2
    DETECT_MIN_LINE_HEIGHT = 10

    def __init__(self):
        super().__init__()
        self.width_to_hash = None
        self.possible_widths = None

    # ==================== 加载缓存 ====================
    def load(self, log=None):
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
        if log: log(f"缓存加载完成，共 {len(self.width_to_hash)} 种宽度，"
                    f"耗时 {time.time()-t0:.3f} 秒")
        self._loaded = True

    # ==================== 图片IO ====================
    @staticmethod
    def _imread_unicode(path):
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

    def _load_image(self, source):
        if isinstance(source, np.ndarray):
            return source
        return self._imread_unicode(source)

    # ==================== 提取纸张 ====================
    def _extract_papers(self, image_source, min_width, log):
        img = self._load_image(image_source)
        green = (img[:,:,0]==87)&(img[:,:,1]==87)&(img[:,:,2]==1)
        ys, xs = np.where(green)
        if len(xs)==0:
            raise ValueError("未找到绿色像素")
        gx1, gy1, gx2, gy2 = xs.min(), ys.min(), xs.max(), ys.max()
        if self.DEBUG_MODE and log:
            log(f"[Debug] 绿色边框: x1={gx1}, y1={gy1}, x2={gx2}, y2={gy2}")

        roi = img[gy1:gy2+1, gx1:gx2+1].copy()
        roi[green[gy1:gy2+1, gx1:gx2+1]] = (0,0,0)

        non_black = np.any(roi!=0, axis=2).astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(non_black, connectivity=8)
        candidates = []
        for i in range(1, num):
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            if w > min_width:
                candidates.append((y, x, y+h-1, x+w-1))
        if not candidates:
            raise ValueError("未找到宽度大于阈值的纸张区域")

        candidates.sort(key=lambda r: r[0])
        papers = []
        for top, left, bottom, right in candidates:
            paper = roi[top+1:bottom, left+1:right]
            if paper.size == 0:
                raise ValueError("纸张区域收缩后无效")
            papers.append(paper)
        return papers

    # ==================== 行检测 ====================
    def _detect_text_lines(self, img, expand_x, log):
        H, W = img.shape[:2]
        fg = (img[:,:,0]==1)&(img[:,:,1]==1)&(img[:,:,2]==1)
        if not fg.any():
            return []

        row_counts = fg.sum(axis=1)
        has_text = row_counts > self.DETECT_MIN_ROW_PIXELS
        padded = np.concatenate(([False], has_text, [False]))
        diff = np.diff(padded.astype(np.int8))
        starts = np.where(diff==1)[0]
        ends = np.where(diff==-1)[0] - 1
        segments = list(zip(starts.tolist(), ends.tolist()))

        merged = []
        for seg in segments:
            if merged and seg[0] - merged[-1][1] - 1 <= self.DETECT_MIN_GAP:
                merged[-1][1] = seg[1]
            else:
                merged.append(list(seg))

        rows = []
        for y1, y2 in merged:
            h = y2 - y1 + 1
            if self.DETECT_MIN_LINE_HEIGHT <= h <= 16:
                rows.append((y1, y2, h))
        if not rows:
            return []

        n = len(rows)
        determined = [False]*n
        final_rows = [None]*n

        for i, (y1, y2, h) in enumerate(rows):
            if h == 16:
                determined[i] = True
                final_rows[i] = (y1, y2)

        for i, (y1, y2, h) in enumerate(rows):
            if determined[i] or h not in (14,15):
                continue
            if not (i>0 and determined[i-1] and i<n-1 and determined[i+1]):
                continue
            prev_y2 = final_rows[i-1][1]
            next_y1 = final_rows[i+1][0]
            cond_up = (prev_y2+6 < H and fg[prev_y2+1:prev_y2+6, :].sum()==0)
            cond_down = (next_y1-6 >=0 and fg[next_y1-5:next_y1, :].sum()==0)
            if not (cond_up and cond_down):
                continue
            if next_y1 - prev_y2 - 1 != 26:
                continue
            new_y1, new_y2 = prev_y2+6, next_y1-6
            if new_y1<0 or new_y2>=H or new_y2-new_y1+1!=16:
                continue
            determined[i] = True
            final_rows[i] = (new_y1, new_y2)

        line_regions = []
        for row in final_rows:
            if row is None:
                continue
            y1, y2 = row
            cols = np.where(fg[y1:y2+1,:].sum(axis=0)>0)[0]
            if len(cols)==0:
                continue
            x1 = max(0, cols.min()-expand_x)
            x2 = min(W-1, cols.max()+expand_x)
            line_regions.append((y1, x1, y2, x2))
        return line_regions

    # ==================== 单行识别（★ 改造：返回 (text, chars)）====================
    def _recognize_line(self, binary_line, log):
        h, w_line = binary_line.shape
        if h != self.TEMPLATE_HEIGHT:
            raise ValueError(f"行高应为 {self.TEMPLATE_HEIGHT}，实际 {h}")

        best_matches = {}   # x → (char, prio, bold, w)
        for w in self.possible_widths:
            if w_line < w:
                continue
            windows = sliding_window_view(
                binary_line, (self.TEMPLATE_HEIGHT, w)
            ).reshape(-1, self.TEMPLATE_HEIGHT * w)
            nonempty = windows.any(axis=1)
            if not nonempty.any():
                continue
            valid = windows[nonempty]
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

            for char, x, prio, bold in zip(matched_chars, matched_x,
                                            matched_priorities, matched_bold):
                coord = int(x)
                if coord not in best_matches:
                    best_matches[coord] = (char, prio, bold, w)
                else:
                    old_prio, old_bold = best_matches[coord][1], best_matches[coord][2]
                    if prio < old_prio or (prio == old_prio and not bold and old_bold):
                        best_matches[coord] = (char, prio, bold, w)

        if not best_matches:
            return "", []

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

    # ==================== 对外接口（★ 改造：返回 OCR结果 dict）====================
    def recognize(self, image_path, log=None, declared_type=None):
        if not self._loaded:
            self.load(log=log)

        if declared_type is None:
            declared_type = self.default_declared_type

        if isinstance(image_path, str):
            source = image_path
        else:
            source = "采集卡"

        t0 = time.time()
        if log: log("开始提取纸张...")
        papers = self._extract_papers(image_path, self.EXTRACT_MIN_WIDTH, log)
        if log: log(f"提取到 {len(papers)} 张，耗时 {time.time()-t0:.3f}s")

        pages = []
        for pi, paper in enumerate(papers):
            if log: log(f"===== 第 {pi+1}/{len(papers)} 张 =====")
            regions = self._detect_text_lines(paper, self.DETECT_EXPAND_X, log)
            if log: log(f"  检测到 {len(regions)} 行")

            h_page, w_page = paper.shape[:2]
            lines = []

            for li, (y1, x1, y2, x2) in enumerate(regions, 1):
                line_img = paper[y1:y2+1, x1:x2+1]
                gray = cv2.cvtColor(line_img, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 128, 1, cv2.THRESH_BINARY_INV)

                t1 = time.time()
                text, chars_rel = self._recognize_line(binary, log)
                dt = time.time() - t1

                # 相对坐标 → 绝对坐标（相对于纸张）
                chars = []
                for c in chars_rel:
                    chars.append(make_char(c["ch"], x1 + c["x1"], x1 + c["x2"]))

                y_mid = (y1 + y2) // 2
                lines.append(make_line(text, y_mid, y1, y2, x1, x2, chars))

                if log:
                    log(f"  行 {li:02d}: {text}" +
                        (f"  ({dt:.3f}s)" if self.TIMING_VERBOSE else ""))

            pages.append(make_page(pi, w_page, h_page, lines))

        if log: log(f"识别完成，总耗时 {time.time()-t0:.3f}s")
        return make_result(source, self.name, declared_type, pages,
                   processor=self.processor)