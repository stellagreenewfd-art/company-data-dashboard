# -*- coding: utf-8 -*-
"""
PythonAnywhere WSGI 入口。
PythonAnywhere 的磁盘是持久的，SQLite 数据库文件会一直保留，
无需任何外部数据库或持久盘挂载。

部署时，在 PythonAnywhere 的 Web 标签里把 WSGI 配置文件指向本文件，
或将其内容替换为：

    import sys
    path = '/home/<你的用户名>/company-data-dashboard'
    if path not in sys.path:
        sys.path.insert(0, path)
    from app import app as application
"""
import sys
import os

# 项目根目录（根据实际部署路径修改）
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# 生产环境：从环境变量读取密钥（PythonAnywhere 的环境变量面板设置 SECRET_KEY）
# 若未设置则使用下方默认值（仅建议本地测试，线上请务必在 PA 环境变量里设置 SECRET_KEY）
os.environ.setdefault("SECRET_KEY", "3c0f5301c429c07bd8ed52dc2b163b89c374a89e8f788831")
# PythonAnywhere 自带 HTTPS，开启 Secure Cookie
os.environ.setdefault("SECURE_COOKIES", "1")

from app import app as application  # noqa: E402

if __name__ == "__main__":
    application.run()
