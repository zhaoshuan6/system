#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
认证与用户管理路由

  POST /api/auth/login          - 登录（返回 JWT token）
  POST /api/auth/logout         - 登出
  GET  /api/auth/me             - 获取当前用户信息
  POST /api/auth/reset_password - 通过密保重置密码（超管专用）
  GET  /api/auth/users          - 获取用户列表（超管）
  POST /api/auth/users          - 创建普通管理员（超管）
  PUT  /api/auth/users/<id>     - 修改用户（超管）
  DELETE /api/auth/users/<id>   - 删除用户（超管）
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, jsonify, g

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# JWT 密钥：从环境变量读取，未设置时启动报错
_jwt_secret = os.environ.get("JWT_SECRET")
if not _jwt_secret:
    raise RuntimeError(
        "环境变量 JWT_SECRET 未设置！请在启动前执行：\n"
        "  Windows: set JWT_SECRET=<你的随机密钥>\n"
        "  Linux/Mac: export JWT_SECRET=<你的随机密钥>"
    )
JWT_SECRET: str = _jwt_secret
JWT_EXPIRES = 24   # token 有效期（小时）

# 密保问题（固定，答案仅以哈希形式存储在数据库中）
SECRET_QUESTIONS = [
    "您父亲的名字是什么？",
    "您母亲的名字是什么？",
]


# ----------------------------------------------------------------
#  JWT 工具
# ----------------------------------------------------------------

def generate_token(user) -> str:
    payload = {
        "user_id":  user.user_id,
        "username": user.username,
        "role":     user.role,
        "exp":      datetime.utcnow() + timedelta(hours=JWT_EXPIRES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ----------------------------------------------------------------
#  认证装饰器
# ----------------------------------------------------------------

def login_required(f):
    """要求已登录"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"success": False, "error": "未登录，请先登录"}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({"success": False, "error": "登录已过期，请重新登录"}), 401
        g.current_user = payload
        return f(*args, **kwargs)
    return decorated


def superuser_required(f):
    """要求超级管理员"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"success": False, "error": "未登录"}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({"success": False, "error": "登录已过期"}), 401
        if payload.get("role") != "superuser":
            return jsonify({"success": False, "error": "权限不足，需要超级管理员权限"}), 403
        g.current_user = payload
        return f(*args, **kwargs)
    return decorated


def _extract_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("token") or None


# ----------------------------------------------------------------
#  初始化超级管理员
# ----------------------------------------------------------------

def init_superuser():
    """
    系统启动时自动创建超级管理员（如果不存在）。
    初始密码随机生成并打印到日志，请登录后立即修改。
    密保答案从环境变量 SUPERUSER_SECRET_Q1 / SUPERUSER_SECRET_Q2 读取。
    """
    import secrets
    from backend.database.db import get_session
    from backend.database.models import User

    session = get_session()
    try:
        existing = session.query(User).filter_by(username="superuser").first()
        if existing:
            logger.info("超级管理员已存在")
            return

        # 初始密码：随机 12 位，启动时打印一次
        init_password = secrets.token_urlsafe(12)

        secret_q1 = os.environ.get("SUPERUSER_SECRET_Q1", "")
        secret_q2 = os.environ.get("SUPERUSER_SECRET_Q2", "")
        if not secret_q1 or not secret_q2:
            logger.warning(
                "环境变量 SUPERUSER_SECRET_Q1 / SUPERUSER_SECRET_Q2 未设置，"
                "密保功能将不可用！"
            )

        su = User(
            username   = "superuser",
            password   = User.hash_password(init_password),
            role       = "superuser",
            is_active  = True,
            created_by = "system",
            secret_q1  = User.hash_password(secret_q1) if secret_q1 else None,
            secret_q2  = User.hash_password(secret_q2) if secret_q2 else None,
        )
        session.add(su)
        session.commit()
        logger.warning(
            "\n"
            "=" * 60 + "\n"
            f"  超级管理员已创建！\n"
            f"  账号：superuser\n"
            f"  初始密码：{init_password}\n"
            f"  请登录后立即修改密码！\n"
            "=" * 60
        )
    except Exception as e:
        session.rollback()
        logger.error(f"创建超级管理员失败: {e}")
    finally:
        session.close()


# ----------------------------------------------------------------
#  POST /api/auth/login
# ----------------------------------------------------------------

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "请输入用户名和密码"}), 400

    from backend.database.db import get_session
    from backend.database.models import User

    session = get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return jsonify({"success": False, "error": "用户名或密码错误"}), 401
        if not user.is_active:
            return jsonify({"success": False, "error": "账号已被禁用，请联系管理员"}), 403
        if not user.check_password(password):
            return jsonify({"success": False, "error": "用户名或密码错误"}), 401

        token = generate_token(user)
        logger.info(f"用户登录: {username} ({user.role})")

        return jsonify({
            "success": True,
            "token":   token,
            "user": {
                "user_id":  user.user_id,
                "username": user.username,
                "role":     user.role,
            }
        })
    finally:
        session.close()


# ----------------------------------------------------------------
#  GET /api/auth/me
# ----------------------------------------------------------------

