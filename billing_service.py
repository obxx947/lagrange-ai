# -*- coding: utf-8 -*-
"""
计费服务模块
-----------
管理用户平台Token的查询、扣减、充值操作。
每次AI对话/模拟器分析完成后自动扣减用户Token。
区分「平台可用Token」与「DeepSeek消耗Token」两套统计。
"""

import sqlite3
from typing import Tuple

from database import get_sync_connection


# ==================== Token 查询 ====================

def get_user_tokens(user_id: int) -> int:
    """查询用户剩余平台Token"""
    conn = get_sync_connection()
    row = conn.execute(
        "SELECT platform_tokens FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    
    if row:
        return row["platform_tokens"]
    return 0


def get_user_deepseek_stats(user_id: int) -> dict:
    """查询用户DeepSeek Token累计消耗统计"""
    conn = get_sync_connection()
    row = conn.execute(
        "SELECT deepseek_input_tokens, deepseek_output_tokens FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    
    if row:
        return {
            "input_tokens": row["deepseek_input_tokens"],
            "output_tokens": row["deepseek_output_tokens"],
            "total_tokens": row["deepseek_input_tokens"] + row["deepseek_output_tokens"],
        }
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


# ==================== Token 扣减 ====================

def deduct_tokens(
    user_id: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int
) -> Tuple[bool, str, int]:
    """
    从用户账户扣减平台Token
    
    Args:
        user_id: 用户ID
        prompt_tokens: 本次输入Token数（DeepSeek计费）
        completion_tokens: 本次输出Token数（DeepSeek计费）
        total_tokens: 本次总消耗
    
    Returns:
        (是否成功, 消息, 剩余Token数)
    """
    conn = get_sync_connection()
    
    try:
        # 查询当前余额
        user = conn.execute(
            "SELECT platform_tokens FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            return False, "用户不存在", 0
        
        current_tokens = user["platform_tokens"]
        
        # 检查余额是否充足
        if current_tokens < total_tokens:
            conn.close()
            return False, f"平台Token余额不足（当前：{current_tokens}，需要：{total_tokens}），请联系管理员充值", current_tokens
        
        # 扣减平台Token
        new_balance = current_tokens - total_tokens
        conn.execute(
            "UPDATE users SET platform_tokens = ? WHERE id = ?",
            (new_balance, user_id)
        )
        
        # 累加DeepSeek消耗统计
        conn.execute(
            """UPDATE users 
               SET deepseek_input_tokens = deepseek_input_tokens + ?,
                   deepseek_output_tokens = deepseek_output_tokens + ?
               WHERE id = ?""",
            (prompt_tokens, completion_tokens, user_id)
        )
        
        conn.commit()
        conn.close()
        
        return True, f"Token扣减成功（消耗 {total_tokens}，剩余 {new_balance}）", new_balance
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Token扣减失败：{e}", 0


# ==================== Token 充值（管理员操作） ====================

def recharge_user_tokens(
    admin_id: int,
    target_username: str,
    amount: int
) -> Tuple[bool, str, dict]:
    """
    管理员为用户充值平台Token
    
    Args:
        admin_id: 操作管理员ID
        target_username: 目标用户名
        amount: 充值数量
    
    Returns:
        (成功标志, 消息, 操作详情)
    """
    conn = get_sync_connection()
    
    try:
        # 查找目标用户
        target = conn.execute(
            "SELECT id, username, platform_tokens FROM users WHERE username = ?",
            (target_username,)
        ).fetchone()
        
        if not target:
            conn.close()
            return False, f"用户「{target_username}」不存在", None
        
        target_id = target["id"]
        old_balance = target["platform_tokens"]
        new_balance = old_balance + amount
        
        # 更新余额
        conn.execute(
            "UPDATE users SET platform_tokens = ? WHERE id = ?",
            (new_balance, target_id)
        )
        
        # 写入对账日志（永久保存）
        conn.execute(
            "INSERT INTO recharge_log (admin_id, target_user_id, amount) VALUES (?, ?, ?)",
            (admin_id, target_id, amount)
        )
        
        conn.commit()
        
        detail = {
            "target_username": target_username,
            "amount": amount,
            "old_balance": old_balance,
            "new_balance": new_balance,
        }
        
        conn.close()
        return True, f"充值成功：{target_username} 增加 {amount} Token（{old_balance} → {new_balance}）", detail
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"充值操作失败：{e}", None


# ==================== 充值日志查询 ====================

def get_recharge_logs(limit: int = 50) -> list:
    """查询最近的充值日志"""
    conn = get_sync_connection()
    rows = conn.execute(
        """SELECT r.id, r.admin_id, r.target_user_id, r.amount, r.created_at,
                  a.username as admin_name, t.username as target_name
           FROM recharge_log r
           LEFT JOIN users a ON r.admin_id = a.id
           LEFT JOIN users t ON r.target_user_id = t.id
           ORDER BY r.created_at DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row["id"],
            "admin_id": row["admin_id"],
            "admin_name": row["admin_name"] or "未知",
            "target_user_id": row["target_user_id"],
            "target_name": row["target_name"] or "未知",
            "amount": row["amount"],
            "created_at": row["created_at"],
        })
    
    return logs
