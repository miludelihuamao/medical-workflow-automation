import numpy as np
from PIL import Image
import os
from pathlib import Path

OUTPUT_DIR = "./bitmask_library"
os.makedirs(OUTPUT_DIR, exist_ok=True)

IMAGE_EXTS = {'.png', '.bmp', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.webp'}


def binarize_only(image_path, threshold=128, invert=False):
    """
    仅二值化，不裁剪、不缩放。
    返回二值掩码，形状与原始图片完全一致。
    默认：白底黑字，字符像素为 1，背景为 0。
    invert=True：黑底白字时使用。
    """
    img = Image.open(image_path).convert('L')
    arr = np.array(img, dtype=np.uint8)
    mask = (arr < threshold).astype(np.uint8)
    if invert:
        mask = (mask == 0).astype(np.uint8)
    return mask


def build_library_from_folder(input_dir,
                              output_name="font_12px.npz",
                              threshold=128,
                              invert=False,
                              expected_height=12,
                              label_file=None):
    """
    批量读取文件夹中的图片，生成一个合并的 12 像素高位图字库 npz。

    参数：
        input_dir:      图片所在文件夹
        output_name:    输出 npz 文件名
        threshold:      二值化阈值
        invert:         黑底白字时设为 True
        expected_height:要求图片高度，默认 12；可设为 None 不检查
        label_file:     可选标签映射文件，每行：文件名<TAB>字符
    """
    input_path = Path(input_dir)
    if not input_path.is_dir():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    # 可选标签映射
    label_map = {}
    if label_file is not None:
        with open(label_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) == 1:
                    parts = line.split()
                if len(parts) >= 2:
                    label_map[parts[0]] = parts[1]

    # 收集图片文件
    image_files = sorted([
        p for p in input_path.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ])

    templates_list = []
    chars_list = []
    widths_list = []
    skipped = []

    for img_file in image_files:
        mask = binarize_only(img_file, threshold, invert)
        h, w = mask.shape

        if expected_height is not None and h != expected_height:
            skipped.append((img_file.name, h, w))
            print(f"⚠️ 跳过 {img_file.name}: 高度 {h}，不是 {expected_height}")
            continue

        # 字符标签：优先使用映射文件，否则用文件名（不含扩展名）
        if img_file.name in label_map:
            char_label = label_map[img_file.name]
        else:
            char_label = img_file.stem

        templates_list.append(mask)
        chars_list.append(char_label)
        widths_list.append(w)
        print(f"✅ 已加入: {img_file.name} -> 字符 '{char_label}'，尺寸 {h}x{w}")

    if not templates_list:
        raise ValueError("没有找到符合高度要求的图片，未生成库文件。")

    n = len(templates_list)
    templates = np.empty(n, dtype=object)
    for i, mask in enumerate(templates_list):
        templates[i] = mask

    chars = np.array(chars_list, dtype=object)   # object 避免多字符标签被截断
    widths = np.array(widths_list, dtype=np.int32)

    out_path = os.path.join(OUTPUT_DIR, output_name)
    np.savez_compressed(out_path,
                        templates=templates,
                        chars=chars,
                        widths=widths)
    print(f"\n✅ 已保存库文件: {out_path}")
    print(f"   共 {n} 个字符；高度: {expected_height}；宽度范围: {min(widths_list)}~{max(widths_list)}")
    if skipped:
        print(f"   跳过 {len(skipped)} 个高度不符合的文件。")
    return out_path


if __name__ == "__main__":
    # ===== 使用前修改这里 =====
    input_dir = r"C:\Users\liusu\Documents\BaiduSyncdisk\Code\bitmask_library\手动补丁库"   # 12像素高字符图片所在文件夹
    # 白底黑字：invert=False；黑底白字：invert=True
    build_library_from_folder(
        input_dir=input_dir,
        output_name="font_12px_budk.npz",
        threshold=128,
        invert=False,
        expected_height=12
    )