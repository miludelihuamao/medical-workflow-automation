import os
import time
import pickle
import numpy as np

# ============================================================
# 配置路径与参数（与识别脚本保持一致）
# ============================================================
BASE_DIR = r"替换成你本地的文件路径"LIBRARY_SPECS = [
    (os.path.join(BASE_DIR, "chars_gb2312_simplified_16x16_variable.npz"), 0, False),
    (os.path.join(BASE_DIR, "chars_gb2312_simplified_bold_16x16_variable.npz"), 0, True),
    (os.path.join(BASE_DIR, "chars_gbk_ext_simplified_16x16_variable.npz"), 1, False),
    (os.path.join(BASE_DIR, "chars_gbk_ext_simplified_bold_16x16_variable.npz"), 1, True),
    (os.path.join(BASE_DIR, "chars_digits_16x16_variable.npz"), 2, False),
    (os.path.join(BASE_DIR, "chars_digits_bold_16x16_variable.npz"), 2, True),
    (os.path.join(BASE_DIR, "chars_letters_16x16_variable.npz"), 3, False),
    (os.path.join(BASE_DIR, "chars_letters_bold_16x16_variable.npz"), 3, True),
    (os.path.join(BASE_DIR, "chars_symbols_16x16_variable.npz"), 4, False),
    (os.path.join(BASE_DIR, "chars_symbols_bold_16x16_variable.npz"), 4, True),
    (os.path.join(BASE_DIR, "single_⟋.npz"), 4, False),
]

TEMPLATE_HEIGHT = 16
BLACKLIST = {"丨"}
CACHE_FILE = os.path.join(BASE_DIR, "font_hash_cache.pkl")

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
        print(f"加载字库：{os.path.basename(path)}，共 {len(chars)} 个字符，优先级 {priority}，粗体={is_bold}")
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
        priorities = np.array([item[1][0] for item in best_items], dtype=np.int32)
        bold_flags = np.array([item[1][1] for item in best_items], dtype=bool)
        chars_arr = np.array([item[1][2] for item in best_items])
        width_to_hash[w] = (keys, chars_arr, priorities, bold_flags)

    possible_widths = sorted(width_to_hash.keys())
    print(f"哈希表构建完成，共 {len(width_to_hash)} 种宽度，耗时 {time.time()-start:.3f} 秒")
    return width_to_hash, possible_widths

def save_cache(width_to_hash, possible_widths):
    print(f"保存缓存到：{CACHE_FILE}")
    start = time.time()
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump((width_to_hash, possible_widths), f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"缓存保存完成，耗时 {time.time()-start:.3f} 秒")

if __name__ == "__main__":
    width_to_hash, possible_widths = build_hash_tables()
    save_cache(width_to_hash, possible_widths)
    print("步骤1完成，缓存已生成。")