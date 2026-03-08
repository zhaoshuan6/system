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

if __name__ == "__main__":
    from config import SERVER_CONFIG
    from backend.api.app import app

    print("=" * 55)
    print("  🎥 视频人物检索系统")
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
