# -*- coding: utf-8 -*-
"""
中间件模块
---------
提供 FastAPI 中间件：
1. JWT 鉴权中间件 — 拦截未授权请求，自动处理Token过期
2. 限流中间件 — 单用户每小时最多10次AI/模拟器请求
"""

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from auth import verify_jwt_token
import config

# ==================== JWT 鉴权依赖（用于路由层） ====================

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> dict:
    """
    JWT 鉴权依赖注入
    
    从请求头 Authorization: Bearer <token> 中提取并验证JWT，
    验证通过返回 payload 字典，失败抛出 401。
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="请先登录后再使用此功能")
    
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="登录凭证已过期，请重新登录")
    
    return payload


async def get_admin_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> dict:
    """
    管理员鉴权依赖 — 在 get_current_user 基础上额外验证 is_admin 字段
    """
    payload = await get_current_user(request, credentials)
    
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="无权访问管理员功能")
    
    return payload


# ==================== 管理员IP白名单检查 ====================

def check_admin_ip(request: Request):
    """
    检查请求是否来自本机（127.0.0.1）
    管理员后台仅允许本机访问，局域网其他设备无法进入
    """
    client_host = request.client.host if request.client else ""
    if client_host != "127.0.0.1":
        raise HTTPException(
            status_code=403,
            detail="管理员后台仅限本机(127.0.0.1)访问，当前IP无权限"
        )
    return True


# ==================== 限流中间件 ====================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    单用户限流中间件
    
    规则：每个用户每小时最多 N 次请求（默认10次），
    限流窗口为整点自然小时，非滑动窗口。
    限流数据存储在内存中，服务重启后重置。
    """
    
    def __init__(self, app):
        super().__init__(app)
        # 存储结构：{ user_id: [(timestamp, ...), ...] }
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # 只对 AI 对话和模拟器分析接口限流
        path = request.url.path
        limited_paths = ["/api/chat", "/api/simulator/analyze"]
        
        if not any(path.startswith(p) for p in limited_paths):
            return await call_next(request)
        
        # 提取用户身份（从JWT中解析）
        user_id = await self._extract_user_id(request)
        if not user_id:
            return await call_next(request)
        
        # 检查限流
        if self._is_rate_limited(user_id):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "请求过于频繁，每小时最多10次对话/模拟请求，请稍后再试",
                    "error_code": "RATE_LIMITED"
                }
            )
        
        # 记录本次请求
        self._record_request(user_id)
        
        return await call_next(request)
    
    async def _extract_user_id(self, request: Request) -> str:
        """从请求中提取用户ID"""
        # 尝试从 Authorization 头解析 JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = verify_jwt_token(token)
            if payload:
                return payload.get("sub", "")
        return ""
    
    def _is_rate_limited(self, user_id: str) -> bool:
        """检查用户是否超过限流阈值"""
        now = time.time()
        current_hour_start = now - (now % config.RATE_LIMIT_WINDOW)
        
        # 清理过期记录
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if t >= current_hour_start
        ]
        
        return len(self._requests[user_id]) >= config.RATE_LIMIT_MAX
    
    def _record_request(self, user_id: str):
        """记录一次请求"""
        self._requests[user_id].append(time.time())
