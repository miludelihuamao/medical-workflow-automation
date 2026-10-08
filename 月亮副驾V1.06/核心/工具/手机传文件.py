# -*- coding: utf-8 -*-
"""
================================================================
【核心 / 工具 / 手机传文件】

用途：
    局域网内开网页，手机扫码后可以：
      - 上传文件
      - 提交文字

参考 scanshare 的功能，用 Python 重写，可直接融入 PyQt5 进程。
================================================================
"""
import os
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi


# ==================== HTML 模板 ====================
_上传页面HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>手机传文件</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, sans-serif;
    background: #f5f5f5;
    margin: 0;
    padding: 15px;
    color: #333;
  }
  h1 { color: #333; font-size: 18px; text-align: center; margin-top: 15px; }
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    margin: 15px auto;
    max-width: 500px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  .card h2 { font-size: 15px; margin: 0 0 12px 0; color: #555; }
  input[type="file"] { display: block; margin: 10px 0; font-size: 15px; width: 100%; }
  textarea {
    width: 100%;
    padding: 10px;
    font-size: 15px;
    border: 1px solid #ccc;
    border-radius: 6px;
    resize: vertical;
    min-height: 80px;
    font-family: inherit;
  }
  button {
    background: #4a90e2;
    color: #fff;
    border: none;
    padding: 12px 24px;
    font-size: 16px;
    border-radius: 8px;
    cursor: pointer;
    margin-top: 8px;
    width: 100%;
  }
  button:active { background: #357ab8; }
  .status { margin-top: 8px; color: #666; font-size: 13px; text-align: center; }
</style>
</head>
<body>
  <h1>📱 手机传文件</h1>

  <div class="card">
    <h2>📎 上传文件</h2>
    <form method="POST" enctype="multipart/form-data"
          action="/upload_file" id="form_file">
      <input type="file" name="file" multiple required>
      <button type="submit">上传</button>
      <div class="status" id="status_file"></div>
    </form>
  </div>

  <div class="card">
    <h2>✍️ 提交文字</h2>
    <form method="POST" action="/upload_text" id="form_text">
      <textarea name="text" placeholder="输入要发送的文字..."></textarea>
      <button type="submit">发送</button>
      <div class="status" id="status_text"></div>
    </form>
  </div>

  <script>
    document.getElementById('form_file').onsubmit = function() {
      document.getElementById('status_file').innerText = '上传中...';
    };
    document.getElementById('form_text').onsubmit = function() {
      document.getElementById('status_text').innerText = '发送中...';
    };
  </script>
</body>
</html>
"""

_成功页面HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>发送成功</title>
<style>
  body { font-family: -apple-system, sans-serif; background: #f5f5f5;
         text-align: center; padding: 50px 20px; }
  .check { font-size: 60px; }
  p { color: #333; font-size: 18px; }
  a { color: #4a90e2; text-decoration: none; }
</style>
</head>
<body>
  <div class="check">✅</div>
  <p>发送成功</p>
  <p><a href="/">返回继续</a></p>
</body>
</html>
"""


# ==================== HTTP 处理器 ====================
class _上传请求处理器(BaseHTTPRequestHandler):
    """处理 / 和上传请求"""

    保存目录 = ""
    回调 = None
    文字保存文件 = ""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._返回HTML(_上传页面HTML)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        try:
            if self.path == "/upload_file":
                self._处理文件上传()
            elif self.path == "/upload_text":
                self._处理文字上传()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            print(f"[手机传文件] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()

    # ---------- 文件上传 ----------
    def _处理文件上传(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_response(400)
            self.end_headers()
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )

        保存的文件列表 = []
        file_items = form["file"]
        if not isinstance(file_items, list):
            file_items = [file_items]

        for item in file_items:
            if not item.filename:
                continue
            文件名 = os.path.basename(item.filename)
            保存路径 = os.path.join(self.保存目录, 文件名)
            with open(保存路径, "wb") as f:
                while True:
                    chunk = item.file.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            保存的文件列表.append(保存路径)

        if self.回调 and 保存的文件列表:
            try:
                self.回调("file", 保存的文件列表)
            except Exception as e:
                print(f"[手机传文件] 回调失败: {e}")

        self._返回HTML(_成功页面HTML)

    # ---------- 文字上传 ----------
    def _处理文字上传(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        from urllib.parse import parse_qs
        params = parse_qs(body)
        文本 = params.get("text", [""])[0].strip()

        if not 文本:
            self._返回HTML(_成功页面HTML)
            return

        try:
            with open(self.文字保存文件, "a", encoding="utf-8") as f:
                f.write(文本 + "\n\n")
        except Exception as e:
            print(f"[手机传文件] 文字保存失败: {e}")

        if self.回调:
            try:
                self.回调("text", 文本)
            except Exception as e:
                print(f"[手机传文件] 回调失败: {e}")

        self._返回HTML(_成功页面HTML)

    # ---------- 工具 ----------
    def _返回HTML(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ==================== 服务 ====================
class 手机传文件服务:
    def __init__(self, 保存目录, 端口=8765, 回调=None):
        """
        保存目录: 上传的文件保存到哪里
        端口: HTTP 端口
        回调: 收到内容时调用，参数为 (类型, 数据)
              类型 "file" → 数据是文件路径列表
              类型 "text" → 数据是文本字符串
        """
        self.保存目录 = 保存目录
        self.端口 = 端口
        self.回调 = 回调
        self.服务器 = None
        self.线程 = None
        self.文字保存文件 = os.path.join(保存目录, "收到的文字.txt")

    @staticmethod
    def 获取本机IP():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def 获取URL(self):
        return f"http://{self.获取本机IP()}:{self.端口}"

    def 启动(self):
        if self.服务器 is not None:
            return False
        os.makedirs(self.保存目录, exist_ok=True)

        _上传请求处理器.保存目录 = self.保存目录
        _上传请求处理器.回调 = self.回调
        _上传请求处理器.文字保存文件 = self.文字保存文件

        try:
            self.服务器 = HTTPServer(("0.0.0.0", self.端口),
                                     _上传请求处理器)
        except OSError as e:
            print(f"[手机传文件] 端口 {self.端口} 无法绑定: {e}")
            self.服务器 = None
            return False

        self.线程 = threading.Thread(
            target=self.服务器.serve_forever, daemon=True)
        self.线程.start()
        print(f"[手机传文件] 已启动: {self.获取URL()}")
        return True

    def 停止(self):
        if self.服务器 is None:
            return
        self.服务器.shutdown()
        self.服务器.server_close()
        self.服务器 = None
        self.线程 = None
        print("[手机传文件] 已停止")

    def 是否运行(self):
        return self.服务器 is not None