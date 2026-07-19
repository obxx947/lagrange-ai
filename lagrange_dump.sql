-- ============================================================
-- 拉格朗日AI — SQLite 数据库导出示例
-- 生成：sqlite3 lagrange.db .dump > lagrange_dump.sql
-- ============================================================

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- 数据库元信息
-- 数据库: lagrange.db
-- 应用: 无尽的拉格朗日 AI战术推演中心 v2.0
-- 表数: 5 (users, session_login, chat_record, recharge_log, simulator_save)
-- 导出时间: 2026-07-20

-- users 表结构
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    platform_tokens INTEGER NOT NULL DEFAULT 10000,
    deepseek_input_tokens  INTEGER NOT NULL DEFAULT 0,
    deepseek_output_tokens INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 管理员账号（示例数据）
-- INSERT INTO users VALUES(1,'admin','$2b$12$...','999999999',0,0,'2026-07-20 00:00:00');

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

COMMIT;
