import os
import time
import pickle
import numpy as np

# ============================================================
# 配置路径与参数
# ============================================================
TEMPLATE_HEIGHT = 12          # 高度固定为12
BLACKLIST = {"丨", "|"}      # 黑名单字符（不参与匹配，包括竖线符号）

# 多字库配置：(文件路径, 优先级, 是否粗体)
# 优先级越小越优先；数字0，英文Tahoma 1，英文宋体 2，GB2312简化 3，符号 4，GBK拓展 5
LIBRARY_SPECS = [
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\chars_digits_12x12_variable.npz", 0, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\chars_digits_normal_12_12x12_variable.npz", 0, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\chars_letters_normal_12_12x12_variable.npz", 1, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\font_12px_R.npz", 1, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\chars_letters_12x12_variable.npz", 2, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\chars_gb2312_simplified_12x12_variable.npz", 3, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\chars_symbols_12x12_variable.npz", 4, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\chars_symbols_normal_12_12x12_variable.npz", 4, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\chars_gbk_ext_simplified_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\粗体\chars_digits_bold_12_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\粗体\chars_letters_bold_12_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12+16像素Tahoma字库\粗体\chars_symbols_bold_12_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\粗体\chars_digits_bold_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\粗体\chars_gb2312_simplified_bold_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\粗体\chars_gbk_ext_simplified_bold_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\粗体\chars_letters_bold_12x12_variable.npz", 5, False),
    (r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\12像素宋体字库\粗体\chars_symbols_bold_12x12_variable.npz", 5, False),
]

CACHE_FILE = r"替换成你本地的文件路径"
# ============================================================
# 构建哈希表
# ============================================================
def build_hash_tables():
    print("开始构建哈希表...")
    start = time.time()
    width_to_entries = {}
    for path, priority, is_bold in LIBRARY_SPECS:
        data = np.load(path, allow_pickle=True)
        templates = data['templates']
        chars = data['chars']
        widths = data['widths']
        print(f"加载字库：{os.path.basename(path)}，共 {len(chars)} 个字符，优先级 {priority}")
        for i in range(len(chars)):
            char = chars[i]
            if char in BLACKLIST:
                continue
            w = int(widths[i])
            tmpl = templates[i]
            if tmpl.ndim != 2 or tmpl.shape[0] != TEMPLATE_HEIGHT:
                continue
            flat = (tmpl > 0).astype(np.uint8).reshape(1, -1)
            packed = np.packbits(flat, axis=1).tobytes()
            width_to_entries.setdefault(w, []).append((priority, is_bold, char, packed))
    width_to_hash = {}
    for w, entries in width_to_entries.items():
        entries.sort(key=lambda e: (e[0], e[1]))
        best = {}
        for priority, is_bold, char, key in entries:
            if key not in best:
                best[key] = (priority, is_bold, char)
        if not best:
            continue
        best_items = list(best.items())
        best_items.sort(key=lambda item: item[0])
        bytes_len = len(best_items[0][0])
        keys = np.array([item[0] for item in best_items], dtype=f'S{bytes_len}')
        chars_arr = np.array([item[1][2] for item in best_items])
        width_to_hash[w] = (keys, chars_arr)
    possible_widths = sorted(width_to_hash.keys())
    print(f"哈希表构建完成，共 {len(width_to_hash)} 种宽度，耗时 {time.time()-start:.3f} 秒")
    return width_to_hash

def save_cache(width_to_hash):
    print(f"保存缓存到：{CACHE_FILE}")
    start = time.time()
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(width_to_hash, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"缓存保存完成，耗时 {time.time()-start:.3f} 秒")

if __name__ == "__main__":
    width_to_hash = build_hash_tables()
    save_cache(width_to_hash)
    print("步骤1完成，缓存已生成。")