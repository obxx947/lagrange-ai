# -*- coding: utf-8 -*-
"""
管理员 API 路由模块
------------------
提供管理员后台全部功能接口：
- 管理员登录（独立密码，从 .env 读取）
- 用户Token充值（127.0.0.1 IP白名单强制限制）
- 充值对账日志查询
- 数据库一键备份

所有管理员接口均需：
1. 管理员 JWT 鉴权
2. 请求来源 IP 为 127.0.0.1（本机）
"""

from fastapi import APIRouter, HTTPException, Depends, Request

from models import (
    AdminLoginRequest, AdminLoginResponse,
    RechargeRequest, RechargeLogResponse,
    MessageResponse,
)
from auth import admin_login
from middleware import get_admin_user, check_admin_ip
from billing_service import recharge_user_tokens, get_recharge_logs
from database import backup_database, cleanup_expired_data

# ==================== 创建路由 ====================
router = APIRouter(prefix="/api/admin", tags=["管理员接口"])


# ==================== 管理员登录 ====================

@router.post("/login", response_model=AdminLoginResponse)
async def api_admin_login(req: AdminLoginRequest, request: Request):
    """
    管理员登录
    
    - 使用独立的强密码验证（从 .env 配置读取）
    - 不检查 IP，允许局域网内登录（但后续操作强制检查IP）
    """
    success, message, token = admin_login(req.password)
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    return AdminLoginResponse(
        access_token=token,
        message=message,
    )


# ==================== Token 充值（核心功能） ====================

@router.post("/recharge")
async def api_recharge(
    req: RechargeRequest,
    request: Request,
    payload: dict = Depends(get_admin_user)
):
    """
    管理员为用户充值平台Token
    
    安全约束：
    - 仅本机 127.0.0.1 可访问
    - 需管理员 JWT 鉴权
    - 所有充值操作永久写入对账日志（recharge_log 表）
    - 不可删除充值日志
    """
    # 强制 IP 白名单检查
    check_admin_ip(request)
    
    admin_id = int(payload["sub"])
    
    success, message, detail = recharge_user_tokens(
        admin_id=admin_id,
        target_username=req.target_username,
        amount=req.amount,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "detail": detail,
    }


# ==================== 充值日志查询 ====================

@router.get("/logs")
async def api_recharge_logs(
    request: Request,
    payload: dict = Depends(get_admin_user),
    limit: int = 50
):
    """
    查询充值对账日志
    
    - 仅本机可访问
    - 返回最近 N 条充值记录
    - 包含操作管理员、目标用户、充值数量、操作时间
    """
    check_admin_ip(request)
    
    logs = get_recharge_logs(limit)
    return {"logs": logs, "count": len(logs)}


# ==================== 数据库备份 ====================

@router.post("/backup")
async def api_backup_database(
    request: Request,
    payload: dict = Depends(get_admin_user)
):
    """
    一键备份 SQLite 数据库
    
    - 仅本机可访问
    - 备份文件存放于 db_backup 目录
    - 文件名包含日期时间戳，不会覆盖历史备份
    """
    check_admin_ip(request)
    
    try:
        backup_path = backup_database()
        return {
            "success": True,
            "message": "数据库备份成功",
            "backup_path": backup_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库备份失败：{str(e)}")


# ==================== 手动清理过期数据 ====================

@router.post("/cleanup")
async def api_cleanup_data(
    request: Request,
    payload: dict = Depends(get_admin_user)
):
    """
    手动执行数据清理（正常情况下由定时任务自动执行）
    
    - 删除超过 7 天的登录日志
    - 删除超过 14 天的聊天记录
    """
    check_admin_ip(request)
    
    try:
        result = cleanup_expired_data()
        return {"success": True, "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据清理失败：{str(e)}")
