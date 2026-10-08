# models.py
"""
数据模型层 - 定义所有步骤类型
"""
from dataclasses import dataclass, field, asdict
from typing import Literal, List, Dict, Any, Optional, Union
import json


@dataclass
class BaseStep:
    """步骤基类"""
    type: str
    name: str = ""
    enabled: bool = True
    description: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MouseStep(BaseStep):
    """鼠标操作步骤（支持单击、双击、右键、中键、拖动、移动、滚轮）"""
    type: Literal["mouse"] = "mouse"
    
    # 动作类型
    action: Literal[
        "click",           # 单击（左键）
        "double_click",    # 双击（左键）
        "right_click",     # 右键单击
        "middle_click",    # 中键单击
        "drag",            # 按住-移动-松开（拖动）
        "move",            # 移动位置
        "scroll"           # 滚轮滚动
    ] = "click"
    
    # 坐标设置
    use_last_location: bool = True  # 使用上次定位的坐标
    x: int = 0
    y: int = 0
    offset_x: int = 0
    offset_y: int = 0
    
    # 按钮设置（用于 click、double_click，但 right_click/middle_click 已隐含）
    button: Literal["left", "right", "middle"] = "left"
    
    # 拖动专用
    drag_to_x: int = 0
    drag_to_y: int = 0
    drag_duration: float = 0.5  # 拖动持续时间
    
    # 滚轮专用
    scroll_direction: Literal["up", "down"] = "up"  # 滚动方向
    scroll_amount: int = 1  # 滚动量（格数）
    
    # 延迟
    delay_before: float = 0.0  # 操作前延迟
    delay_after: float = 0.2  # 操作后延迟


@dataclass
class KeyboardStep(BaseStep):
    """键盘操作步骤"""
    type: Literal["keyboard"] = "keyboard"
    
    # 操作类型
    action: Literal["type_text", "press_keys"] = "type_text"
    
    # 输入内容（用于 type_text）
    text: str = ""
    
    # 按键列表（用于 press_keys，记录器生成的按键序列）
    keys: List[Dict[str, Any]] = field(default_factory=list)
    # 每个按键格式: {'key': int, 'text': str, 'ctrl': bool, 'shift': bool, 'alt': bool, 'meta': bool}
    
    # 输入选项
    press_enter: bool = False  # 是否在输入后按回车
    enter_times: int = 1  # 回车次数
    
    # 输入间隔
    use_default_interval: bool = True  # 使用默认间隔
    custom_interval: float = 0.00  # 自定义按键间隔（秒）
    
    # 延迟
    delay_before: float = 0.0
    delay_after: float = 0.2


@dataclass
class WaitStep(BaseStep):
    """等待步骤"""
    type: Literal["wait"] = "wait"
    
    duration: float = 1.0  # 等待时长（秒）


@dataclass
class LocateStep(BaseStep):
    """
    图像定位步骤（增强版）
    - 支持保存匹配区域的四个顶点坐标
    - 内置条件分支：根据识别结果执行不同子步骤
    - 内置循环：可循环识别直到满足条件
    """
    type: Literal["locate"] = "locate"
    
    # ========== 图片配置 ==========
    template: str = ""  # 主图片路径
    additional_templates: List[str] = field(default_factory=list)  # 额外的图片（多图定位）
    
    # ========== 识别参数 ==========
    threshold: float = 1.0  # 匹配阈值
    timeout: float = 10.0  # 单次识别超时（秒）
    retry_count: int = 10  # 单次识别内部重试次数（1表示不重试）
    retry_interval: float = 1.0  # 内部重试间隔（秒）
    
    # ========== 搜索区域限制 ==========
    use_region: bool = False  # 是否限制搜索区域
    region_x: int = 0
    region_y: int = 0
    region_width: int = 1920
    region_height: int = 1080
    
    # ========== 坐标偏移 ==========
    offset_x: int = 0
    offset_y: int = 0
    
    # ========== 结果处理 ==========
    use_center: bool = True  # 保存中心点坐标（否则保存左上角）
    save_to_variable: str = ""  # 保存中心点/左上角坐标到变量
    
    # 导出四个顶点坐标（左上、右上、右下、左下）
    save_corners: bool = False
    corners_variable_prefix: str = ""  # 四顶点变量名前缀，例如 "loc1" 会生成 loc1_tl, loc1_tr, loc1_br, loc1_bl
    
    # ========== 文字图片配置（用于OCR场景） ==========
    is_text_image: bool = False
    text_content: str = ""
    text_font_size: int = 14
    text_bold: bool = False
    text_font_family: str = "Microsoft YaHei"

    # 分支逻辑（替换原来的 condition, then_steps, else_steps）
    branches: List[Dict[str, Any]] = field(default_factory=list) 
  
    # ========== 循环设置 ==========
    loop_enabled: bool = False  # 是否启用循环
    loop_mode: Literal["until_found", "while_found", "count"] = "until_found"
    # until_found: 循环直到找到图片（或达到最大次数）
    # while_found: 只要找到图片就继续循环（或达到最大次数）
    # count: 固定次数循环
    max_iterations: int = 10  # 最大循环次数（防止死循环）
    check_interval: float = 1.0  # 每次循环之间的间隔（秒）
    
    # ========== 失败处理 ==========
    on_fail: Literal["stop", "continue", "skip"] = "stop"


