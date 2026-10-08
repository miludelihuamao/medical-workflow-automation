# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 编排配置窗口】

用途：
    编排编辑器。让用户可视化地组合多个原子工作流：
      - 左侧列出所有可用的原子工作流（扫描 数据/工作流/）
      - 中间是一个表格，每行一个节点，可设置"成功跳转"和"失败跳转"
      - 右侧管理已保存的编排文件（数据/编排/）

职责：
    1. 加载/保存编排文件（*.编排.json）
    2. 支持添加、删除、上移、下移节点
    3. 支持给每个节点设置 on_success / on_fail 跳转目标
    4. 树状结构，禁止循环引用

被谁使用：
    - 界面/主窗口.py            （菜单「编排」→「编排管理」）

依赖：
    无（纯 GUI + JSON 读写）
================================================================
"""
import os
import json

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QWidget, QSplitter, QInputDialog,
    QComboBox, QHeaderView, QAbstractItemView, QListWidget, QListWidgetItem,
    QSizePolicy
)
from PyQt5.QtCore import Qt

# 项目根目录 = 月亮副驾/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS_DIR = os.path.join(BASE_DIR, "数据", "工作流")
编排_DIR = os.path.join(BASE_DIR, "数据", "编排")

# 存储用的路径前缀（相对于项目根）
WORKFLOW_PREFIX = "数据/工作流/"

# 布局常量
DIALOG_W = 1400
DIALOG_H = 800
ROW_HEIGHT = 44           # 表格行高
HEADER_HEIGHT = 40        # 表头高度
BUTTON_H = 36             # 按钮统一高度
LEFT_MIN_W = 260          # 左侧列表最小宽度
RIGHT_MIN_W = 280         # 右侧列表最小宽度


class FlowConfigDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编排管理")
        self.resize(DIALOG_W, DIALOG_H)
        self.setMinimumSize(1200, 700)

        self.current_flow_path = None
        self._init_ui()
        self._ensure_dirs()
        self._load_available_workflows()
        self._refresh_flow_list()

    # ==================== UI ====================
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # ---------- 左：可用工作流 ----------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        lbl_left = QLabel("可用原子工作流")
        lbl_left.setStyleSheet("font-weight: bold; font-size: 13px;")
        left_layout.addWidget(lbl_left)

        hint_left = QLabel("双击添加到编排")
        hint_left.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(hint_left)

        self.list_available = QListWidget()
        self.list_available.setStyleSheet(
            "QListWidget::item { padding: 8px 6px; }")
        self.list_available.itemDoubleClicked.connect(self._add_node)
        left_layout.addWidget(self.list_available, stretch=1)

        btn_refresh = QPushButton("刷新列表")
        btn_refresh.setMinimumHeight(BUTTON_H)
        btn_refresh.clicked.connect(self._load_available_workflows)
        left_layout.addWidget(btn_refresh)

        left.setMinimumWidth(LEFT_MIN_W)
        splitter.addWidget(left)

        # ---------- 中：编排表格 ----------
        mid = QWidget()
        mid_layout = QVBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(10)

        lbl_mid = QLabel("当前编排（从第一行开始执行）")
        lbl_mid.setStyleSheet("font-weight: bold; font-size: 13px;")
        mid_layout.addWidget(lbl_mid)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["节点名", "工作流文件", "成功 →", "失败 →", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(True)
        self.table.setStyleSheet(
            "QTableWidget { gridline-color: #e0e0e0; }"
            "QTableWidget::item { padding: 4px 6px; }")

        # 列宽
        header = self.table.horizontalHeader()
        header.setMinimumHeight(HEADER_HEIGHT)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 50)

        mid_layout.addWidget(self.table, stretch=1)

        # 表格操作按钮
        row = QHBoxLayout()
        row.setSpacing(10)

        btn_up = QPushButton("↑ 上移")
        btn_up.setMinimumHeight(BUTTON_H)
        btn_up.setMinimumWidth(90)
        btn_up.clicked.connect(self._move_up)
        row.addWidget(btn_up)

        btn_down = QPushButton("↓ 下移")
        btn_down.setMinimumHeight(BUTTON_H)
        btn_down.setMinimumWidth(90)
        btn_down.clicked.connect(self._move_down)
        row.addWidget(btn_down)

        btn_remove = QPushButton("删除选中行")
        btn_remove.setMinimumHeight(BUTTON_H)
        btn_remove.setMinimumWidth(110)
        btn_remove.clicked.connect(self._remove_node)
        row.addWidget(btn_remove)

        row.addStretch()

        lbl_tip = QLabel("提示：跳转选『结束』= 流程在此终止")
        lbl_tip.setStyleSheet("color: #888; font-size: 11px;")
        row.addWidget(lbl_tip)

        mid_layout.addLayout(row)

        splitter.addWidget(mid)

        # ---------- 右：文件操作 ----------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        info_group = QGroupBox("编排信息")
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(12, 16, 12, 16)

        self.edit_flow_name = QLineEdit()
        self.edit_flow_name.setPlaceholderText("例如：入院登记全流程")
        self.edit_flow_name.setMinimumHeight(BUTTON_H)
        info_layout.addRow("编排名:", self.edit_flow_name)

        self.lbl_flow_file = QLabel("(未保存)")
        self.lbl_flow_file.setStyleSheet("color: #666; font-size: 11px;")
        self.lbl_flow_file.setWordWrap(True)
        info_layout.addRow("文件:", self.lbl_flow_file)

        right_layout.addWidget(info_group)

        lbl_saved = QLabel("已保存的编排")
        lbl_saved.setStyleSheet("font-weight: bold; font-size: 13px;")
        right_layout.addWidget(lbl_saved)

        hint_right = QLabel("双击加载")
        hint_right.setStyleSheet("color: #888; font-size: 11px;")
        right_layout.addWidget(hint_right)

        self.list_saved = QListWidget()
        self.list_saved.setStyleSheet(
            "QListWidget::item { padding: 8px 6px; }")
        self.list_saved.itemDoubleClicked.connect(self._load_saved_flow)
        right_layout.addWidget(self.list_saved, stretch=1)

        # 文件操作按钮（分行更清晰）
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(8)
        btn_new = QPushButton("新建")
        btn_new.setMinimumHeight(BUTTON_H)
        btn_new.clicked.connect(self._new_flow)
        btn_row1.addWidget(btn_new)
        btn_save = QPushButton("保存")
        btn_save.setMinimumHeight(BUTTON_H)
        btn_save.clicked.connect(self._save_flow)
        btn_row1.addWidget(btn_save)
        right_layout.addLayout(btn_row1)

        btn_del = QPushButton("删除选中的编排")
        btn_del.setMinimumHeight(BUTTON_H)
        btn_del.clicked.connect(self._delete_saved)
        right_layout.addWidget(btn_del)

        right.setMinimumWidth(RIGHT_MIN_W)
        splitter.addWidget(right)

        # 初始比例 2:5:2
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([280, 800, 320])

        layout.addWidget(splitter, stretch=1)

        # 底部关闭
        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setMinimumHeight(BUTTON_H)
        btn_close.setMinimumWidth(100)
        btn_close.clicked.connect(self.reject)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

    # ==================== 初始化 ====================
    def _ensure_dirs(self):
        os.makedirs(WORKFLOWS_DIR, exist_ok=True)
        os.makedirs(编排_DIR, exist_ok=True)

    def _load_available_workflows(self):
        self.list_available.clear()
        if not os.path.exists(WORKFLOWS_DIR):
            return
        for fname in sorted(os.listdir(WORKFLOWS_DIR)):
            if fname.endswith(".json") and not fname.endswith(".编排.json"):
                path = os.path.join(WORKFLOWS_DIR, fname)
                display = fname
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    wf_name = data.get("name", "")
                    if wf_name:
                        display = f"{wf_name}\n{fname}"
                except Exception:
                    pass
                item = QListWidgetItem(display)
                # 存储相对于项目根的路径（数据/工作流/xxx.json）
                item.setData(Qt.UserRole, f"{WORKFLOW_PREFIX}{fname}")
                item.setData(Qt.UserRole + 1, fname)
                self.list_available.addItem(item)

    def _refresh_flow_list(self):
        self.list_saved.clear()
        if not os.path.exists(编排_DIR):
            return
        for fname in sorted(os.listdir(编排_DIR)):
            if fname.endswith(".编排.json"):
                item = QListWidgetItem(fname)
                item.setData(Qt.UserRole, os.path.join(编排_DIR, fname))
                self.list_saved.addItem(item)

    # ==================== 添加节点 ====================
    def _add_node(self, item):
        wf_path = item.data(Qt.UserRole)
        display_name = item.text().split("\n")[0]
        self._append_row(display_name, wf_path)

    def _append_row(self, name, wf_path):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, ROW_HEIGHT)

        # 0 节点名
        self.table.setItem(row, 0, QTableWidgetItem(name))

        # 1 工作流（只读，显示去掉前缀的路径）
        display_path = wf_path
        if display_path.startswith(WORKFLOW_PREFIX):
            display_path = display_path[len(WORKFLOW_PREFIX):]
        wf_item = QTableWidgetItem(display_path)
        wf_item.setFlags(wf_item.flags() & ~Qt.ItemIsEditable)
        wf_item.setToolTip(wf_path)
        self.table.setItem(row, 1, wf_item)

        # 2 成功跳转
        combo_s = QComboBox()
        combo_s.setMinimumHeight(ROW_HEIGHT - 8)
        self.table.setCellWidget(row, 2, combo_s)

        # 3 失败跳转
        combo_f = QComboBox()
        combo_f.setMinimumHeight(ROW_HEIGHT - 8)
        self.table.setCellWidget(row, 3, combo_f)

        # 4 删除按钮
        btn_del = QPushButton("×")
        btn_del.setFixedSize(32, 32)
        btn_del.clicked.connect(
            lambda _, b=btn_del: self._remove_row_by_button(b))
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addStretch()
        wl.addWidget(btn_del)
        wl.addStretch()
        self.table.setCellWidget(row, 4, wrap)

        self._refresh_all_combos()

    def _remove_row_by_button(self, btn):
        for r in range(self.table.rowCount()):
            wrap = self.table.cellWidget(r, 4)
            if wrap is None:
                continue
            inner = wrap.findChild(QPushButton)
            if inner == btn:
                self.table.removeRow(r)
                self._refresh_all_combos()
                return

    def _refresh_all_combos(self):
        """重建所有跳转下拉框的选项"""
        ids = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            name = item.text() if item else ""
            nid = f"n{r+1}"
            ids.append((nid, name))

        for r in range(self.table.rowCount()):
            for col in (2, 3):
                combo = self.table.cellWidget(r, col)
                if combo is None:
                    continue
                current = combo.currentData() if combo.count() > 0 else None
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("结束（终止流程）", None)
                for nid, nname in ids:
                    if nid == f"n{r+1}":
                        continue
                    display = nname if len(nname) <= 12 else nname[:12] + "…"
                    combo.addItem(f"{nid}  {display}", nid)
                if current is not None:
                    idx = combo.findData(current)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.blockSignals(False)

    # ==================== 移动 / 删除 ====================
    def _move_up(self):
        row = self.table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self.table.setCurrentCell(row - 1, 0)

    def _move_down(self):
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount() - 1:
            self._swap_rows(row, row + 1)
            self.table.setCurrentCell(row + 1, 0)

    def _swap_rows(self, r1, r2):
        data1 = self._read_row(r1)
        data2 = self._read_row(r2)
        self._write_row(r1, data2)
        self._write_row(r2, data1)
        self._refresh_all_combos()

    def _read_row(self, r):
        item0 = self.table.item(r, 0)
        item1 = self.table.item(r, 1)
        name = item0.text() if item0 else ""
        wf = item1.text() if item1 else ""
        cs = self.table.cellWidget(r, 2)
        cf = self.table.cellWidget(r, 3)
        s = cs.currentData() if cs else None
        f = cf.currentData() if cf else None
        return name, wf, s, f

    def _write_row(self, r, data):
        name, wf, s, f = data
        if self.table.item(r, 0):
            self.table.item(r, 0).setText(name)
        if self.table.item(r, 1):
            self.table.item(r, 1).setText(wf)
        cs = self.table.cellWidget(r, 2)
        cf = self.table.cellWidget(r, 3)
        if cs:
            idx = cs.findData(s)
            if idx >= 0:
                cs.setCurrentIndex(idx)
        if cf:
            idx = cf.findData(f)
            if idx >= 0:
                cf.setCurrentIndex(idx)

    def _remove_node(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._refresh_all_combos()

    # ==================== 文件操作 ====================
    def _new_flow(self):
        self.table.setRowCount(0)
        self.edit_flow_name.clear()
        self.current_flow_path = None
        self.lbl_flow_file.setText("(未保存)")

    def _save_flow(self):
        name = self.edit_flow_name.text().strip()
        if not name:
            name, ok = QInputDialog.getText(self, "输入编排名", "编排名:")
            if not ok or not name.strip():
                return
            name = name.strip()
            self.edit_flow_name.setText(name)

        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "提示", "编排里还没有节点")
            return

        nodes = []
        for r in range(self.table.rowCount()):
            nid = f"n{r+1}"
            nname = (self.table.item(r, 0).text()
                     if self.table.item(r, 0) else "")
            wf_display = (self.table.item(r, 1).text()
                          if self.table.item(r, 1) else "")
            # 还原成带前缀的完整路径（数据/工作流/xxx.json）
            wf = (wf_display if wf_display.startswith(WORKFLOW_PREFIX)
                  else f"{WORKFLOW_PREFIX}{wf_display}")
            cs = self.table.cellWidget(r, 2)
            cf = self.table.cellWidget(r, 3)
            on_success = cs.currentData() if cs else None
            on_fail = cf.currentData() if cf else None

            nodes.append({
                "id": nid,
                "name": nname,
                "workflow": wf,
                "on_success": on_success,
                "on_fail": on_fail,
            })

        flow_data = {"name": name, "nodes": nodes}

        if self.current_flow_path is None:
            default = os.path.join(编排_DIR, f"{name}.编排.json")
            path, _ = QFileDialog.getSaveFileName(
                self, "保存编排", default, "编排文件 (*.编排.json)")
            if not path:
                return
            if not path.endswith(".编排.json"):
                path += ".编排.json"
            self.current_flow_path = path

        try:
            with open(self.current_flow_path, "w", encoding="utf-8") as f:
                json.dump(flow_data, f, ensure_ascii=False, indent=2)
            self.lbl_flow_file.setText(
                os.path.basename(self.current_flow_path))
            self._refresh_flow_list()
            QMessageBox.information(self, "成功", "已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _load_saved_flow(self, item):
        path = item.data(Qt.UserRole)
        if not os.path.exists(path):
            QMessageBox.warning(self, "提示", "文件不存在")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取失败: {e}")
            return

        self.table.setRowCount(0)
        self.edit_flow_name.setText(data.get("name", ""))
        self.current_flow_path = path
        self.lbl_flow_file.setText(os.path.basename(path))

        for node in data.get("nodes", []):
            wf_path = node.get("workflow", "")
            nname = node.get("name", "")
            self._append_row(nname, wf_path)

        nodes = data.get("nodes", [])
        for r, node in enumerate(nodes):
            if r >= self.table.rowCount():
                break
            cs = self.table.cellWidget(r, 2)
            cf = self.table.cellWidget(r, 3)
            s = node.get("on_success")
            f = node.get("on_fail")
            if cs:
                idx = cs.findData(s)
                if idx >= 0:
                    cs.setCurrentIndex(idx)
            if cf:
                idx = cf.findData(f)
                if idx >= 0:
                    cf.setCurrentIndex(idx)

    def _delete_saved(self):
        item = self.list_saved.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先在右侧列表选择一项")
            return
        path = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认",
            f"确定删除 {os.path.basename(path)} 吗？",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            os.remove(path)
            self._refresh_flow_list()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {e}")