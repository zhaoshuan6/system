#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flask 后端应用入口"""

import os
import sys
import logging
from pathlib import Path

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

app = Flask(__name__)

from config import CORS_ORIGINS
CORS(app,
     origins=CORS_ORIGINS,
     supports_credentials=True,
     expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"])

# 注册蓝图
from backend.api.routes.auth    import auth_bp
from backend.api.routes.search  import search_bp
from backend.api.routes.monitor import monitor_bp
from backend.api.routes.data    import data_bp
from backend.api.routes.history import history_bp

app.register_blueprint(auth_bp,    url_prefix="/api/auth")
app.register_blueprint(search_bp,  url_prefix="/api/search")
app.register_blueprint(monitor_bp, url_prefix="/api/monitor")
app.register_blueprint(data_bp,    url_prefix="/api/data")
app.register_blueprint(history_bp, url_prefix="/api/history")


@app.route("/api/health")
def health():
    return {"status": "ok", "message": "视频检索系统运行中"}


# 启动时初始化超级管理员
with app.app_context():
    try:
        from backend.api.routes.auth import init_superuser
        init_superuser()
    except Exception as e:
        logging.getLogger(__name__).warning(f"超级管理员初始化失败: {e}")


if __name__ == "__main__":
    from config import SERVER_CONFIG
    app.run(
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        debug=SERVER_CONFIG["debug"],
    )
