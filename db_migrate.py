# -*- coding: utf-8 -*-
"""
数据库迁移工具
-------------
管理 SQLite 数据库的版本迁移和结构变更。
支持迁移脚本的增量和回滚。
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

import config
from database import get_sync_connection, get_db_path


# ==================== 迁移记录表 ====================

def init_migrations():
    """创建迁移记录表"""
    conn = get_sync_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS db_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            description TEXT,
            applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


def get_applied_migrations() -> set:
    """获取已应用的迁移版本"""
    conn = get_sync_connection()
    try:
        rows = conn.execute("SELECT version FROM db_migrations").fetchall()
        return {r["version"] for r in rows}
    except sqlite3.OperationalError:
        init_migrations()
        return set()
    finally:
        conn.close()


# ==================== 迁移定义 ====================

MIGRATIONS = [
    {
        "version": "001_initial",
        "description": "初始数据库结构（5张核心表）",
        "up": """
            -- 此迁移已在 database.py::init_database() 中执行
            -- 此处仅做记录
            SELECT 1;
        """,
        "down": """
            DROP TABLE IF EXISTS simulator_save;
            DROP TABLE IF EXISTS recharge_log;
            DROP TABLE IF EXISTS chat_record;
            DROP TABLE IF EXISTS session_login;
            DROP TABLE IF EXISTS users;
        """,
    },
    {
        "version": "002_add_indexes",
        "description": "添加性能索引",
        "up": """
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_simulator_user ON simulator_save(user_id);
            CREATE INDEX IF NOT EXISTS idx_chat_user_date ON chat_record(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_recharge_target ON recharge_log(target_user_id);
        """,
        "down": """
            DROP INDEX IF EXISTS idx_users_username;
            DROP INDEX IF EXISTS idx_simulator_user;
            DROP INDEX IF EXISTS idx_chat_user_date;
            DROP INDEX IF EXISTS idx_recharge_target;
        """,
    },
    {
        "version": "003_add_user_stats",
        "description": "添加用户统计字段",
        "up": """
            ALTER TABLE users ADD COLUMN total_chats INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE users ADD COLUMN total_saves INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE users ADD COLUMN last_login TEXT;
        """,
        "down": """
            -- SQLite 不支持 DROP COLUMN，需要重建表
            -- 实际生产环境使用 CREATE TABLE ... AS SELECT
        """,
    },
]


# ==================== 迁移执行 ====================

def migrate(version: str = None):
    """
    执行数据库迁移到指定版本
    
    Args:
        version: 目标版本号（None = 最新版本）
    """
    init_migrations()
    applied = get_applied_migrations()
    
    conn = get_sync_connection()
    
    try:
        for mig in MIGRATIONS:
            if mig["version"] in applied:
                continue
            
            print(f"[迁移] 应用 {mig['version']}: {mig['description']}")
            
            # 执行迁移SQL
            for stmt in mig["up"].split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    conn.execute(stmt)
            
            # 记录迁移
            conn.execute(
                "INSERT INTO db_migrations (version, description) VALUES (?, ?)",
                (mig["version"], mig["description"])
            )
            conn.commit()
            print(f"[迁移] ✓ {mig['version']} 完成")
            
            if version and mig["version"] == version:
                break
        
        print("[迁移] 数据库已是最新版本")
        
    except Exception as e:
        conn.rollback()
        print(f"[迁移] ✗ 失败: {e}")
        raise
    finally:
        conn.close()


def rollback(version: str):
    """
    回滚数据库到指定版本
    """
    applied = get_applied_migrations()
    
    if version not in applied:
        print(f"[迁移] 版本 {version} 未应用，无需回滚")
        return
    
    conn = get_sync_connection()
    
    try:
        # 从后往前回滚
        for mig in reversed(MIGRATIONS):
            if mig["version"] not in applied:
                continue
            
            if mig["version"] == version:
                break
            
            print(f"[回滚] 撤销 {mig['version']}: {mig['description']}")
            
            for stmt in mig.get("down", "").split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    conn.execute(stmt)
            
            conn.execute("DELETE FROM db_migrations WHERE version = ?", (mig["version"],))
            conn.commit()
        
        print(f"[回滚] ✓ 已回滚到 {version}")
        
    except Exception as e:
        conn.rollback()
        print(f"[回滚] ✗ 失败: {e}")
        raise
    finally:
        conn.close()


def show_status():
    """显示当前迁移状态"""
    init_migrations()
    applied = get_applied_migrations()
    
    print("=" * 60)
    print("  数据库迁移状态")
    print("=" * 60)
    print(f"  数据库: {get_db_path()}")
    
    for mig in MIGRATIONS:
        status = "✓ 已应用" if mig["version"] in applied else "○ 待应用"
        print(f"  [{status}] {mig['version']} — {mig['description']}")
    
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "migrate":
            migrate(sys.argv[2] if len(sys.argv) > 2 else None)
        elif cmd == "rollback":
            rollback(sys.argv[2] if len(sys.argv) > 2 else "001_initial")
        elif cmd == "status":
            show_status()
        else:
            print("用法: python db_migrate.py [migrate|rollback|status]")
    else:
        show_status()
