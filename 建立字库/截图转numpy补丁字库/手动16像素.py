import numpy as np
from PIL import Image
import os

OUTPUT_DIR = "./bitmask_library"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def binarize_only(image_path, threshold=128, invert=False):
    """
    仅二值化，不裁剪、不缩放。
    返回二值掩码，形状与原始图片完全一致（高度应为16）。
    """
    img = Image.open(image_path).convert('L')
    arr = np.array(img, dtype=np.uint8)
    # 二值化：字符为1，背景为0
    mask = (arr < threshold).astype(np.uint8)
    if invert:
        mask = 1 - mask
    return mask   # shape 保持原样，例如 (16, width)

def build_single_symbol_no_resize(image_path, char_label, threshold=128, invert=False):
    """
    生成单个符号的npz文件，不改变图片尺寸（仅二值化）。
    """
    mask = binarize_only(image_path, threshold, invert)
    h, w = mask.shape

    # 检查高度是否为16（如果不符合，给出警告但不强制修改）
    if h != 16:
        print(f"⚠️ 警告：图片高度为 {h}，不是 16 像素。库要求高度为16，可能导致加载失败。")

    # 构造与原有库一致的数据结构
    templates = np.empty(1, dtype=object)
    templates[0] = mask
    chars = np.array([char_label])
    widths = np.array([w], dtype=np.int32)

    # 保存
    safe_name = char_label.replace('\\', '＼').replace('/', '／') \
                          .replace(':', '：').replace('*', '＊') \
                          .replace('?', '？').replace('|', '｜') \
                          .replace('"', '＂').replace('<', '＜').replace('>', '＞')
    out_path = os.path.join(OUTPUT_DIR, f"single_{safe_name}.npz")
    np.savez_compressed(out_path, templates=templates, chars=chars, widths=widths)
    print(f"✅ 已保存: {out_path}")
    print(f"   字符: {char_label}, 尺寸: {h}x{w} 像素（未做任何改动）")
    return out_path

if __name__ == "__main__":
    img_file = r"替换成你本地的文件路径"    symbol_char = "⟋"
    # 如果你的图片是黑底白字，将 invert 改为 True
    build_single_symbol_no_resize(img_file, symbol_char, threshold=128, invert=False)