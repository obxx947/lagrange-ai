# -*- coding: utf-8 -*-
"""
模拟器服务模块
-------------
处理模拟器编队存档的增删改查（绑定用户账号，存入SQLite）。
提供模拟器AI战术分析的接口封装。
"""

import json
from typing import List, Optional, Tuple

from database import get_sync_connection


# ==================== 编队存档 CRUD ====================

def save_fleet_config(
    user_id: int,
    save_name: str,
    fleet_config: dict,
    save_id: Optional[int] = None
) -> Tuple[bool, str, Optional[dict]]:
    """
    保存用户模拟器编队配置
    
    如果提供 save_id 则为更新已有存档，否则创建新存档
    
    Args:
        user_id: 用户ID
        save_name: 存档名称
        fleet_config: 舰队配置JSON
        save_id: 已有存档ID（更新时提供）
    
    Returns:
        (成功标志, 消息, 存档数据)
    """
    conn = get_sync_connection()
    
    try:
        config_json = json.dumps(fleet_config, ensure_ascii=False)
        
        if save_id:
            # 更新已有存档（验证所有权）
            existing = conn.execute(
                "SELECT id FROM simulator_save WHERE id = ? AND user_id = ?",
                (save_id, user_id)
            ).fetchone()
            
            if not existing:
                conn.close()
                return False, "存档不存在或无权修改", None
            
            conn.execute(
                """UPDATE simulator_save 
                   SET save_name = ?, fleet_config = ?, updated_at = datetime('now', 'localtime')
                   WHERE id = ?""",
                (save_name, config_json, save_id)
            )
            conn.commit()
            
            saved = conn.execute(
                "SELECT * FROM simulator_save WHERE id = ?", (save_id,)
            ).fetchone()
        else:
            # 创建新存档
            cursor = conn.execute(
                """INSERT INTO simulator_save (user_id, save_name, fleet_config)
                   VALUES (?, ?, ?)""",
                (user_id, save_name, config_json)
            )
            conn.commit()
            
            saved = conn.execute(
                "SELECT * FROM simulator_save WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        
        conn.close()
        
        result = _format_save_record(saved)
        return True, "存档保存成功", result
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"存档保存失败：{e}", None


def get_user_saves(user_id: int) -> List[dict]:
    """获取用户所有模拟器存档"""
    conn = get_sync_connection()
    rows = conn.execute(
        """SELECT * FROM simulator_save 
           WHERE user_id = ? 
           ORDER BY updated_at DESC""",
        (user_id,)
    ).fetchall()
    conn.close()
    
    return [_format_save_record(row) for row in rows]


def delete_save(user_id: int, save_id: int) -> Tuple[bool, str]:
    """删除用户指定的模拟器存档"""
    conn = get_sync_connection()
    
    existing = conn.execute(
        "SELECT id FROM simulator_save WHERE id = ? AND user_id = ?",
        (save_id, user_id)
    ).fetchone()
    
    if not existing:
        conn.close()
        return False, "存档不存在或无权删除"
    
    conn.execute("DELETE FROM simulator_save WHERE id = ?", (save_id,))
    conn.commit()
    conn.close()
    
    return True, "存档已删除"


def get_save_by_id(user_id: int, save_id: int) -> Optional[dict]:
    """获取单个存档详情"""
    conn = get_sync_connection()
    row = conn.execute(
        "SELECT * FROM simulator_save WHERE id = ? AND user_id = ?",
        (save_id, user_id)
    ).fetchone()
    conn.close()
    
    if row:
        return _format_save_record(row)
    return None


def _format_save_record(row) -> dict:
    """将数据库行转换为字典格式"""
    fleet_config = row["fleet_config"]
    if isinstance(fleet_config, str):
        try:
            fleet_config = json.loads(fleet_config)
        except json.JSONDecodeError:
            fleet_config = {}
    
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "save_name": row["save_name"],
        "fleet_config": fleet_config,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
