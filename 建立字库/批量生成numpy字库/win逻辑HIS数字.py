import os
import time
import ctypes
from ctypes import wintypes
import numpy as np
from PIL import Image

# ---------------- 配置 ----------------
FONT_NAME = "Tahoma"
FONT_SIZE_12 = 12
TARGET_HEIGHT_12 = 12
VERTICAL_OFFSET_12 = -1            # 垂直偏移

OUTPUT_DIR = "./bitmask_library"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAVE_INDIVIDUAL_IMAGES = True
IMAGE_SAVE_DIR = os.path.join(OUTPUT_DIR, "char_individual_tahoma_gdi")
if SAVE_INDIVIDUAL_IMAGES:
    os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

# ---------------- Win32 API 声明 ----------------
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)

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

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]

# 常量
DIB_RGB_COLORS = 0
BI_RGB = 0
TRANSPARENT = 1
FW_NORMAL = 400
FW_BOLD = 700
ANSI_CHARSET = 0
OUT_DEFAULT_PRECIS = 0
CLIP_DEFAULT_PRECIS = 0
NONANTIALIASED_QUALITY = 3
DEFAULT_PITCH = 0
FF_DONTCARE = 0
GGI_MARK_NONEXISTING_GLYPHS = 0x0001

# 显式声明参数/返回值类型
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]

user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

user32.FillRect.restype = ctypes.c_int
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]

gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]

gdi32.DeleteDC.restype = ctypes.c_int
gdi32.DeleteDC.argtypes = [wintypes.HDC]

gdi32.CreateFontIndirectW.restype = wintypes.HFONT
gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]

gdi32.SelectObject.restype = ctypes.c_void_p  # HGDIOBJ 使用通用指针
gdi32.SelectObject.argtypes = [wintypes.HDC, ctypes.c_void_p]

gdi32.DeleteObject.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]

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

# ---------------- 字符集生成函数 ----------------
def generate_digits():
    """数字 0-9"""
    return [str(i) for i in range(10)]

# ---------------- 字体支持检测 ----------------
def filter_supported_chars(chars, font_name, font_size, weight=FW_NORMAL):
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
        logfont.lfCharSet = ANSI_CHARSET
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
                # 数字必须保留，即使检测失败
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
def render_char_gdi(char, font_name, font_size, height, vertical_offset=0, weight=FW_NORMAL):
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
        logfont.lfCharSet = ANSI_CHARSET
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
        rect = RECT(0, 0, width, height)
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
def build_library(chars, font_name, font_size, height, vertical_offset=0,
                  weight=FW_NORMAL, label="tahoma_gdi",
                  save_images=SAVE_INDIVIDUAL_IMAGES):
    print(f"候选字符数: {len(chars)}", flush=True)

    supported_chars = filter_supported_chars(chars, font_name, font_size, weight)
    rejected_chars = [c for c in chars if c not in supported_chars]
    print(f"字体支持字符: {len(supported_chars)}，剔除字符: {len(rejected_chars)}", flush=True)
    if rejected_chars:
        print(f"剔除字符列表: {''.join(rejected_chars)}", flush=True)

    templates, valid_chars, widths, failed = [], [], [], []
    start_time = time.time()

    for i, ch in enumerate(supported_chars, 1):
        try:
            mask = render_char_gdi(ch, font_name, font_size, height, vertical_offset, weight)
            if mask.shape[0] != height:
                raise ValueError("高度不符")
            templates.append(mask)
            valid_chars.append(ch)
            widths.append(mask.shape[1])

            if save_images:
                img_disp = Image.fromarray((1 - mask) * 255, mode='L')
                scale = 10
                img_disp = img_disp.resize((mask.shape[1] * scale, height * scale), Image.NEAREST)
                safe_name = ch  # 数字无需替换非法字符
                img_disp.save(os.path.join(IMAGE_SAVE_DIR, f"{safe_name}_{label}.png"))

            if i % 20 == 0 or i == len(supported_chars):
                elapsed = time.time() - start_time
                print(f"进度: {i}/{len(supported_chars)}，速度: {i/elapsed:.1f} 字符/秒", flush=True)

        except Exception as e:
            failed.append(ch)
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
        print(f"失败字符: {failed}", flush=True)
    print(f"宽度范围: {min(widths) if widths else 0} ~ {max(widths) if widths else 0} 像素", flush=True)
    print(f"保存: {output_path}", flush=True)
    print(f"耗时: {time.time()-start_time:.2f} 秒", flush=True)


if __name__ == "__main__":
    print("🚀 开始构建 Tahoma 数字字库（12px，普通/加粗）...", flush=True)

    digits = generate_digits()

    for weight_name, weight in [("normal", FW_NORMAL), ("bold", FW_BOLD)]:
        label_12 = f"digits_{weight_name}_12"
        print(f"\n========== 构建 {label_12} ==========", flush=True)
        build_library(digits, FONT_NAME, FONT_SIZE_12, TARGET_HEIGHT_12,
                      vertical_offset=VERTICAL_OFFSET_12, weight=weight,
                      label=label_12, save_images=SAVE_INDIVIDUAL_IMAGES)

    print("\n🎉 全部完成！", flush=True)