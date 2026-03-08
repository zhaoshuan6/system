#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库连接管理
- 自动启动 MySQL 服务（Windows）
- 自动创建数据库（如果不存在）
- 提供 engine 和 session 的获取方法
"""

import sys
import time
import logging
import subprocess
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pymysql

logger = logging.getLogger(__name__)


# ================================================================
#  自动启动 MySQL 服务
# ================================================================

def start_mysql_service():
    """
    检查 MySQL 服务是否运行，未运行则自动启动（Windows）
    """
    # 先尝试连接，如果能连上就不需要启动
    if _can_connect():
        logger.info("✅ MySQL 服务已在运行")
        return True

    logger.info("MySQL 服务未启动，正在自动启动...")

    # Windows 下常见的 MySQL 服务名
    service_names = ["MySQL", "MySQL80", "MySQL57", "MySQL56", "MySQLXY"]

    for service in service_names:
        try:
            result = subprocess.run(
                ["net", "start", service],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info(f"✅ MySQL 服务 '{service}' 启动成功")
                time.sleep(2)  # 等待服务完全就绪
                return True
            # 如果提示"服务已启动"也算成功
            if "已经启动" in result.stdout or "already been started" in result.stdout:
                logger.info(f"✅ MySQL 服务 '{service}' 已在运行")
                return True
        except subprocess.TimeoutExpired:
            logger.warning(f"启动服务 '{service}' 超时")
        except FileNotFoundError:
            # net 命令不存在（非Windows）
            break
        except Exception as e:
            logger.debug(f"尝试启动 '{service}' 失败: {e}")

    # 所有服务名都失败，最后再尝试连接一次
    time.sleep(1)
    if _can_connect():
        logger.info("✅ MySQL 已可连接")
        return True

    logger.error(
        "❌ 无法自动启动 MySQL 服务\n"
        "请手动启动：以管理员身份运行 cmd，执行 net start MySQL\n"
        "或在任务管理器 → 服务 中手动启动 MySQL"
    )
    return False


def _can_connect() -> bool:
    """尝试连接 MySQL，返回是否成功"""
    from config import MYSQL_CONFIG
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG["host"],
            port=MYSQL_CONFIG["port"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


# ================================================================
#  数据库初始化
# ================================================================

def create_database_if_not_exists():
    """连接 MySQL，如果目标数据库不存在则自动创建"""
    from config import MYSQL_CONFIG

    conn = pymysql.connect(
        host=MYSQL_CONFIG["host"],
        port=MYSQL_CONFIG["port"],
        user=MYSQL_CONFIG["user"],
        password=MYSQL_CONFIG["password"],
        charset=MYSQL_CONFIG["charset"],
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cursor:
            db_name = MYSQL_CONFIG["database"]
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
        logger.info(f"✅ 数据库 '{MYSQL_CONFIG['database']}' 已就绪")
    finally:
        conn.close()


def get_engine():
    """
    获取 SQLAlchemy Engine
    会自动：启动MySQL → 创建数据库 → 创建所有表
    """
    from config import get_db_url
    from backend.database.models import Base

    # 1. 确保 MySQL 服务已启动
    if not start_mysql_service():
        raise RuntimeError(
            "MySQL 服务无法启动，请手动启动后重试\n"
            "管理员CMD执行: net start MySQL"
        )

    # 2. 确保数据库存在
    create_database_if_not_exists()

    # 3. 创建 engine 并建表
    engine = create_engine(
        get_db_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
    Base.metadata.create_all(engine)
    logger.info("✅ 所有数据表已就绪")

    return engine


# 模块级单例
_engine = None

def get_db_engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def get_session():
    """获取数据库 Session，用完记得调用 session.close()"""
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()
