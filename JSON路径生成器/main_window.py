# main_window.py
"""
工作流编辑器主窗口
"""
import sys
import os
from typing import Optional, List
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QScrollArea, QToolBar,
    QAction, QFileDialog, QMessageBox, QMenu, QLabel, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence

from models import (
    Workflow, BaseStep, LocateStep, MouseStep, KeyboardStep,
    WaitStep, RoiAnalysisStep,
    get_step_display_name, STEP_TYPE_NAMES
)
from form_builder import StepFormBuilder
from themes import ThemeManager


class WorkflowTreeWidget(QTreeWidget):
    """工作流步骤树形视图"""
    
    stepSelected = pyqtSignal(BaseStep)
    stepMoved = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workflow = None
        self.setup_ui()
    
    def setup_ui(self):
        """初始化UI"""
        self.setHeaderLabel("步骤列表")
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # 信号连接
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def set_workflow(self, workflow: Workflow):
        """设置工作流"""
        self.workflow = workflow
        self.refresh()
    
    def refresh(self):
        """刷新树形视图"""
        self.clear()
        if not self.workflow:
            return
        
        for step in self.workflow.steps:
            self._add_step_item(step, self)
    
    def _add_step_item(self, step: BaseStep, parent):
        item = QTreeWidgetItem(parent)
        item.setText(0, get_step_display_name(step))
        item.setData(0, Qt.UserRole, step)
        return item
    
    def select_step(self, step: BaseStep):
        """选中指定步骤（递归搜索）"""
        def search(item):
            if item.data(0, Qt.UserRole) is step:
                return item
            for i in range(item.childCount()):
                found = search(item.child(i))
                if found:
                    return found
            return None
        
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            found = search(root.child(i))
            if found:
                self.setCurrentItem(found)
                self.scrollToItem(found)
                break
    
    def _on_selection_changed(self):
        """选择改变时触发"""
        items = self.selectedItems()
        if items:
            step = items[0].data(0, Qt.UserRole)
            if step:
                self.stepSelected.emit(step)
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        item = self.itemAt(pos)
        
        menu = QMenu(self)
        
        # 添加步骤菜单（保留，方便在子步骤中添加）
        add_menu = menu.addMenu("➕ 添加步骤")
        for step_type, display_name in STEP_TYPE_NAMES.items():
            action = add_menu.addAction(display_name)
            action.triggered.connect(lambda checked, t=step_type: self._add_new_step(t, item))
        
        if item:
            step = item.data(0, Qt.UserRole)
            if step:
                menu.addSeparator()
                
                # 删除步骤
                delete_action = menu.addAction("🗑️ 删除步骤")
                delete_action.triggered.connect(lambda: self._delete_step(item))
                
                # 复制步骤
                duplicate_action = menu.addAction("📋 复制步骤")
                duplicate_action.triggered.connect(lambda: self._duplicate_step(item))
        
        menu.exec_(self.mapToGlobal(pos))
    
    def _add_new_step(self, step_type: str, parent_item: Optional[QTreeWidgetItem]):
        from models import STEP_TYPE_MAP
        step_class = STEP_TYPE_MAP.get(step_type)
        if not step_class:
            return
        new_step = step_class()
        if parent_item and parent_item.parent() is None:
            # 插入到选中顶层步骤之后
            index = self.indexOfTopLevelItem(parent_item) + 1
            self.workflow.steps.insert(index, new_step)
        else:
            self.workflow.steps.append(new_step)
        self.refresh()
        self.stepMoved.emit()
    def _insert_step_at(self, step: BaseStep, parent_item, index: int):
        # 仅处理顶层插入
        if parent_item is None:
            self.workflow.steps.insert(index, step)
        else:
            # 其他情况忽略或按需处理
            pass

    
    def _delete_step(self, item: QTreeWidgetItem):
        """删除步骤"""
        step = item.data(0, Qt.UserRole)
        if not step:
            return
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除步骤 '{get_step_display_name(step)}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if step in self.workflow.steps:
                self.workflow.steps.remove(step)
            
            self.refresh()
            self.stepMoved.emit()
    
    def _duplicate_step(self, item: QTreeWidgetItem):
        """复制步骤"""
        step = item.data(0, Qt.UserRole)
        if not step:
            return
        
        import copy
        new_step = copy.deepcopy(step)
        new_step.name = f"{step.name} (副本)" if step.name else ""
        
        index = self.workflow.steps.index(step) + 1
        self.workflow.steps.insert(index, new_step)
        
        self.refresh()
        self.stepMoved.emit()


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.workflow = Workflow()
        self.current_file = None
        self.theme_manager = ThemeManager()
        
        self.setup_ui()
        self.setup_actions()
        self.apply_theme()
        
        self.setWindowTitle("工作流编辑器")
        self.resize(1400, 900)
    
    def setup_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.tree_widget = WorkflowTreeWidget()
        self.tree_widget.set_workflow(self.workflow)
        self.tree_widget.stepSelected.connect(self._on_step_selected)
        self.tree_widget.stepMoved.connect(self._on_workflow_changed)
        splitter.addWidget(self.tree_widget)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        
        title_label = QLabel("步骤属性")
        title_label.setObjectName("title")
        right_layout.addWidget(title_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.form_builder = StepFormBuilder()
        self.form_builder.stepChanged.connect(self._on_step_changed)
        scroll_area.setWidget(self.form_builder)
        
        right_layout.addWidget(scroll_area)
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 1000])
        
        main_layout.addWidget(splitter)
        
        self.statusBar().showMessage("就绪")
    
    def setup_actions(self):
        """设置动作"""
        # 文件操作
        new_action = QAction("📄 新建", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_workflow)
        self.toolbar.addAction(new_action)
        
        open_action = QAction("📂 打开", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_workflow)
        self.toolbar.addAction(open_action)
        
        save_action = QAction("💾 保存", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_workflow)
        self.toolbar.addAction(save_action)
        
        save_as_action = QAction("📝 另存为", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.save_workflow_as)
        self.toolbar.addAction(save_as_action)
        
        self.toolbar.addSeparator()
        
        # ========== 添加步骤按钮（一字排开） ==========

        add_mouse = QAction("🖱️ 鼠标操作", self)
        add_mouse.triggered.connect(lambda: self.add_step("mouse"))
        self.toolbar.addAction(add_mouse)
        
        add_keyboard = QAction("⌨️ 键盘输入", self)
        add_keyboard.triggered.connect(lambda: self.add_step("keyboard"))
        self.toolbar.addAction(add_keyboard)

        add_locate = QAction("📍 图像定位", self)
        add_locate.triggered.connect(lambda: self.add_step("locate"))
        self.toolbar.addAction(add_locate)
        
        add_roi = QAction("🔍 ROI分析", self)
        add_roi.triggered.connect(lambda: self.add_step("roi_analysis"))
        self.toolbar.addAction(add_roi)

        add_wait = QAction("⏱️ 等待", self)
        add_wait.triggered.connect(lambda: self.add_step("wait"))
        self.toolbar.addAction(add_wait)        
        self.toolbar.addSeparator()
        
        # 主题切换
        self.theme_action = QAction("🌙 切换深色", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        self.toolbar.addAction(self.theme_action)
    
    def apply_theme(self):
        """应用主题"""
        stylesheet = self.theme_manager.get_stylesheet()
        self.setStyleSheet(stylesheet)
        
        if self.theme_manager.is_dark:
            self.theme_action.setText("☀️ 切换浅色")
        else:
            self.theme_action.setText("🌙 切换深色")
    
    def toggle_theme(self):
        """切换主题"""
        self.theme_manager.toggle_theme()
        self.apply_theme()
    
    def new_workflow(self):
        """新建工作流"""
        if self._check_save_changes():
            self.workflow = Workflow()
            self.current_file = None
            self.tree_widget.set_workflow(self.workflow)
            self.form_builder.build_form(None)
            self.setWindowTitle("工作流编辑器 - 未命名")
            self.statusBar().showMessage("创建新工作流")
    
    def open_workflow(self):
        """打开工作流"""
        if not self._check_save_changes():
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开工作流", "", "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                self.workflow = Workflow.load(file_path)
                self.current_file = file_path
                self.tree_widget.set_workflow(self.workflow)
                self.form_builder.build_form(None)
                self.setWindowTitle(f"工作流编辑器 - {os.path.basename(file_path)}")
                self.statusBar().showMessage(f"已打开: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开文件失败:\n{e}")
    
    def save_workflow(self):
        """保存工作流"""
        if self.current_file:
            try:
                self.workflow.save(self.current_file)
                self.statusBar().showMessage(f"已保存: {self.current_file}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败:\n{e}")
        else:
            self.save_workflow_as()
    
    def save_workflow_as(self):
        """另存为"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存工作流", "", "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                if not file_path.endswith('.json'):
                    file_path += '.json'
                
                self.workflow.save(file_path)
                self.current_file = file_path
                self.setWindowTitle(f"工作流编辑器 - {os.path.basename(file_path)}")
                self.statusBar().showMessage(f"已保存: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败:\n{e}")
    
    def _check_save_changes(self) -> bool:
        """检查是否保存更改"""
        return True
    
    def _on_step_selected(self, step: BaseStep):
        """步骤选中时"""
        self.form_builder.build_form(step)
    
    def _on_step_changed(self, step: BaseStep):
        """步骤属性改变时"""
        self.tree_widget.refresh()
    
    def _on_workflow_changed(self):
        """工作流结构改变时"""
        pass
    
    def add_step(self, step_type: str):
        """添加步骤（工具栏按钮调用）"""
        from models import STEP_TYPE_MAP
        
        step_class = STEP_TYPE_MAP.get(step_type)
        if not step_class:
            return
        
        new_step = step_class()
        self.workflow.steps.append(new_step)
        self.tree_widget.refresh()
        # 自动选中新添加的步骤
        self.tree_widget.select_step(new_step)
        self.statusBar().showMessage(f"已添加步骤: {get_step_display_name(new_step)}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("工作流编辑器")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()