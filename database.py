# -*- coding: utf-8 -*-
"""
SQLite 数据库模块
----------------
管理全部 5 张数据表的创建、迁移和连接。
使用 aiosqlite 实现异步数据库操作。
"""

import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path

import config

# ==================== 数据库连接 ====================

def get_db_path() -> str:
    """获取数据库文件路径，确保目录存在"""
    db_path = Path(config.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


def get_sync_connection() -> sqlite3.Connection:
    """获取同步 SQLite 连接（用于初始化和管理操作）"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # WAL 模式提高并发
    conn.execute("PRAGMA foreign_keys=ON")         # 启用外键约束
    return conn


# ==================== 数据库初始化（5张表） ====================

def init_database():
    """
    初始化数据库：创建全部 5 张表（如不存在则自动创建）
    
    表结构说明：
    1. users          - 用户账号 + 平台Token余额（永久保存）
    2. session_login  - 登录会话日志（7天自动清理）
    3. chat_record    - 服务端对话记录（14天自动清理）
    4. recharge_log   - 管理员充值对账日志（永久保存）
    5. simulator_save - 用户模拟器编队存档（永久保存，绑定user_id）
    """
    conn = get_sync_connection()
    cursor = conn.cursor()

    # -------------------- 1. users 表 --------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    NOT NULL UNIQUE,          -- 用户名（唯一）
            password_hash   TEXT    NOT NULL,                  -- bcrypt 加盐哈希
            platform_tokens INTEGER NOT NULL DEFAULT 10000,   -- 用户可用平台Token
            deepseek_input_tokens  INTEGER NOT NULL DEFAULT 0,-- DeepSeek累计输入Token
            deepseek_output_tokens INTEGER NOT NULL DEFAULT 0,-- DeepSeek累计输出Token
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # -------------------- 2. session_login 表 --------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_login (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,                  -- 关联 users.id
            jwt_token_hash  TEXT    NOT NULL,                  -- JWT 哈希值（用于追踪）
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            expires_at      TEXT    NOT NULL,                  -- 过期时间
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    # 为清理查询创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_expires 
        ON session_login(expires_at)
    """)

    # -------------------- 3. chat_record 表 --------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_record (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,                 -- 关联 users.id
            question         TEXT    NOT NULL,                 -- 用户提问
            answer           TEXT    NOT NULL,                 -- AI 回复
            source_docs      TEXT,                             -- 引用的资料来源（JSON）
            prompt_tokens    INTEGER NOT NULL DEFAULT 0,      -- 输入Token数
            completion_tokens INTEGER NOT NULL DEFAULT 0,     -- 输出Token数
            total_tokens     INTEGER NOT NULL DEFAULT 0,      -- 总消耗Token数
            created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    # 为清理查询创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_created 
        ON chat_record(created_at)
    """)

    # -------------------- 4. recharge_log 表 --------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recharge_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id        INTEGER NOT NULL,                  -- 操作管理员ID
            target_user_id  INTEGER NOT NULL,                  -- 目标用户ID
            amount          INTEGER NOT NULL,                  -- 充值Token数量
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (admin_id)       REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (target_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # -------------------- 5. simulator_save 表 --------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulator_save (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,                     -- 关联 users.id（绑定账号）
            save_name    TEXT    NOT NULL,                     -- 存档名称
            fleet_config TEXT    NOT NULL,                     -- 舰队配置（JSON字符串）
            created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    print(f"[数据库] 初始化完成，数据库路径：{get_db_path()}")


# ==================== 数据库备份 ====================

def backup_database() -> str:
    """
    备份 SQLite 数据库到 db_backup 目录
    返回备份文件路径，文件名包含日期时间戳
    """
    backup_dir = Path(config.DB_BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"lagrange_backup_{timestamp}.db"
    backup_path = backup_dir / backup_name
    
    # 确保所有事务已写入磁盘
    source_conn = get_sync_connection()
    source_conn.execute("PRAGMA wal_checkpoint(FULL)")
    source_conn.close()
    
    # 复制数据库文件
    shutil.copy2(get_db_path(), str(backup_path))
    print(f"[备份] 数据库已备份至：{backup_path}")
    return str(backup_path)


# ==================== 清理过期数据 ====================

def cleanup_expired_data():
    """
    清理过期数据：
    - 删除超过 7 天的登录会话记录
    - 删除超过 14 天的聊天记录
    """
    conn = get_sync_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 删除过期会话（7天）
    cursor.execute(
        "DELETE FROM session_login WHERE expires_at < datetime(?, '-7 days')",
        (now,)
    )
    deleted_sessions = cursor.rowcount
    
    # 删除过期聊天记录（14天）
    cursor.execute(
        "DELETE FROM chat_record WHERE created_at < datetime(?, '-14 days')",
        (now,)
    )
    deleted_chats = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    result = f"[清理] 已清理 {deleted_sessions} 条过期会话、{deleted_chats} 条过期聊天记录"
    print(result)
    return result