@dataclass
class RoiAnalysisStep(BaseStep):
    """
    ROI区域分析步骤（增强版）
    - 支持保存ROI区域的四个顶点坐标
    - 内置条件分支：根据分析结果（内容占比）执行不同子步骤
    - 内置循环：可循环分析直到满足条件
    """
    type: Literal["roi_analysis"] = "roi_analysis"
    
    # ========== 参考图片列表 ==========
    reference_images: List[str] = field(default_factory=list)
    
    # ========== ROI配置 ==========
    roi_offset_x: int = 0
    roi_offset_y: int = -20
    roi_width: int = 25
    roi_height: int = 22
    
    # 导出ROI区域四个顶点坐标
    save_corners: bool = False
    corners_variable_prefix: str = ""  # 例如 "roi1" 会生成 roi1_tl, roi1_tr, roi1_br, roi1_bl
    
    # ========== 分析参数 ==========
    white_threshold: int = 200  # 白色像素阈值
    content_threshold: float = 5.5  # 内容判定阈值（百分比）
    
    # ========== 结果保存 ==========
    save_results_to: str = "roi_results"  # 保存分析结果（内容占比）到变量
    
    # ========== 条件分支（基于分析结果） ==========
    condition: Literal["if_content_above", "if_content_below", "always"] = "always"
    # if_content_above: 内容占比 >= content_threshold 时执行 then_steps
    # if_content_below: 内容占比 < content_threshold 时执行 then_steps
    # always: 始终执行 then_steps（此时 else_steps 被忽略）
    
    # 子步骤：条件满足时执行
    then_steps: List[Dict[str, Any]] = field(default_factory=list)
    # 子步骤：条件不满足时执行（仅在 condition 不为 always 时有效）
    else_steps: List[Dict[str, Any]] = field(default_factory=list)
    
    # ========== 循环设置 ==========
    loop_enabled: bool = False  # 是否启用循环
    loop_mode: Literal["until_above", "until_below", "count"] = "until_above"
    # until_above: 循环直到内容占比 >= content_threshold（或达到最大次数）
    # until_below: 循环直到内容占比 < content_threshold（或达到最大次数）
    # count: 固定次数循环
    max_iterations: int = 10  # 最大循环次数
    check_interval: float = 1.0  # 每次循环之间的间隔（秒）
    
    # ========== 失败处理 ==========
    on_fail: Literal["stop", "continue"] = "continue"

    # 分支逻辑
    branches: List[Dict[str, Any]] = field(default_factory=list)


# 步骤类型映射表（仅包含新逻辑中的步骤类型）
STEP_TYPE_MAP = {
    "locate": LocateStep,
    "mouse": MouseStep,
    "keyboard": KeyboardStep,
    "wait": WaitStep,
    "roi_analysis": RoiAnalysisStep,
}


def step_from_dict(data: dict) -> BaseStep:
    """从字典创建步骤对象"""
    step_type = data.get("type")
    step_class = STEP_TYPE_MAP.get(step_type)
    if step_class is None:
        return BaseStep.from_dict(data)
    return step_class.from_dict(data)


@dataclass
class Workflow:
    """工作流"""
    name: str = "新工作流"
    description: str = ""
    version: str = "1.0"
    steps: List[BaseStep] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "steps": [step.to_dict() for step in self.steps]
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建"""
        steps_data = data.get("steps", [])
        steps = [step_from_dict(s) for s in steps_data]
        
        return cls(
            name=data.get("name", "新工作流"),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            steps=steps
        )
    
    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: str):
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


# 步骤类型显示名称（用于UI）
STEP_TYPE_NAMES = {
    "locate": "🔍 图像定位",
    "mouse": "🖱️ 鼠标操作",
    "keyboard": "⌨️ 键盘输入",
    "wait": "⏱️ 等待",
    "roi_analysis": "📊 ROI分析",
}


def get_step_display_name(step: BaseStep) -> str:
    """获取步骤显示名称"""
    prefix = STEP_TYPE_NAMES.get(step.type, "❓")
    if step.name:
        return f"{prefix} - {step.name}"
    else:
        return prefix