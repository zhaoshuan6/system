#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
搜索历史路由

  GET    /api/history        - 获取历史列表（超管看全部，普通管理员看自己的）
  DELETE /api/history/<id>   - 删除单条记录
  DELETE /api/history        - 清空历史（超管清全部，普通管理员清自己的）
"""

import logging
from flask import Blueprint, request, jsonify, g
from backend.api.routes.auth import login_required, superuser_required

logger = logging.getLogger(__name__)
history_bp = Blueprint("history", __name__)


# ----------------------------------------------------------------
#  GET /api/history
# ----------------------------------------------------------------

@history_bp.route("/", methods=["GET"])
@login_required
def list_history():
    from backend.database.db import get_session
    from backend.database.models import SearchHistory

    search_type = request.args.get("type")        # 可选：text / image / trajectory
    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    session = get_session()
    try:
        query = session.query(SearchHistory)

        # 普通管理员只能看自己的
        if g.current_user["role"] != "superuser":
            query = query.filter_by(user_id=g.current_user["user_id"])

        if search_type:
            query = query.filter_by(search_type=search_type)

        total = query.count()
        records = (
            query.order_by(SearchHistory.created_at.desc())
                 .offset((page - 1) * per_page)
                 .limit(per_page)
                 .all()
        )

        return jsonify({
            "success": True,
            "total":   total,
            "page":    page,
            "records": [r.to_dict() for r in records],
        })
    finally:
        session.close()


# ----------------------------------------------------------------
#  DELETE /api/history/<id>  删除单条
# ----------------------------------------------------------------

@history_bp.route("/<int:record_id>", methods=["DELETE"])
@login_required
def delete_record(record_id: int):
    from backend.database.db import get_session
    from backend.database.models import SearchHistory

    session = get_session()
    try:
        record = session.query(SearchHistory).filter_by(id=record_id).first()
        if not record:
            return jsonify({"success": False, "error": "记录不存在"}), 404

        # 普通管理员只能删自己的
        if g.current_user["role"] != "superuser" and record.user_id != g.current_user["user_id"]:
            return jsonify({"success": False, "error": "无权删除他人记录"}), 403

        session.delete(record)
        session.commit()
        return jsonify({"success": True, "message": "已删除"})
    finally:
        session.close()


# ----------------------------------------------------------------
#  DELETE /api/history  清空历史
# ----------------------------------------------------------------

@history_bp.route("/", methods=["DELETE"])
@login_required
def clear_history():
    from backend.database.db import get_session
    from backend.database.models import SearchHistory

    search_type = request.args.get("type")  # 可选：只清某类型

    session = get_session()
    try:
        query = session.query(SearchHistory)

        # 普通管理员只能清自己的
        if g.current_user["role"] != "superuser":
            query = query.filter_by(user_id=g.current_user["user_id"])

        if search_type:
            query = query.filter_by(search_type=search_type)

        count = query.count()
        query.delete(synchronize_session=False)
        session.commit()
        logger.info(f"用户 {g.current_user['username']} 清空了 {count} 条搜索历史")
        return jsonify({"success": True, "message": f"已清空 {count} 条记录"})
    finally:
        session.close()
