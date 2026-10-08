# form_builder.py
"""
动态表单构建器 - 根据步骤类型自动生成参数编辑表单
"""
from PyQt5.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QTextEdit, QGroupBox, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox
)
from PyQt5.QtCore import pyqtSignal, Qt

from models import (
    BaseStep, LocateStep, MouseStep, KeyboardStep, WaitStep,
    RoiAnalysisStep, step_from_dict, get_step_display_name, STEP_TYPE_MAP
)
from widgets import (
    ImagePathEdit, KeyRecorderWidget, MultiImageWidget,
    TextImageDialog, RoiConfigWidget
)


class SubStepsDialog(QDialog):
    """编辑分支子步骤的对话框"""
    def __init__(self, steps: list, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.setWindowTitle("编辑子步骤")
        self.resize(450, 350)
        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.step_list = QListWidget()
        layout.addWidget(self.step_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加子步骤")
        remove_btn = QPushButton("删除子步骤")
        edit_btn = QPushButton("编辑子步骤")
        add_btn.clicked.connect(self.add_step)
        remove_btn.clicked.connect(self.remove_step)
        edit_btn.clicked.connect(self.edit_step)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(edit_btn)
        layout.addLayout(btn_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def refresh_list(self):
        self.step_list.clear()
        for i, step_dict in enumerate(self.steps):
            step = step_from_dict(step_dict)
            display = get_step_display_name(step)
            self.step_list.addItem(f"{i+1}. {display}")

    def add_step(self):
        # 简化：添加一个默认的鼠标步骤，实际可弹出类型选择
        from models import MouseStep
        new_step = MouseStep()
        self.steps.append(new_step.to_dict())
        self.refresh_list()

    def remove_step(self):
        row = self.step_list.currentRow()
        if 0 <= row < len(self.steps):
            del self.steps[row]
            self.refresh_list()

    def edit_step(self):
        row = self.step_list.currentRow()
        if not (0 <= row < len(self.steps)):
            return
        step_dict = self.steps[row]
        step = step_from_dict(step_dict)
        # 创建临时表单编辑
        dialog = StepEditDialog(step, self)
        if dialog.exec_() == QDialog.Accepted:
            self.steps[row] = step.to_dict()
            self.refresh_list()

    def get_steps(self):
        return self.steps


class StepEditDialog(QDialog):
    """用于编辑单个步骤的对话框"""
    def __init__(self, step: BaseStep, parent=None):
        super().__init__(parent)
        self.step = step
        self.setWindowTitle(f"编辑步骤 - {get_step_display_name(step)}")
        self.resize(500, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.form_builder = StepFormBuilder()
        self.form_builder.build_form(self.step)
        layout.addWidget(self.form_builder)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class BranchEditorWidget(QWidget):
    """分支编辑器，管理 if/elif/else 分支及其子步骤"""
    branchesChanged = pyqtSignal(list)

    def __init__(self, step_type: str, branches: list, parent=None):
        super().__init__(parent)
        self.step_type = step_type  # "locate" 或 "roi_analysis"
        self.branches = branches    # 直接引用步骤的 branches 列表
        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.branch_list = QListWidget()
        self.branch_list.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.branch_list)

        btn_layout = QHBoxLayout()
        add_if_btn = QPushButton("添加 IF")
        add_elif_btn = QPushButton("添加 ELIF")
        add_else_btn = QPushButton("添加 ELSE")
        remove_btn = QPushButton("删除分支")
        edit_btn = QPushButton("编辑子步骤")

        add_if_btn.clicked.connect(lambda: self.add_branch("if"))
        add_elif_btn.clicked.connect(lambda: self.add_branch("elif"))
        add_else_btn.clicked.connect(lambda: self.add_branch("else"))
        remove_btn.clicked.connect(self.remove_branch)
        edit_btn.clicked.connect(self.edit_steps)

        btn_layout.addWidget(add_if_btn)
        btn_layout.addWidget(add_elif_btn)
        btn_layout.addWidget(add_else_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(edit_btn)
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.branch_list.clear()
        for i, branch in enumerate(self.branches):
            cond = branch.get("condition_type", "?")
            steps_count = len(branch.get("steps", []))
            item = QListWidgetItem(f"{i+1}. {cond} ({steps_count} 个子步骤)")
            item.setData(Qt.UserRole, i)
            self.branch_list.addItem(item)

    def add_branch(self, kind):
        if self.step_type == "locate":
            if kind == "if":
                condition_type = "if_found"
            elif kind == "elif":
                condition_type = "elif_not_found"
            else:
                condition_type = "else"
        else:  # roi_analysis
            if kind == "if":
                condition_type = "if_content_above"
            elif kind == "elif":
                condition_type = "elif_content_below"
            else:
                condition_type = "else"
        self.branches.append({"condition_type": condition_type, "steps": []})
        self.refresh_list()
        self.branchesChanged.emit(self.branches)

    def remove_branch(self):
        row = self.branch_list.currentRow()
        if 0 <= row < len(self.branches):
            del self.branches[row]
            self.refresh_list()
            self.branchesChanged.emit(self.branches)

    def edit_steps(self):
        row = self.branch_list.currentRow()
        if not (0 <= row < len(self.branches)):
            return
        branch = self.branches[row]
        dialog = SubStepsDialog(branch["steps"], self)
        if dialog.exec_() == QDialog.Accepted:
            branch["steps"] = dialog.get_steps()
            self.refresh_list()
            self.branchesChanged.emit(self.branches)


class StepFormBuilder(QWidget):
    """步骤表单构建器"""
    
    stepChanged = pyqtSignal(BaseStep)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step = None
        self.form_widgets = {}
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
    
    def build_form(self, step: BaseStep):
        self.clear_form()
        self.current_step = step
        self.form_widgets.clear()
        
        if step is None:
            placeholder = QLabel("请选择一个步骤")
            placeholder.setObjectName("subtitle")
            self.main_layout.addWidget(placeholder)
            return
        
        if isinstance(step, LocateStep):
            self._build_locate_form(step)
        elif isinstance(step, MouseStep):
            self._build_mouse_form(step)
        elif isinstance(step, KeyboardStep):
            self._build_keyboard_form(step)
        elif isinstance(step, WaitStep):
            self._build_wait_form(step)
        elif isinstance(step, RoiAnalysisStep):
            self._build_roi_analysis_form(step)
        
        self._add_common_fields(step)
    
    def clear_form(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _add_common_fields(self, step: BaseStep):
        group = QGroupBox("通用设置")
        layout = QFormLayout(group)
        
        name_edit = QLineEdit(step.name)
        name_edit.setPlaceholderText("步骤名称（可选）")
        name_edit.textChanged.connect(lambda v: self._update_field('name', v))
        layout.addRow("名称:", name_edit)
        self.form_widgets['name'] = name_edit
        
        desc_edit = QTextEdit(step.description)
        desc_edit.setPlaceholderText("步骤描述（可选）")
        desc_edit.setMaximumHeight(60)
        desc_edit.textChanged.connect(lambda: self._update_field('description', desc_edit.toPlainText()))
        layout.addRow("描述:", desc_edit)
        self.form_widgets['description'] = desc_edit
        
        enabled_check = QCheckBox("启用此步骤")
        enabled_check.setChecked(step.enabled)
        enabled_check.toggled.connect(lambda v: self._update_field('enabled', v))
        layout.addRow("", enabled_check)
        self.form_widgets['enabled'] = enabled_check
        
        self.main_layout.addWidget(group)
        self.main_layout.addStretch()
    
    def _update_field(self, field_name: str, value):
        if self.current_step and hasattr(self.current_step, field_name):
            setattr(self.current_step, field_name, value)
            self.stepChanged.emit(self.current_step)
    
    # ==================== 图像定位表单 ====================
    def _build_locate_form(self, step: LocateStep):
        # ========== 图片配置 ==========
        img_group = QGroupBox("图片配置")
        img_layout = QFormLayout(img_group)
        
        text_img_check = QCheckBox("生成文字图片")
        text_img_check.setChecked(step.is_text_image)
        text_img_check.toggled.connect(lambda v: self._update_field('is_text_image', v))
        img_layout.addRow("", text_img_check)
        self.form_widgets['is_text_image'] = text_img_check
        
        template_edit = ImagePathEdit()
        template_edit.set_path(step.template)
        template_edit.pathChanged.connect(lambda v: self._update_field('template', v))
        img_layout.addRow("主图片:", template_edit)
        self.form_widgets['template'] = template_edit
        
        text_config_widget = QWidget()
        text_config_layout = QFormLayout(text_config_widget)
        text_config_layout.setContentsMargins(0, 0, 0, 0)
        
        text_content_edit = QLineEdit(step.text_content)
        text_content_edit.setPlaceholderText("输入要识别的文字")
        text_content_edit.textChanged.connect(lambda v: self._update_field('text_content', v))
        text_config_layout.addRow("文字内容:", text_content_edit)
        
        text_font_spin = QSpinBox()
        text_font_spin.setRange(8, 72)
        text_font_spin.setValue(step.text_font_size)
        text_font_spin.valueChanged.connect(lambda v: self._update_field('text_font_size', v))
        text_config_layout.addRow("字号:", text_font_spin)
        
        text_bold_check = QCheckBox("加粗")
        text_bold_check.setChecked(step.text_bold)
        text_bold_check.toggled.connect(lambda v: self._update_field('text_bold', v))
        text_config_layout.addRow("", text_bold_check)
        
        text_font_combo = QComboBox()
        text_font_combo.addItems(["Microsoft YaHei", "SimSun", "SimHei", "KaiTi"])
        text_font_combo.setCurrentText(step.text_font_family)
        text_font_combo.currentTextChanged.connect(lambda v: self._update_field('text_font_family', v))
        text_config_layout.addRow("字体:", text_font_combo)
        
        text_config_widget.setVisible(step.is_text_image)
        text_img_check.toggled.connect(text_config_widget.setVisible)
        img_layout.addRow("", text_config_widget)
        
        multi_img_widget = MultiImageWidget()
        multi_img_widget.set_images(step.additional_templates)
        multi_img_widget.imagesChanged.connect(lambda v: self._update_field('additional_templates', v))
        img_layout.addRow("附加图片:", multi_img_widget)
        self.form_widgets['additional_templates'] = multi_img_widget
        
        self.main_layout.addWidget(img_group)
        
        # ========== 识别参数 ==========
        recog_group = QGroupBox("识别参数")
        recog_layout = QFormLayout(recog_group)
        
        threshold_spin = QDoubleSpinBox()
        threshold_spin.setRange(0.0, 1.0)
        threshold_spin.setSingleStep(0.05)
        threshold_spin.setValue(step.threshold)
        threshold_spin.valueChanged.connect(lambda v: self._update_field('threshold', v))
        recog_layout.addRow("匹配阈值:", threshold_spin)
        
        timeout_spin = QDoubleSpinBox()
        timeout_spin.setRange(0.0, 300.0)
        timeout_spin.setSingleStep(1.0)
        timeout_spin.setValue(step.timeout)
        timeout_spin.setSuffix(" 秒")
        timeout_spin.valueChanged.connect(lambda v: self._update_field('timeout', v))
        recog_layout.addRow("超时时间:", timeout_spin)
        
        retry_spin = QSpinBox()
        retry_spin.setRange(1, 100)
        retry_spin.setValue(step.retry_count)
        retry_spin.valueChanged.connect(lambda v: self._update_field('retry_count', v))
        recog_layout.addRow("内部重试次数:", retry_spin)
        
        interval_spin = QDoubleSpinBox()
        interval_spin.setRange(0.1, 60.0)
        interval_spin.setSingleStep(0.1)
        interval_spin.setValue(step.retry_interval)
        interval_spin.setSuffix(" 秒")
        interval_spin.valueChanged.connect(lambda v: self._update_field('retry_interval', v))
        recog_layout.addRow("重试间隔:", interval_spin)
        
        self.main_layout.addWidget(recog_group)
        
        # ========== 搜索区域 ==========
        region_group = QGroupBox("搜索区域限制")
        region_layout = QFormLayout(region_group)
        
        use_region_check = QCheckBox("启用区域限制")
        use_region_check.setChecked(step.use_region)
        use_region_check.toggled.connect(lambda v: self._update_field('use_region', v))
        region_layout.addRow("", use_region_check)
        
        region_x_spin = QSpinBox()
        region_x_spin.setRange(0, 9999)
        region_x_spin.setValue(step.region_x)
        region_x_spin.valueChanged.connect(lambda v: self._update_field('region_x', v))
        region_layout.addRow("X坐标:", region_x_spin)
        
        region_y_spin = QSpinBox()
        region_y_spin.setRange(0, 9999)
        region_y_spin.setValue(step.region_y)
        region_y_spin.valueChanged.connect(lambda v: self._update_field('region_y', v))
        region_layout.addRow("Y坐标:", region_y_spin)
        
        region_w_spin = QSpinBox()
        region_w_spin.setRange(1, 9999)
        region_w_spin.setValue(step.region_width)
        region_w_spin.valueChanged.connect(lambda v: self._update_field('region_width', v))
        region_layout.addRow("宽度:", region_w_spin)
        
        region_h_spin = QSpinBox()
        region_h_spin.setRange(1, 9999)
        region_h_spin.setValue(step.region_height)
        region_h_spin.valueChanged.connect(lambda v: self._update_field('region_height', v))
        region_layout.addRow("高度:", region_h_spin)
        
        self.main_layout.addWidget(region_group)
        
        # ========== 坐标处理 ==========
        coord_group = QGroupBox("坐标处理")
        coord_layout = QFormLayout(coord_group)
        
        use_center_check = QCheckBox("使用中心点（否则使用左上角）")
        use_center_check.setChecked(step.use_center)
        use_center_check.toggled.connect(lambda v: self._update_field('use_center', v))
        coord_layout.addRow("", use_center_check)
        
        offset_x_spin = QSpinBox()
        offset_x_spin.setRange(-9999, 9999)
        offset_x_spin.setValue(step.offset_x)
        offset_x_spin.valueChanged.connect(lambda v: self._update_field('offset_x', v))
        coord_layout.addRow("X偏移:", offset_x_spin)
        
        offset_y_spin = QSpinBox()
        offset_y_spin.setRange(-9999, 9999)
        offset_y_spin.setValue(step.offset_y)
        offset_y_spin.valueChanged.connect(lambda v: self._update_field('offset_y', v))
        coord_layout.addRow("Y偏移:", offset_y_spin)
        
        save_var_edit = QLineEdit(step.save_to_variable)
        save_var_edit.setPlaceholderText("变量名（可选）")
        save_var_edit.textChanged.connect(lambda v: self._update_field('save_to_variable', v))
        coord_layout.addRow("保存中心/左上角到变量:", save_var_edit)
        
        save_corners_check = QCheckBox("导出四个顶点坐标")
        save_corners_check.setChecked(step.save_corners)
        save_corners_check.toggled.connect(lambda v: self._update_field('save_corners', v))
        coord_layout.addRow("", save_corners_check)
        
        corners_prefix_edit = QLineEdit(step.corners_variable_prefix)
        corners_prefix_edit.setPlaceholderText("变量名前缀，如 'loc1'")
        corners_prefix_edit.textChanged.connect(lambda v: self._update_field('corners_variable_prefix', v))
        coord_layout.addRow("顶点变量前缀:", corners_prefix_edit)
        
        self.main_layout.addWidget(coord_group)
        
        # ========== 分支逻辑 ==========
        branch_group = QGroupBox("分支逻辑（if/elif/else）")
        branch_layout = QVBoxLayout(branch_group)
        
        branch_editor = BranchEditorWidget("locate", step.branches)
        branch_editor.branchesChanged.connect(lambda v: self._update_field('branches', v))
        branch_layout.addWidget(branch_editor)
        
        self.main_layout.addWidget(branch_group)
        
        # ========== 循环设置 ==========
        loop_group = QGroupBox("循环设置")
        loop_layout = QFormLayout(loop_group)
        
        loop_enabled_check = QCheckBox("启用循环")
        loop_enabled_check.setChecked(step.loop_enabled)
        loop_enabled_check.toggled.connect(lambda v: self._update_field('loop_enabled', v))
        loop_layout.addRow("", loop_enabled_check)
        
        loop_widget = QWidget()
        loop_widget_layout = QFormLayout(loop_widget)
        loop_widget_layout.setContentsMargins(0, 0, 0, 0)
        
        loop_mode_combo = QComboBox()
        loop_mode_combo.addItem("循环直到找到", "until_found")
        loop_mode_combo.addItem("找到时继续循环", "while_found")
        loop_mode_combo.addItem("固定次数循环", "count")
        loop_mode_index = {"until_found": 0, "while_found": 1, "count": 2}.get(step.loop_mode, 0)
        loop_mode_combo.setCurrentIndex(loop_mode_index)
        loop_mode_combo.currentIndexChanged.connect(
            lambda i: self._update_field('loop_mode', loop_mode_combo.currentData())
        )
        loop_widget_layout.addRow("循环模式:", loop_mode_combo)
        
        max_iter_spin = QSpinBox()
        max_iter_spin.setRange(1, 10000)
        max_iter_spin.setValue(step.max_iterations)
        max_iter_spin.valueChanged.connect(lambda v: self._update_field('max_iterations', v))
        loop_widget_layout.addRow("最大迭代次数:", max_iter_spin)
        
        check_interval_spin = QDoubleSpinBox()
        check_interval_spin.setRange(0.1, 60.0)
        check_interval_spin.setSingleStep(0.5)
        check_interval_spin.setValue(step.check_interval)
        check_interval_spin.setSuffix(" 秒")
        check_interval_spin.valueChanged.connect(lambda v: self._update_field('check_interval', v))
        loop_widget_layout.addRow("循环间隔:", check_interval_spin)
        
        loop_widget.setVisible(step.loop_enabled)
        loop_enabled_check.toggled.connect(loop_widget.setVisible)
        loop_layout.addRow("", loop_widget)
        
        self.main_layout.addWidget(loop_group)
        
        # ========== 失败处理 ==========
        fail_group = QGroupBox("失败处理")
        fail_layout = QFormLayout(fail_group)
        
        fail_combo = QComboBox()
        fail_combo.addItems(["停止执行", "继续执行", "跳过此步骤"])
        fail_map = {"stop": 0, "continue": 1, "skip": 2}
        fail_combo.setCurrentIndex(fail_map.get(step.on_fail, 0))
        fail_combo.currentIndexChanged.connect(
            lambda i: self._update_field('on_fail', ["stop", "continue", "skip"][i])
        )
        fail_layout.addRow("失败时:", fail_combo)
        
        self.main_layout.addWidget(fail_group)
    
    # ==================== ROI 分析表单 ====================
    def _build_roi_analysis_form(self, step: RoiAnalysisStep):
        # ========== 参考图片 ==========
        ref_group = QGroupBox("参考图片")
        ref_layout = QVBoxLayout(ref_group)
        
        multi_img_widget = MultiImageWidget()
        multi_img_widget.set_images(step.reference_images)
        multi_img_widget.imagesChanged.connect(lambda v: self._update_field('reference_images', v))
        ref_layout.addWidget(multi_img_widget)
        
        self.main_layout.addWidget(ref_group)
        
        # ========== ROI配置 ==========
        roi_group = QGroupBox("ROI区域配置")
        roi_layout = QFormLayout(roi_group)
        
        roi_widget = RoiConfigWidget()
        roi_widget.set_config({
            'offset_x': step.roi_offset_x,
            'offset_y': step.roi_offset_y,
            'width': step.roi_width,
            'height': step.roi_height
        })
        roi_widget.configChanged.connect(lambda cfg: self._update_roi_config(cfg))
        roi_layout.addRow("区域设置:", roi_widget)
        
        save_corners_check = QCheckBox("导出ROI四个顶点坐标")
        save_corners_check.setChecked(step.save_corners)
        save_corners_check.toggled.connect(lambda v: self._update_field('save_corners', v))
        roi_layout.addRow("", save_corners_check)
        
        corners_prefix_edit = QLineEdit(step.corners_variable_prefix)
        corners_prefix_edit.setPlaceholderText("变量名前缀，如 'roi1'")
        corners_prefix_edit.textChanged.connect(lambda v: self._update_field('corners_variable_prefix', v))
        roi_layout.addRow("顶点变量前缀:", corners_prefix_edit)
        
        self.main_layout.addWidget(roi_group)
        
        # ========== 分析参数 ==========
        analysis_group = QGroupBox("分析参数")
        analysis_layout = QFormLayout(analysis_group)
        
        white_threshold_spin = QSpinBox()
        white_threshold_spin.setRange(0, 255)
        white_threshold_spin.setValue(step.white_threshold)
        white_threshold_spin.valueChanged.connect(lambda v: self._update_field('white_threshold', v))
        analysis_layout.addRow("白色阈值:", white_threshold_spin)
        
        content_threshold_spin = QDoubleSpinBox()
        content_threshold_spin.setRange(0.0, 100.0)
        content_threshold_spin.setSingleStep(0.5)
        content_threshold_spin.setValue(step.content_threshold)
        content_threshold_spin.setSuffix(" %")
        content_threshold_spin.valueChanged.connect(lambda v: self._update_field('content_threshold', v))
        analysis_layout.addRow("内容阈值:", content_threshold_spin)
        
        save_var_edit = QLineEdit(step.save_results_to)
        save_var_edit.setPlaceholderText("保存内容占比到变量")
        save_var_edit.textChanged.connect(lambda v: self._update_field('save_results_to', v))
        analysis_layout.addRow("保存结果到变量:", save_var_edit)
        
        self.main_layout.addWidget(analysis_group)
        
        # ========== 分支逻辑 ==========
        branch_group = QGroupBox("分支逻辑（if/elif/else）")
        branch_layout = QVBoxLayout(branch_group)
        
        branch_editor = BranchEditorWidget("roi_analysis", step.branches)
        branch_editor.branchesChanged.connect(lambda v: self._update_field('branches', v))
        branch_layout.addWidget(branch_editor)
        
        self.main_layout.addWidget(branch_group)
        
        # ========== 循环设置 ==========
        loop_group = QGroupBox("循环设置")
        loop_layout = QFormLayout(loop_group)
        
        loop_enabled_check = QCheckBox("启用循环")
        loop_enabled_check.setChecked(step.loop_enabled)
        loop_enabled_check.toggled.connect(lambda v: self._update_field('loop_enabled', v))
        loop_layout.addRow("", loop_enabled_check)
        
        loop_widget = QWidget()
        loop_widget_layout = QFormLayout(loop_widget)
        loop_widget_layout.setContentsMargins(0, 0, 0, 0)
        
        loop_mode_combo = QComboBox()
        loop_mode_combo.addItem("循环直到内容占比高于阈值", "until_above")
        loop_mode_combo.addItem("循环直到内容占比低于阈值", "until_below")
        loop_mode_combo.addItem("固定次数循环", "count")
        loop_mode_index = {"until_above": 0, "until_below": 1, "count": 2}.get(step.loop_mode, 0)
        loop_mode_combo.setCurrentIndex(loop_mode_index)
        loop_mode_combo.currentIndexChanged.connect(
            lambda i: self._update_field('loop_mode', loop_mode_combo.currentData())
        )
        loop_widget_layout.addRow("循环模式:", loop_mode_combo)
        
        max_iter_spin = QSpinBox()
        max_iter_spin.setRange(1, 10000)
        max_iter_spin.setValue(step.max_iterations)
        max_iter_spin.valueChanged.connect(lambda v: self._update_field('max_iterations', v))
        loop_widget_layout.addRow("最大迭代次数:", max_iter_spin)
        
        check_interval_spin = QDoubleSpinBox()
        check_interval_spin.setRange(0.1, 60.0)
        check_interval_spin.setSingleStep(0.5)
        check_interval_spin.setValue(step.check_interval)
        check_interval_spin.setSuffix(" 秒")
        check_interval_spin.valueChanged.connect(lambda v: self._update_field('check_interval', v))
        loop_widget_layout.addRow("循环间隔:", check_interval_spin)
        
        loop_widget.setVisible(step.loop_enabled)
        loop_enabled_check.toggled.connect(loop_widget.setVisible)
        loop_layout.addRow("", loop_widget)
        
        self.main_layout.addWidget(loop_group)
        
        # ========== 失败处理 ==========
        fail_group = QGroupBox("失败处理")
        fail_layout = QFormLayout(fail_group)
        
        fail_combo = QComboBox()
        fail_combo.addItems(["停止执行", "继续执行"])
        fail_map = {"stop": 0, "continue": 1}
        fail_combo.setCurrentIndex(fail_map.get(step.on_fail, 1))
        fail_combo.currentIndexChanged.connect(
            lambda i: self._update_field('on_fail', ["stop", "continue"][i])
        )
        fail_layout.addRow("失败时:", fail_combo)
        
        self.main_layout.addWidget(fail_group)
    
    # ==================== 鼠标操作表单 ====================
    def _build_mouse_form(self, step: MouseStep):
        """构建鼠标操作表单（支持右键、中键、滚轮）"""
        # ========== 动作配置 ==========
        action_group = QGroupBox("动作配置")
        action_layout = QFormLayout(action_group)

        action_combo = QComboBox()
        action_combo.addItems([
            "左键单击", "左键双击", "右键单击", "中键单击",
            "拖动", "移动", "滚轮滚动"
        ])
        action_list = [
            "click", "double_click", "right_click", "middle_click",
            "drag", "move", "scroll"
        ]
        current_action = getattr(step, 'action', 'click')
        if current_action in action_list:
            action_combo.setCurrentIndex(action_list.index(current_action))
        else:
            action_combo.setCurrentIndex(0)

        def on_action_changed(index):
            action = action_list[index]
            self._update_field('action', action)
            if action == "right_click":
                self._update_field('button', "right")
            elif action == "middle_click":
                self._update_field('button', "middle")
            else:
                self._update_field('button', "left")

        action_combo.currentIndexChanged.connect(on_action_changed)
        action_layout.addRow("动作类型:", action_combo)
        self.form_widgets['action_combo'] = action_combo

        self.main_layout.addWidget(action_group)

        # ========== 坐标设置 ==========
        coord_group = QGroupBox("坐标设置")
        coord_layout = QFormLayout(coord_group)

        use_last_check = QCheckBox("使用上次定位的坐标")
        use_last_check.setChecked(getattr(step, 'use_last_location', True))
        use_last_check.toggled.connect(lambda v: self._update_field('use_last_location', v))
        coord_layout.addRow("", use_last_check)

        x_spin = QSpinBox()
        x_spin.setRange(0, 9999)
        x_spin.setValue(getattr(step, 'x', 0))
        x_spin.setEnabled(not use_last_check.isChecked())
        x_spin.valueChanged.connect(lambda v: self._update_field('x', v))
        coord_layout.addRow("X坐标:", x_spin)
        use_last_check.toggled.connect(lambda v: x_spin.setEnabled(not v))

        y_spin = QSpinBox()
        y_spin.setRange(0, 9999)
        y_spin.setValue(getattr(step, 'y', 0))
        y_spin.setEnabled(not use_last_check.isChecked())
        y_spin.valueChanged.connect(lambda v: self._update_field('y', v))
        coord_layout.addRow("Y坐标:", y_spin)
        use_last_check.toggled.connect(lambda v: y_spin.setEnabled(not v))

        offset_x_spin = QSpinBox()
        offset_x_spin.setRange(-9999, 9999)
        offset_x_spin.setValue(getattr(step, 'offset_x', 0))
        offset_x_spin.valueChanged.connect(lambda v: self._update_field('offset_x', v))
        coord_layout.addRow("X偏移:", offset_x_spin)

        offset_y_spin = QSpinBox()
        offset_y_spin.setRange(-9999, 9999)
        offset_y_spin.setValue(getattr(step, 'offset_y', 0))
        offset_y_spin.valueChanged.connect(lambda v: self._update_field('offset_y', v))
        coord_layout.addRow("Y偏移:", offset_y_spin)

        self.main_layout.addWidget(coord_group)

        # ========== 拖动设置（条件显示） ==========
        drag_group = QGroupBox("拖动设置")
        drag_layout = QFormLayout(drag_group)

        drag_x_spin = QSpinBox()
        drag_x_spin.setRange(0, 9999)
        drag_x_spin.setValue(getattr(step, 'drag_to_x', 0))
        drag_x_spin.valueChanged.connect(lambda v: self._update_field('drag_to_x', v))
        drag_layout.addRow("目标X:", drag_x_spin)

        drag_y_spin = QSpinBox()
        drag_y_spin.setRange(0, 9999)
        drag_y_spin.setValue(getattr(step, 'drag_to_y', 0))
        drag_y_spin.valueChanged.connect(lambda v: self._update_field('drag_to_y', v))
        drag_layout.addRow("目标Y:", drag_y_spin)

        drag_duration_spin = QDoubleSpinBox()
        drag_duration_spin.setRange(0.0, 10.0)
        drag_duration_spin.setSingleStep(0.1)
        drag_duration_spin.setValue(getattr(step, 'drag_duration', 0.5))
        drag_duration_spin.setSuffix(" 秒")
        drag_duration_spin.valueChanged.connect(lambda v: self._update_field('drag_duration', v))
        drag_layout.addRow("持续时间:", drag_duration_spin)

        drag_group.setVisible(current_action == "drag")
        action_combo.currentIndexChanged.connect(lambda i: drag_group.setVisible(action_list[i] == "drag"))

        self.main_layout.addWidget(drag_group)

        # ========== 滚动设置（条件显示） ==========
        scroll_group = QGroupBox("滚动设置")
        scroll_layout = QFormLayout(scroll_group)

        direction_combo = QComboBox()
        direction_combo.addItem("向上", "up")
        direction_combo.addItem("向下", "down")
        direction_combo.setCurrentIndex(0 if getattr(step, 'scroll_direction', 'up') == 'up' else 1)
        direction_combo.currentIndexChanged.connect(
            lambda i: self._update_field('scroll_direction', direction_combo.currentData())
        )
        scroll_layout.addRow("滚动方向:", direction_combo)

        scroll_amount_spin = QSpinBox()
        scroll_amount_spin.setRange(1, 1000)
        scroll_amount_spin.setValue(getattr(step, 'scroll_amount', 1))
        scroll_amount_spin.valueChanged.connect(lambda v: self._update_field('scroll_amount', v))
        scroll_layout.addRow("滚动量:", scroll_amount_spin)

        scroll_group.setVisible(current_action == "scroll")
        action_combo.currentIndexChanged.connect(
            lambda i: scroll_group.setVisible(action_list[i] == "scroll")
        )

        self.main_layout.addWidget(scroll_group)

        # ========== 延迟设置 ==========
        delay_group = QGroupBox("延迟设置")
        delay_layout = QFormLayout(delay_group)

        before_spin = QDoubleSpinBox()
        before_spin.setRange(0.0, 60.0)
        before_spin.setSingleStep(0.1)
        before_spin.setValue(getattr(step, 'delay_before', 0.0))
        before_spin.setSuffix(" 秒")
        before_spin.valueChanged.connect(lambda v: self._update_field('delay_before', v))
        delay_layout.addRow("操作前延迟:", before_spin)

        after_spin = QDoubleSpinBox()
        after_spin.setRange(0.0, 60.0)
        after_spin.setSingleStep(0.1)
        after_spin.setValue(getattr(step, 'delay_after', 0.0))
        after_spin.setSuffix(" 秒")
        after_spin.valueChanged.connect(lambda v: self._update_field('delay_after', v))
        delay_layout.addRow("操作后延迟:", after_spin)

        self.main_layout.addWidget(delay_group)

    # ==================== 键盘操作表单 ====================
    def _build_keyboard_form(self, step: KeyboardStep):
        """构建键盘操作表单（仅输入文本和按键序列）"""
        # ========== 操作类型 ==========
        action_group = QGroupBox("操作类型")
        action_layout = QFormLayout(action_group)

        action_combo = QComboBox()
        action_combo.addItems(["输入文本", "按键序列"])
        action_map = {"type_text": 0, "press_keys": 1}
        action_combo.setCurrentIndex(action_map.get(step.action, 0))
        action_combo.currentIndexChanged.connect(
            lambda i: self._update_field('action', ["type_text", "press_keys"][i])
        )
        action_layout.addRow("类型:", action_combo)
        self.form_widgets['action_combo'] = action_combo

        self.main_layout.addWidget(action_group)

        # ========== 输入文本（条件显示） ==========
        text_group = QGroupBox("文本输入")
        text_layout = QFormLayout(text_group)

        text_edit = QTextEdit(step.text)
        text_edit.setPlaceholderText("输入要发送的文本...")
        text_edit.setMaximumHeight(80)
        text_edit.textChanged.connect(lambda: self._update_field('text', text_edit.toPlainText()))
        text_layout.addRow("内容:", text_edit)

        text_group.setVisible(step.action == "type_text")
        action_combo.currentIndexChanged.connect(lambda i: text_group.setVisible(i == 0))
        self.main_layout.addWidget(text_group)

        # ========== 按键序列（条件显示） ==========
        keys_group = QGroupBox("按键序列")
        keys_layout = QFormLayout(keys_group)

        keys_recorder = KeyRecorderWidget()
        keys_recorder.set_keys(step.keys)
        keys_recorder.keysChanged.connect(lambda v: self._update_field('keys', v))
        keys_layout.addRow("按键记录:", keys_recorder)

        keys_group.setVisible(step.action == "press_keys")
        action_combo.currentIndexChanged.connect(lambda i: keys_group.setVisible(i == 1))
        self.main_layout.addWidget(keys_group)

        # ========== 输入选项 ==========
        option_group = QGroupBox("输入选项")
        option_layout = QFormLayout(option_group)

        enter_check = QCheckBox("输入后按回车")
        enter_check.setChecked(step.press_enter)
        enter_check.toggled.connect(lambda v: self._update_field('press_enter', v))
        option_layout.addRow("", enter_check)

        enter_times_spin = QSpinBox()
        enter_times_spin.setRange(1, 10)
        enter_times_spin.setValue(step.enter_times)
        enter_times_spin.valueChanged.connect(lambda v: self._update_field('enter_times', v))
        option_layout.addRow("回车次数:", enter_times_spin)

        self.main_layout.addWidget(option_group)

        # ========== 输入间隔 ==========
        interval_group = QGroupBox("输入间隔")
        interval_layout = QFormLayout(interval_group)

        default_interval_check = QCheckBox("使用默认间隔")
        default_interval_check.setChecked(step.use_default_interval)
        default_interval_check.toggled.connect(lambda v: self._update_field('use_default_interval', v))
        interval_layout.addRow("", default_interval_check)

        custom_interval_spin = QDoubleSpinBox()
        custom_interval_spin.setRange(0.0, 5.0)
        custom_interval_spin.setSingleStep(0.01)
        custom_interval_spin.setValue(step.custom_interval)
        custom_interval_spin.setSuffix(" 秒")
        custom_interval_spin.setEnabled(not step.use_default_interval)
        custom_interval_spin.valueChanged.connect(lambda v: self._update_field('custom_interval', v))
        interval_layout.addRow("自定义间隔:", custom_interval_spin)
        default_interval_check.toggled.connect(lambda v: custom_interval_spin.setEnabled(not v))

        self.main_layout.addWidget(interval_group)

        # ========== 延迟设置 ==========
        delay_group = QGroupBox("延迟设置")
        delay_layout = QFormLayout(delay_group)

        before_spin = QDoubleSpinBox()
        before_spin.setRange(0.0, 60.0)
        before_spin.setSingleStep(0.1)
        before_spin.setValue(step.delay_before)
        before_spin.setSuffix(" 秒")
        before_spin.valueChanged.connect(lambda v: self._update_field('delay_before', v))
        delay_layout.addRow("操作前延迟:", before_spin)

        after_spin = QDoubleSpinBox()
        after_spin.setRange(0.0, 60.0)
        after_spin.setSingleStep(0.1)
        after_spin.setValue(step.delay_after)
        after_spin.setSuffix(" 秒")
        after_spin.valueChanged.connect(lambda v: self._update_field('delay_after', v))
        delay_layout.addRow("操作后延迟:", after_spin)

        self.main_layout.addWidget(delay_group)

    # ==================== 等待表单 ====================
    def _build_wait_form(self, step: WaitStep):
        """构建等待表单"""
        group = QGroupBox("等待设置")
        layout = QFormLayout(group)

        duration_spin = QDoubleSpinBox()
        duration_spin.setRange(0.0, 3600.0)
        duration_spin.setSingleStep(0.5)
        duration_spin.setValue(step.duration)
        duration_spin.setSuffix(" 秒")
        duration_spin.valueChanged.connect(lambda v: self._update_field('duration', v))
        layout.addRow("等待时长:", duration_spin)

        self.main_layout.addWidget(group)
    
    def _update_roi_config(self, config: dict):
        self._update_field('roi_offset_x', config['offset_x'])
        self._update_field('roi_offset_y', config['offset_y'])
        self._update_field('roi_width', config['width'])
        self._update_field('roi_height', config['height'])
