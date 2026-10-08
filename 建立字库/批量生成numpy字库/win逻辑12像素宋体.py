import os
import time
import ctypes
from ctypes import wintypes
import numpy as np
from PIL import Image

# ---------------- 配置 ----------------
FONT_NAME = "宋体"               # 或 "SimSun"
FONT_SIZE = 16                   # 9 磅 = 12 像素
TARGET_HEIGHT = 12
VERTICAL_OFFSET = 1              # 字体的上下偏移

OUTPUT_DIR = "./bitmask_library"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAVE_INDIVIDUAL_IMAGES = True    # 若需加速可改为 False，避免生成大量图片
IMAGE_SAVE_DIR = os.path.join(OUTPUT_DIR, "char_individual")
if SAVE_INDIVIDUAL_IMAGES:
    os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

# ---------------- Win32 API 声明 ----------------
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

LF_FACESIZE = 32

class LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", wintypes.LONG),
        ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG),
        ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG),
        ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE),
        ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE),
        ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE),
        ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE),
        ("lfFaceName", wintypes.WCHAR * LF_FACESIZE),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]

class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", wintypes.BYTE),
        ("rgbGreen", wintypes.BYTE),
        ("rgbRed", wintypes.BYTE),
        ("rgbReserved", wintypes.BYTE),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]

class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

class TEXTMETRICW(ctypes.Structure):
    _fields_ = [
        ("tmHeight", wintypes.LONG),
        ("tmAscent", wintypes.LONG),
        ("tmDescent", wintypes.LONG),
        ("tmInternalLeading", wintypes.LONG),
        ("tmExternalLeading", wintypes.LONG),
        ("tmAveCharWidth", wintypes.LONG),
        ("tmMaxCharWidth", wintypes.LONG),
        ("tmWeight", wintypes.LONG),
        ("tmOverhang", wintypes.LONG),
        ("tmDigitizedAspectX", wintypes.LONG),
        ("tmDigitizedAspectY", wintypes.LONG),
        ("tmFirstChar", wintypes.WCHAR),
        ("tmLastChar", wintypes.WCHAR),
        ("tmDefaultChar", wintypes.WCHAR),
        ("tmBreakChar", wintypes.WCHAR),
        ("tmItalic", wintypes.BYTE),
        ("tmUnderlined", wintypes.BYTE),
        ("tmStruckOut", wintypes.BYTE),
        ("tmPitchAndFamily", wintypes.BYTE),
        ("tmCharSet", wintypes.BYTE),
    ]

# 常量
DIB_RGB_COLORS = 0
BI_RGB = 0
TRANSPARENT = 1
FW_NORMAL = 400
FW_BOLD = 700
GB2312_CHARSET = 134
DEFAULT_CHARSET = 1
OUT_DEFAULT_PRECIS = 0
CLIP_DEFAULT_PRECIS = 0
NONANTIALIASED_QUALITY = 3      # 关闭字体平滑
DEFAULT_PITCH = 0
FF_DONTCARE = 0
GGI_MARK_NONEXISTING_GLYPHS = 0x0001
LCMAP_SIMPLIFIED_CHINESE = 0x02000000
LOCALE_SYSTEM_DEFAULT = 0x0800  # 中文简体

# 显式声明参数/返回值类型
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]

user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

user32.FillRect.restype = ctypes.c_int
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]

gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]

gdi32.DeleteDC.restype = ctypes.c_int
gdi32.DeleteDC.argtypes = [wintypes.HDC]

gdi32.CreateFontIndirectW.restype = wintypes.HFONT
gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]

gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]

gdi32.DeleteObject.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]

gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD
]

gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]

gdi32.SetTextColor.restype = wintypes.COLORREF
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]

gdi32.SetBkMode.restype = ctypes.c_int
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]

gdi32.GetTextMetricsW.restype = ctypes.c_int
gdi32.GetTextMetricsW.argtypes = [wintypes.HDC, ctypes.POINTER(TEXTMETRICW)]

gdi32.TextOutW.restype = ctypes.c_int
gdi32.TextOutW.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]

gdi32.GetTextExtentPoint32W.restype = ctypes.c_int
gdi32.GetTextExtentPoint32W.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(SIZE)]

gdi32.GetGlyphIndicesW.restype = wintypes.DWORD
gdi32.GetGlyphIndicesW.argtypes = [
    wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
    ctypes.POINTER(wintypes.WORD), wintypes.DWORD
]

