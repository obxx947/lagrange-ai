-- ============================================================
-- 拉格朗日智能体 - 数据库完整Schema
-- SQLite版本，包含建表、索引、约束、初始化数据、存储过程模拟
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    platform_tokens INTEGER NOT NULL DEFAULT 10000,
    deepseek_input_tokens INTEGER NOT NULL DEFAULT 0,
    deepseek_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_chat_count INTEGER NOT NULL DEFAULT 0,
    last_login_at TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 会话登录表
CREATE TABLE IF NOT EXISTS session_login (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    jwt_token_hash TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    is_valid INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 聊天记录表
CREATE TABLE IF NOT EXISTS chat_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source_docs TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    model_name TEXT NOT NULL DEFAULT 'deepseek-chat',
    rag_chunks_used INTEGER NOT NULL DEFAULT 0,
    response_time_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 充值日志表
CREATE TABLE IF NOT EXISTS recharge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    target_user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT,
    before_balance INTEGER NOT NULL,
    after_balance INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (admin_id) REFERENCES users(id),
    FOREIGN KEY (target_user_id) REFERENCES users(id)
);

-- 舰队存档表
CREATE TABLE IF NOT EXISTS simulator_save (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    save_name TEXT NOT NULL,
    fleet_config TEXT NOT NULL,
    battle_mode TEXT NOT NULL DEFAULT 'escort',
    bomb_distance REAL NOT NULL DEFAULT 15.0,
    total_command_value INTEGER NOT NULL DEFAULT 0,
    ship_count INTEGER NOT NULL DEFAULT 0,
    is_public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 战斗历史表
CREATE TABLE IF NOT EXISTS battle_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    save_id INTEGER,
    ally_fleet_json TEXT NOT NULL,
    enemy_fleet_json TEXT NOT NULL,
    winner TEXT NOT NULL,
    duration REAL NOT NULL,
    ally_total_damage REAL NOT NULL DEFAULT 0,
    enemy_total_damage REAL NOT NULL DEFAULT 0,
    ally_ships_lost INTEGER NOT NULL DEFAULT 0,
    enemy_ships_lost INTEGER NOT NULL DEFAULT 0,
    battle_log TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (save_id) REFERENCES simulator_save(id) ON DELETE SET NULL
);

-- 舰船评分缓存表
CREATE TABLE IF NOT EXISTS ship_score_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ship_id TEXT NOT NULL UNIQUE,
    tank_score REAL NOT NULL DEFAULT 0,
    dps_score REAL NOT NULL DEFAULT 0,
    support_score REAL NOT NULL DEFAULT 0,
    carrier_score REAL NOT NULL DEFAULT 0,
    overall_score REAL NOT NULL DEFAULT 0,
    meta_tier TEXT NOT NULL DEFAULT 'B',
    calculated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ==================== 索引 ====================

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);

CREATE INDEX IF NOT EXISTS idx_session_expires ON session_login(expires_at);
CREATE INDEX IF NOT EXISTS idx_session_user ON session_login(user_id);
CREATE INDEX IF NOT EXISTS idx_session_valid ON session_login(is_valid);

CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_record(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_record(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_user_created ON chat_record(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_recharge_target ON recharge_log(target_user_id);
CREATE INDEX IF NOT EXISTS idx_recharge_admin ON recharge_log(admin_id);
CREATE INDEX IF NOT EXISTS idx_recharge_created ON recharge_log(created_at);

CREATE INDEX IF NOT EXISTS idx_save_user ON simulator_save(user_id);
CREATE INDEX IF NOT EXISTS idx_save_updated ON simulator_save(updated_at);
CREATE INDEX IF NOT EXISTS idx_save_public ON simulator_save(is_public);

CREATE INDEX IF NOT EXISTS idx_battle_user ON battle_history(user_id);
CREATE INDEX IF NOT EXISTS idx_battle_created ON battle_history(created_at);
CREATE INDEX IF NOT EXISTS idx_battle_winner ON battle_history(winner);

CREATE INDEX IF NOT EXISTS idx_score_ship ON ship_score_cache(ship_id);
CREATE INDEX IF NOT EXISTS idx_score_tier ON ship_score_cache(meta_tier);

-- ==================== 初始化数据 ====================

-- 管理员账户（密码: admin_lagrange_2024）
INSERT OR IGNORE INTO users (username, password_hash, platform_tokens, is_admin, is_active)
VALUES ('admin', '$2b$12$LJ3m4ys3LlGQqDf8xPqPDe0mGvXoMvK.yFZQZ5k7J7LZ6NQHBTWXO', 999999, 1, 1);

-- 测试用户
INSERT OR IGNORE INTO users (username, password_hash, platform_tokens, is_active)
VALUES ('test_user', '$2b$12$TestHashForTestUser12345678901234567890', 10000, 1);

-- 预设舰队存档
INSERT OR IGNORE INTO simulator_save (user_id, save_name, fleet_config, battle_mode, total_command_value, ship_count)
VALUES (2, '新手推荐舰队', '{"tanks":[{"id":"CAS066-A","count":2}],"dps":[{"id":"ranger-A","count":3}]}', 'escort', 126, 5);

-- 舰船评分初始化（部分）
INSERT OR IGNORE INTO ship_score_cache (ship_id, tank_score, dps_score, support_score, carrier_score, overall_score, meta_tier)
VALUES
  ('CAS066-A', 22.5, 35.8, 15.2, 10.1, 28.4, 'B'),
  ('chimera-A', 35.2, 42.1, 18.5, 12.3, 35.6, 'A'),
  ('callisto-A', 18.3, 52.6, 10.2, 8.5, 38.9, 'S'),
  ('io-A', 20.1, 48.7, 12.4, 9.2, 35.8, 'A'),
  ('CV3000-A1', 15.2, 28.4, 38.6, 45.2, 32.1, 'A');

-- ==================== 存储过程模拟（触发器） ====================

-- 自动更新 users.updated_at
CREATE TRIGGER IF NOT EXISTS trg_users_updated
    AFTER UPDATE ON users
    FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = datetime('now', 'localtime') WHERE id = NEW.id;
END;

-- 自动更新 simulator_save.updated_at
CREATE TRIGGER IF NOT EXISTS trg_save_updated
    AFTER UPDATE ON simulator_save
    FOR EACH ROW
BEGIN
    UPDATE simulator_save SET updated_at = datetime('now', 'localtime') WHERE id = NEW.id;
END;

-- 充值后自动更新用户余额
CREATE TRIGGER IF NOT EXISTS trg_recharge_balance
    AFTER INSERT ON recharge_log
    FOR EACH ROW
BEGIN
    UPDATE users SET
        platform_tokens = NEW.after_balance,
        updated_at = datetime('now', 'localtime')
    WHERE id = NEW.target_user_id;
END;

-- 聊天后自动更新用户统计
CREATE TRIGGER IF NOT EXISTS trg_chat_stats
    AFTER INSERT ON chat_record
    FOR EACH ROW
BEGIN
    UPDATE users SET
        deepseek_input_tokens = deepseek_input_tokens + NEW.prompt_tokens,
        deepseek_output_tokens = deepseek_output_tokens + NEW.completion_tokens,
        total_chat_count = total_chat_count + 1,
        updated_at = datetime('now', 'localtime')
    WHERE id = NEW.user_id;
END;

-- ==================== 视图 ====================

-- 用户活跃度视图
CREATE VIEW IF NOT EXISTS v_user_activity AS
SELECT
    u.id,
    u.username,
    u.platform_tokens,
    u.total_chat_count,
    COUNT(c.id) as recent_chats_7d,
    MAX(c.created_at) as last_chat_at,
    COUNT(b.id) as total_battles,
    u.created_at
FROM users u
LEFT JOIN chat_record c ON u.id = c.user_id
    AND c.created_at >= datetime('now', '-7 days')
LEFT JOIN battle_history b ON u.id = b.user_id
GROUP BY u.id;

-- 舰队排行视图
CREATE VIEW IF NOT EXISTS v_fleet_leaderboard AS
SELECT
    u.username,
    s.save_name,
    s.total_command_value,
    s.ship_count,
    COUNT(b.id) as battle_count,
    SUM(CASE WHEN b.winner = 'ally' THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN b.winner = 'ally' THEN 1 ELSE 0 END) AS REAL) /
          MAX(COUNT(b.id), 1) * 100, 1) as win_rate
FROM simulator_save s
JOIN users u ON s.user_id = u.id
LEFT JOIN battle_history b ON s.id = b.save_id
WHERE s.is_public = 1
GROUP BY s.id
HAVING battle_count >= 5
ORDER BY win_rate DESC;

-- 舰船使用率视图
CREATE VIEW IF NOT EXISTS v_ship_usage AS
SELECT
    sc.ship_id,
    sc.meta_tier,
    sc.tank_score,
    sc.dps_score,
    sc.support_score,
    sc.carrier_score,
    sc.overall_score,
    COUNT(DISTINCT s.id) as times_saved,
    COUNT(DISTINCT b.id) as times_battled,
    ROUND(AVG(CASE WHEN b.winner = 'ally' THEN 1.0 ELSE 0.0 END) * 100, 1) as avg_win_rate
FROM ship_score_cache sc
LEFT JOIN simulator_save s ON s.fleet_config LIKE '%' || sc.ship_id || '%'
LEFT JOIN battle_history b ON s.id = b.save_id
GROUP BY sc.ship_id;
