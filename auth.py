# -*- coding: utf-8 -*-
"""
认证模块
-------
提供 JWT 签发/验证、bcrypt 密码哈希、用户注册/登录等核心认证功能。
所有密码使用 bcrypt 加盐加密存储，全程不采集手机号/邮箱等隐私信息。
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple

from jose import jwt, JWTError
from passlib.context import CryptContext

import config
from database import get_sync_connection

# ==================== bcrypt 密码哈希配置 ====================
# cost=12 确保足够的哈希强度
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 加盐哈希"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


# ==================== JWT 签发与验证 ====================

def create_jwt_token(user_id: int, username: str, is_admin: bool = False) -> str:
    """
    签发 JWT 访问凭证
    
    Args:
        user_id: 用户ID
        username: 用户名
        is_admin: 是否为管理员Token
    
    Returns:
        JWT 字符串，有效期7天
    """
    now = datetime.utcnow()
    expire = now + timedelta(days=config.JWT_EXPIRATION_DAYS)
    
    payload = {
        "sub": str(user_id),        # subject：用户ID
        "username": username,       # 用户名
        "is_admin": is_admin,       # 管理员标识
        "iat": now,                 # 签发时间
        "exp": expire,              # 过期时间
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    
    # 记录登录会话到数据库
    _record_session(user_id, token, expire)
    
    return token


def verify_jwt_token(token: str) -> Optional[dict]:
    """
    验证 JWT Token 有效性
    
    Returns:
        成功返回 payload 字典，失败返回 None
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def _record_session(user_id: int, token: str, expires_at: datetime):
    """记录登录会话到 session_login 表"""
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
    
    try:
        conn = get_sync_connection()
        conn.execute(
            "INSERT INTO session_login (user_id, jwt_token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, token_hash, expires_at.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 会话记录失败不影响登录流程


# ==================== 用户注册/登录业务逻辑 ====================

def register_user(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """
    注册新用户
    
    Args:
        username: 用户名（2-32字符）
        password: 密码（4-64字符）
    
    Returns:
        (成功标志, 消息, 用户数据)
    """
    conn = get_sync_connection()
    
    # 检查用户名是否已存在
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    
    if existing:
        conn.close()
        return False, "用户名已被注册，请更换用户名", None
    
    # 创建用户
    password_hash = hash_password(password)
    try:
        cursor = conn.execute(
            """INSERT INTO users (username, password_hash, platform_tokens) 
               VALUES (?, ?, ?)""",
            (username, password_hash, config.DEFAULT_NEW_USER_TOKENS)
        )
        user_id = cursor.lastrowid
        conn.commit()
        
        user_data = {
            "id": user_id,
            "username": username,
            "platform_tokens": config.DEFAULT_NEW_USER_TOKENS,
        }
        conn.close()
        return True, f"注册成功！已赠送 {config.DEFAULT_NEW_USER_TOKENS} 平台Token", user_data
    except sqlite3.IntegrityError:
        conn.close()
        return False, "注册失败，用户名可能已存在", None


def login_user(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """
    用户登录验证
    
    Args:
        username: 用户名
        password: 明文密码
    
    Returns:
        (成功标志, 消息, {user数据 + JWT Token})
    """
    conn = get_sync_connection()
    
    user = conn.execute(
        "SELECT id, username, password_hash, platform_tokens FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    
    if not user:
        conn.close()
        return False, "用户名或密码错误", None
    
    if not verify_password(password, user["password_hash"]):
        conn.close()
        return False, "用户名或密码错误", None
    
    # 签发 JWT
    token = create_jwt_token(user["id"], user["username"])
    expires_in = config.JWT_EXPIRATION_DAYS * 24 * 3600
    
    user_data = {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "username": user["username"],
        "platform_tokens": user["platform_tokens"],
    }
    conn.close()
    return True, "登录成功", user_data


def get_user_by_id(user_id: int) -> Optional[dict]:
    """根据ID查询用户信息"""
    conn = get_sync_connection()
    user = conn.execute(
        "SELECT id, username, platform_tokens, deepseek_input_tokens, "
        "deepseek_output_tokens, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None


# ==================== 管理员认证 ====================

def admin_login(password: str) -> Tuple[bool, str, Optional[str]]:
    """
    管理员登录（使用独立密码，从 .env 配置读取）
    
    Returns:
        (成功标志, 消息, JWT Token)
    """
    if password != config.ADMIN_PASSWORD:
        return False, "管理员密码错误", None
    
    # 查找或创建管理员账号
    conn = get_sync_connection()
    admin_user = conn.execute(
        "SELECT id, username FROM users WHERE username = 'admin'"
    ).fetchone()
    
    if not admin_user:
        # 自动创建管理员账号
        password_hash = hash_password(config.ADMIN_PASSWORD)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, platform_tokens) VALUES (?, ?, ?)",
            ("admin", password_hash, 999999999)
        )
        admin_id = cursor.lastrowid
        conn.commit()
    else:
        admin_id = admin_user["id"]
    
    conn.close()
    
    # 签发管理员 JWT
    token = create_jwt_token(admin_id, "admin", is_admin=True)
    return True, "管理员登录成功", token
