-- ============================================================
-- 拉格朗日AI — 数据库统计视图与预置数据
-- 用法：sqlite3 lagrange.db < ship_stats.sql
-- ============================================================

-- 舰船类型统计视图
CREATE VIEW IF NOT EXISTS v_ship_type_stats AS
SELECT 
    CASE 
        WHEN type = 'battleship' THEN '战列舰'
        WHEN type = 'battlecruiser' THEN '战列巡洋舰'
        WHEN type = 'aircraftcarrier' THEN '航空母舰'
        WHEN type = 'support' THEN '支援舰'
        WHEN type = 'cruiser' THEN '巡洋舰'
        WHEN type = 'destroyer' THEN '驱逐舰'
        WHEN type = 'frigate' THEN '护卫舰'
        WHEN type = 'fighter' THEN '战机'
        WHEN type = 'corvette' THEN '护航艇'
        ELSE type
    END AS ship_type_name,
    type,
    COUNT(*) as count
FROM (
    -- 从 simulator_save 的 JSON 中无法直接统计
    -- 此视图为占位，实际统计由Python完成
    SELECT 'placeholder' as type
)
GROUP BY type;

-- 用户活跃度统计视图
CREATE VIEW IF NOT EXISTS v_user_activity AS
SELECT 
    u.username,
    u.platform_tokens,
    u.created_at,
    COUNT(c.id) as total_chats,
    COALESCE(SUM(c.total_tokens), 0) as total_tokens_used,
    COUNT(s.id) as saved_fleets
FROM users u
LEFT JOIN chat_record c ON u.id = c.user_id
LEFT JOIN simulator_save s ON u.id = s.user_id
GROUP BY u.id;

-- Token消耗统计视图
CREATE VIEW IF NOT EXISTS v_token_stats AS
SELECT 
    date(created_at) as date,
    COUNT(*) as request_count,
    SUM(prompt_tokens) as total_prompt,
    SUM(completion_tokens) as total_completion,
    SUM(total_tokens) as total_tokens
FROM chat_record
GROUP BY date(created_at)
ORDER BY date DESC;

-- 管理员充值汇总视图
CREATE VIEW IF NOT EXISTS v_recharge_summary AS
SELECT 
    t.username as target_user,
    a.username as admin_user,
    COUNT(r.id) as recharge_count,
    SUM(r.amount) as total_recharged
FROM recharge_log r
LEFT JOIN users a ON r.admin_id = a.id
LEFT JOIN users t ON r.target_user_id = t.id
GROUP BY r.target_user_id;