kernel32.LCMapStringW.restype = ctypes.c_int
kernel32.LCMapStringW.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
    ctypes.c_int, wintypes.LPWSTR, ctypes.c_int
]

# ---------------- 字符集生成函数 ----------------
def generate_digits():
    """数字：0-9"""
    return [str(i) for i in range(10)]

def generate_letters():
    """英文字母大小写：A-Z, a-z"""
    return ([chr(i) for i in range(ord('A'), ord('Z')+1)] +
            [chr(i) for i in range(ord('a'), ord('z')+1)])

def generate_symbols():
    """符号：ASCII符号 + 中文标点 + 数学符号 + 其他符号"""
    ascii_symbols = list(r'''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~''')
    cjk_symbols = ['，','。','！','？','；','：','“','”','‘','’','（','）','【','】','《','》','……','—','·','、']
    math_symbols = ['+','−','×','÷','=','≠','±','≤','≥','≈','∞','√','∫','∑','∠','⊥','∵','∴']
    other_symbols = ['℃','℉','°','′','″','‰','§','©','®','™']
    combined = ascii_symbols + cjk_symbols + math_symbols + other_symbols
    # 去重并保持顺序
    return list(dict.fromkeys(combined))

def generate_gb2312_chars():
    """GB2312 全部一、二级汉字（6763个）"""
    chars = []
    for high in range(0xB0, 0xF8):      # 区码 B0-F7
        for low in range(0xA1, 0xFF):    # 位码 A1-FE
            try:
                ch = bytes([high, low]).decode('gb2312')
                if '\u4e00' <= ch <= '\u9fff':   # 只保留汉字
                    chars.append(ch)
            except UnicodeDecodeError:
                pass
    return list(dict.fromkeys(chars))

def is_simplified_chinese(ch):
    """利用 Windows LCMapString 的简繁转换判断字符是否为简体（繁体将被转换为不同字符）"""
    src = ctypes.create_unicode_buffer(ch)
    dst = ctypes.create_unicode_buffer(2)
    ret = kernel32.LCMapStringW(LOCALE_SYSTEM_DEFAULT, LCMAP_SIMPLIFIED_CHINESE,
                                src, 1, dst, 2)
    if ret == 0:
        return True   # 转换失败时保留，避免误删
    return dst.value == ch

def generate_gbk_ext_chars():
    """GBK 中 GB2312 以外的简体中文（过滤繁体/异体）"""
    # 1. 生成 GBK 全部汉字
    gbk_chars = set()
    for high in range(0x81, 0xFF):
        for low in range(0x40, 0xFF):
            if low == 0x7F:   # 跳过无效
                continue
            try:
                ch = bytes([high, low]).decode('gbk')
                if '\u4e00' <= ch <= '\u9fff':
                    gbk_chars.add(ch)
            except UnicodeDecodeError:
                pass

    # 2. GB2312 汉字集合
    gb2312_set = set(generate_gb2312_chars())

    # 3. 差值：GBK 扩展汉字
    ext_chars = gbk_chars - gb2312_set

    # 4. 过滤：仅保留简体（利用系统简繁转换）
    simplified_ext = [ch for ch in ext_chars if is_simplified_chinese(ch)]
    return sorted(simplified_ext)   # 排序保证稳定性

# ---------------- 字体支持检测 ----------------
def filter_supported_chars(chars, font_name, font_size, weight=FW_NORMAL, charset=GB2312_CHARSET):
    hdc_screen = user32.GetDC(0)
    if not hdc_screen:
        raise RuntimeError("GetDC 失败")

    mem_dc = gdi32.CreateCompatibleDC(hdc_screen)
    if not mem_dc:
        user32.ReleaseDC(0, hdc_screen)
        raise RuntimeError("CreateCompatibleDC 失败")

    hfont = None
    old_font = None
    supported = []

    try:
        logfont = LOGFONTW()
        logfont.lfHeight = -font_size
        logfont.lfWidth = 0
        logfont.lfWeight = weight
        logfont.lfCharSet = charset
        logfont.lfOutPrecision = OUT_DEFAULT_PRECIS
        logfont.lfClipPrecision = CLIP_DEFAULT_PRECIS
        logfont.lfQuality = NONANTIALIASED_QUALITY
        logfont.lfPitchAndFamily = DEFAULT_PITCH | FF_DONTCARE
        logfont.lfFaceName = font_name

        hfont = gdi32.CreateFontIndirectW(ctypes.byref(logfont))
        if not hfont:
            raise RuntimeError("CreateFontIndirectW 失败")

        old_font = gdi32.SelectObject(mem_dc, hfont)

        pgi = (wintypes.WORD * 1)()
        for ch in chars:
            if ch == ' ':
                continue
            gdi32.GetGlyphIndicesW(mem_dc, ch, 1, pgi, GGI_MARK_NONEXISTING_GLYPHS)
            if pgi[0] != 0xFFFF:
                supported.append(ch)
            else:
                # 数字必须保留
                if '0' <= ch <= '9':
                    print(f"⚠️ 数字 '{ch}' 检测异常，但强制保留。", flush=True)
                    supported.append(ch)

    finally:
        if old_font is not None:
            gdi32.SelectObject(mem_dc, old_font)
        if hfont:
            gdi32.DeleteObject(hfont)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, hdc_screen)

    return supported

