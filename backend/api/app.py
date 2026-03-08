#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask 后端应用入口
"""

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
CORS(app)

# 注册蓝图
from backend.api.routes.search  import search_bp
from backend.api.routes.monitor import monitor_bp
from backend.api.routes.data    import data_bp

app.register_blueprint(search_bp,  url_prefix="/api/search")
app.register_blueprint(monitor_bp, url_prefix="/api/monitor")
app.register_blueprint(data_bp,    url_prefix="/api/data")


@app.route("/api/health")
def health():
    return {"status": "ok", "message": "视频检索系统运行中"}


if __name__ == "__main__":
    from config import SERVER_CONFIG
    app.run(
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        debug=SERVER_CONFIG["debug"],
    )
