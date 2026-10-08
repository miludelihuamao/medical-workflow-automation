# -*- coding: utf-8 -*-
"""
================================================================
【程序入口】

用途：
    月亮副驾的启动入口。
    负责创建 Qt 应用、初始化主窗口、进入事件循环。

职责：
    1. 创建 QApplication
    2. 根据 ENABLE_LOGIN 决定是否弹登录对话框
    3. 打开主窗口并进入 Qt 事件循环

开关：
    ENABLE_LOGIN = True   启用登录，弹对话框
    ENABLE_LOGIN = False  屏蔽登录，直接用测试用户进入（开发用）
    TEST_USERNAME         屏蔽登录时的用户名

被谁使用：
    直接双击运行，或命令行执行 `python main.py`

依赖：
    - 界面/主窗口.py            （MainWindow）
    - 界面/登录对话框.py         （LoginDialog，按需加载）
================================================================
"""
import sys
from PyQt5.QtWidgets import QApplication

from 界面.主窗口 import MainWindow

# 开关：True = 启用登录，False = 屏蔽登录
ENABLE_LOGIN = False
TEST_USERNAME = "测试用户"


def main():
    app = QApplication(sys.argv)

    if ENABLE_LOGIN:
        from 界面.登录对话框 import LoginDialog
        login = LoginDialog()
        if login.exec_() == LoginDialog.Accepted:
            window = MainWindow(username=login.username)
            window.show()
            sys.exit(app.exec_())
        else:
            sys.exit(0)
    else:
        window = MainWindow(username=TEST_USERNAME)
        window.show()
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()