# ---------------- 渲染单个字符 ----------------
def render_char_gdi(char, font_name, font_size, height, vertical_offset=0,
                    weight=FW_NORMAL, charset=GB2312_CHARSET):
    hdc_screen = user32.GetDC(0)
    if not hdc_screen:
        raise RuntimeError("GetDC 失败")

    mem_dc = gdi32.CreateCompatibleDC(hdc_screen)
    if not mem_dc:
        user32.ReleaseDC(0, hdc_screen)
        raise RuntimeError("CreateCompatibleDC 失败")

    hfont = None
    hbitmap = None
    old_font = None
    old_bmp = None
    white_brush = None

    try:
        logfont = LOGFONTW()
        logfont.lfHeight = -font_size
        logfont.lfWidth = 0
        logfont.lfWeight = weight
        logfont.lfCharSet = charset
        logfont.lfOutPrecision = OUT_DEFAULT_PRECIS
        logfont.lfClipPrecision = CLIP_DEFAULT_PRECIS
        logfont.lfQuality = NONANTIALIASED_QUALITY
        logfont.lfPitchAndFamily = DEFAULT_PITCH | FF_DONTCARE
        logfont.lfFaceName = font_name

        hfont = gdi32.CreateFontIndirectW(ctypes.byref(logfont))
        if not hfont:
            raise RuntimeError("CreateFontIndirectW 失败")

        old_font = gdi32.SelectObject(mem_dc, hfont)

        size = SIZE()
        ok = gdi32.GetTextExtentPoint32W(mem_dc, char, len(char), ctypes.byref(size))
        if not ok or size.cx <= 0:
            raise RuntimeError(f"测量无效 (cx={size.cx})")
        width = size.cx

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height   # 自上而下
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 24
        bmi.bmiHeader.biCompression = BI_RGB

        pbits = ctypes.c_void_p()
        hbitmap = gdi32.CreateDIBSection(mem_dc, ctypes.byref(bmi), DIB_RGB_COLORS,
                                          ctypes.byref(pbits), None, 0)
        if not hbitmap or not pbits:
            raise RuntimeError("CreateDIBSection 失败")

        old_bmp = gdi32.SelectObject(mem_dc, hbitmap)

        white_brush = gdi32.CreateSolidBrush(0x00FFFFFF)
        rect = wintypes.RECT(0, 0, width, height)
        user32.FillRect(mem_dc, ctypes.byref(rect), white_brush)

        gdi32.SetTextColor(mem_dc, 0x00000000)
        gdi32.SetBkMode(mem_dc, TRANSPARENT)

        gdi32.TextOutW(mem_dc, 0, vertical_offset, char, len(char))

        stride = ((width * 3 + 3) // 4) * 4
        buf = ctypes.string_at(pbits, stride * height)
        arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, stride))
        bgr = arr[:, :width * 3].reshape(height, width, 3)

        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:, :, 0] = bgr[:, :, 2]
        img[:, :, 1] = bgr[:, :, 1]
        img[:, :, 2] = bgr[:, :, 0]

        gray = np.dot(img[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
        mask = (gray < 128).astype(np.uint8)

        if np.sum(mask) == 0:
            raise RuntimeError("渲染结果全空白")

        return mask

    finally:
        if old_bmp is not None:
            gdi32.SelectObject(mem_dc, old_bmp)
        if old_font is not None:
            gdi32.SelectObject(mem_dc, old_font)
        if white_brush is not None:
            gdi32.DeleteObject(white_brush)
        if hfont:
            gdi32.DeleteObject(hfont)
        if hbitmap:
            gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, hdc_screen)

# ---------------- 构建字库 ----------------
def build_library(chars, font_name, font_size, height=TARGET_HEIGHT,
                  vertical_offset=VERTICAL_OFFSET, weight=FW_NORMAL,
                  charset=GB2312_CHARSET, label="library",
                  save_images=SAVE_INDIVIDUAL_IMAGES):
    print(f"候选字符数: {len(chars)}", flush=True)

    supported_chars = filter_supported_chars(chars, font_name, font_size, weight, charset)
    rejected_chars = [c for c in chars if c not in supported_chars]
    print(f"字体支持字符: {len(supported_chars)}，剔除字符: {len(rejected_chars)}", flush=True)
    if rejected_chars:
        print(f"剔除字符列表（前50）: {''.join(rejected_chars[:50])}", flush=True)

    templates, valid_chars, widths, failed = [], [], [], []
    start_time = time.time()

    for i, ch in enumerate(supported_chars, 1):
        try:
            mask = render_char_gdi(ch, font_name, font_size, height, vertical_offset,
                                   weight, charset)
            if mask.shape[0] != height:
                raise ValueError("高度不符")
            templates.append(mask)
            valid_chars.append(ch)
            widths.append(mask.shape[1])

            if save_images:
                img_disp = Image.fromarray((1 - mask) * 255, mode='L')
                scale = 10
                img_disp = img_disp.resize((mask.shape[1] * scale, height * scale), Image.NEAREST)
                safe_name = ch.replace('\\', '＼').replace('/', '／').replace(':', '：') \
                              .replace('*', '＊').replace('?', '？').replace('|', '｜') \
                              .replace('"', '＂').replace('<', '＜').replace('>', '＞')
                img_disp.save(os.path.join(IMAGE_SAVE_DIR, f"{safe_name}_{label}.png"))

            if i % 100 == 0 or i == len(supported_chars):
                elapsed = time.time() - start_time
                print(f"进度: {i}/{len(supported_chars)}，速度: {i/elapsed:.1f} 字符/秒", flush=True)

        except Exception as e:
            failed.append(ch)
            if len(failed) <= 20:
                print(f"❌ '{ch}' 跳过: {e}", flush=True)

    templates_obj = np.empty(len(templates), dtype=object)
    for idx, tmpl in enumerate(templates):
        templates_obj[idx] = tmpl

    output_path = os.path.join(OUTPUT_DIR, f"chars_{label}_{height}x{height}_variable.npz")
    np.savez_compressed(output_path,
                         templates=templates_obj,
                         chars=np.array(valid_chars),
                         widths=np.array(widths, dtype=np.int32))

    print(f"\n✅ 完成！成功: {len(valid_chars)}，失败: {len(failed)}", flush=True)
    if failed:
        print(f"失败字符数: {len(failed)}", flush=True)
    print(f"宽度范围: {min(widths) if widths else 0} ~ {max(widths) if widths else 0} 像素", flush=True)
    print(f"保存: {output_path}", flush=True)
    print(f"耗时: {time.time()-start_time:.2f} 秒", flush=True)


if __name__ == "__main__":
    print("🚀 开始构建宋体分类字库（普通 + 加粗）...", flush=True)

    # 定义各类别字符集
    categories = {
        "digits": generate_digits(),
        "letters": generate_letters(),
        "symbols": generate_symbols(),
        "gb2312_simplified": generate_gb2312_chars(),
        "gbk_ext_simplified": generate_gbk_ext_chars(),
    }

    for name, chars in categories.items():
        # GBK 扩展字符使用 DEFAULT_CHARSET，其余用 GB2312_CHARSET
        if name == "gbk_ext_simplified":
            cs = DEFAULT_CHARSET
        else:
            cs = GB2312_CHARSET

        # 普通版
        print(f"\n========== 构建 {name} 普通版 ==========", flush=True)
        build_library(chars, FONT_NAME, FONT_SIZE, TARGET_HEIGHT, VERTICAL_OFFSET,
                      weight=FW_NORMAL, charset=cs, label=name,
                      save_images=SAVE_INDIVIDUAL_IMAGES)

        # 加粗版
        print(f"\n========== 构建 {name} 加粗版 ==========", flush=True)
        build_library(chars, FONT_NAME, FONT_SIZE, TARGET_HEIGHT, VERTICAL_OFFSET,
                      weight=FW_BOLD, charset=cs, label=f"{name}_bold",
                      save_images=SAVE_INDIVIDUAL_IMAGES)

    print("\n🎉 全部完成！", flush=True)