@auth_bp.route("/me", methods=["GET"])
@login_required
def get_me():
    return jsonify({"success": True, "user": g.current_user})


# ----------------------------------------------------------------
#  POST /api/auth/logout
# ----------------------------------------------------------------

@auth_bp.route("/logout", methods=["POST"])
def logout():
    # JWT 无状态，前端删除 token 即可
    return jsonify({"success": True, "message": "已登出"})


# ----------------------------------------------------------------
#  GET /api/auth/questions  获取密保问题
# ----------------------------------------------------------------

@auth_bp.route("/questions", methods=["GET"])
def get_questions():
    return jsonify({"success": True, "questions": SECRET_QUESTIONS})


# ----------------------------------------------------------------
#  POST /api/auth/reset_password  通过密保重置密码
# ----------------------------------------------------------------

@auth_bp.route("/reset_password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    answer1      = data.get("answer1", "").strip()
    answer2      = data.get("answer2", "").strip()
    new_password = data.get("new_password", "").strip()

    if not answer1 or not answer2 or not new_password:
        return jsonify({"success": False, "error": "请填写所有字段"}), 400
    if len(new_password) < 6:
        return jsonify({"success": False, "error": "新密码至少6位"}), 400

    from backend.database.db import get_session
    from backend.database.models import User

    session = get_session()
    try:
        su = session.query(User).filter_by(username="superuser").first()
        if not su:
            return jsonify({"success": False, "error": "超级管理员不存在"}), 404
        if not su.check_secret(answer1, answer2):
            return jsonify({"success": False, "error": "密保答案错误"}), 401

        su.password = User.hash_password(new_password)
        session.commit()
        logger.info("超级管理员密码已重置")
        return jsonify({"success": True, "message": "密码重置成功，请重新登录"})
    finally:
        session.close()


# ----------------------------------------------------------------
#  GET /api/auth/users  用户列表（超管）
# ----------------------------------------------------------------

@auth_bp.route("/users", methods=["GET"])
@superuser_required
def list_users():
    from backend.database.db import get_session
    from backend.database.models import User

    session = get_session()
    try:
        users = session.query(User).order_by(User.user_id).all()
        return jsonify({
            "success": True,
            "users": [u.to_dict() for u in users]
        })
    finally:
        session.close()


# ----------------------------------------------------------------
#  POST /api/auth/users  创建普通管理员（超管）
# ----------------------------------------------------------------

@auth_bp.route("/users", methods=["POST"])
@superuser_required
def create_user():
    data     = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "请填写用户名和密码"}), 400
    if len(username) < 3:
        return jsonify({"success": False, "error": "用户名至少3个字符"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "密码至少6位"}), 400

    from backend.database.db import get_session
    from backend.database.models import User

    session = get_session()
    try:
        if session.query(User).filter_by(username=username).first():
            return jsonify({"success": False, "error": f"用户名 '{username}' 已存在"}), 409

        user = User(
            username   = username,
            password   = User.hash_password(password),
            role       = "admin",   # 只能创建普通管理员
            is_active  = True,
            created_by = g.current_user["username"],
        )
        session.add(user)
        session.commit()
        logger.info(f"创建普通管理员: {username}（由 {g.current_user['username']} 创建）")
        return jsonify({"success": True, "message": f"管理员 {username} 创建成功", "user": user.to_dict()})
    finally:
        session.close()


# ----------------------------------------------------------------
#  PUT /api/auth/users/<user_id>  修改用户（重置密码/启用禁用）
# ----------------------------------------------------------------

@auth_bp.route("/users/<int:user_id>", methods=["PUT"])
@superuser_required
def update_user(user_id: int):
    from backend.database.db import get_session
    from backend.database.models import User

    data = request.get_json() or {}
    session = get_session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return jsonify({"success": False, "error": "用户不存在"}), 404
        if user.role == "superuser":
            return jsonify({"success": False, "error": "不能修改超级管理员"}), 403

        if "password" in data and data["password"].strip():
            pwd = data["password"].strip()
            if len(pwd) < 6:
                return jsonify({"success": False, "error": "密码至少6位"}), 400
            user.password = User.hash_password(pwd)

        if "is_active" in data:
            user.is_active = bool(data["is_active"])

        session.commit()
        return jsonify({"success": True, "message": "用户信息已更新", "user": user.to_dict()})
    finally:
        session.close()


# ----------------------------------------------------------------
#  DELETE /api/auth/users/<user_id>  删除用户（超管）
# ----------------------------------------------------------------

@auth_bp.route("/users/<int:user_id>", methods=["DELETE"])
@superuser_required
def delete_user(user_id: int):
    from backend.database.db import get_session
    from backend.database.models import User

    session = get_session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return jsonify({"success": False, "error": "用户不存在"}), 404
        if user.role == "superuser":
            return jsonify({"success": False, "error": "不能删除超级管理员"}), 403

        username = user.username
        session.delete(user)
        session.commit()
        logger.info(f"删除用户: {username}")
        return jsonify({"success": True, "message": f"用户 {username} 已删除"})
    finally:
        session.close()
