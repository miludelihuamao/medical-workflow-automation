# -*- coding: utf-8 -*-
"""
================================================================
【界面 / 登录对话框】

用途：
    程序启动时的登录窗口。
    输入用户名密码，验证通过后返回用户名给主窗口。

职责：
    1. 显示用户名、密码输入框
    2. 手动处理回车键（用户名框 → 密码框 → 登录）
    3. 校验账号密码，成功返回 self.username，失败弹警告

对外接口：
    dialog = LoginDialog()
    if dialog.exec_() == LoginDialog.Accepted:
        username = dialog.username

被谁使用：
    - 月亮副驾/main.py          （程序入口，先弹登录）
    - 界面/主窗口.py            （切换账号时使用）

注：
    当前账号密码硬编码为 F / F，后续可替换为真实验证逻辑。
================================================================
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.username = ""
        self.setWindowTitle("登录")
        self.setFixedSize(300, 180)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        title = QLabel("自动化操作平台")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("用户名")
        layout.addWidget(self.user_edit)

        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("密码")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pass_edit)

        self.btn_login = QPushButton("登录")
        self.btn_login.setDefault(False)          # 关键：取消默认按钮，防止回车直接触发
        self.btn_login.setAutoDefault(False)      # 同样取消自动默认
        self.btn_login.clicked.connect(self._check_login)
        layout.addWidget(self.btn_login)

        tip = QLabel("提示：测试账号 F / F")
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(tip)

        self.setLayout(layout)

    def keyPressEvent(self, event: QKeyEvent):
        """手动处理回车键：用户名框 → 密码框 → 登录"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self.user_edit.hasFocus():
                # 用户名框回车 → 跳到密码框
                self.pass_edit.setFocus()
                return
            elif self.pass_edit.hasFocus():
                # 密码框回车 → 执行登录
                self._check_login()
                return
        # 其他按键交给父类处理
        super().keyPressEvent(event)

    def _check_login(self):
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text()

        # 硬编码验证，后续可替换
        if user == "F" and pwd == "F":
            self.username = user
            self.accept()
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误")