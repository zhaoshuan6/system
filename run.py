#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统启动脚本
用法：python run.py
"""

import os
import sys
from pathlib import Path

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
sys.path.insert(0, str(Path(__file__).parent))

# 将 config.py 中的安全配置注入环境变量（供 auth 模块使用）
from config import SECURITY_CONFIG
os.environ.setdefault("JWT_SECRET",           SECURITY_CONFIG["jwt_secret"])
os.environ.setdefault("SUPERUSER_SECRET_Q1",  SECURITY_CONFIG["superuser_secret_q1"])
os.environ.setdefault("SUPERUSER_SECRET_Q2",  SECURITY_CONFIG["superuser_secret_q2"])

if __name__ == "__main__":
    from config import SERVER_CONFIG
    from backend.api.app import app

    print("=" * 55)
    print("   视频人物检索系统")
    print("=" * 55)
    print(f"  后端地址 : http://localhost:{SERVER_CONFIG['port']}")
    print(f"  健康检查 : http://localhost:{SERVER_CONFIG['port']}/api/health")
    print("  前端页面 : 用浏览器打开 frontend/index.html")
    print("=" * 55)

    app.run(
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        debug=SERVER_CONFIG["debug"],
        threaded=True,   # 支持多线程（视频流需要）
    )
