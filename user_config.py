# -*- coding: utf-8 -*-
"""
用户自配置系统
--------------
允许用户自行填写 API Key、模型参数、上下文设置，对标 ZCode 体验。
配置存储在 SQLite user_config 表 + localStorage 双重备份。
"""

import json
import sqlite3
from typing import Optional
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "lagrange.db"

DEFAULT_CONFIG = {
    # 大模型
    "llm_provider": "deepseek",          # deepseek / openai / custom
    "llm_api_key": "",
    "llm_api_url": "https://api.deepseek.com",
    "llm_model": "deepseek-chat",
    # 多模型列表（支持多个API/模型）
    "models": [],                         # [{id, name, api_key, api_url, model, provider}]
    "active_model_id": "",
    # Embedding 模型
    "embedding_provider": "openai",       # openai / deepseek / local
    "embedding_api_key": "",
    "embedding_api_url": "https://api.openai.com",
    "embedding_model": "text-embedding-3-small",
    # 联网搜索
    "web_search_provider": "none",        # tavily / serpapi / none
    "web_search_api_key": "",
    # 上下文
    "max_tokens": 100000,
    "max_history_rounds": 50,
    "temperature": 0.3,
}


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_config_table():
    """创建 user_config 表（如果不存在）"""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_config (
            user_id INTEGER PRIMARY KEY,
            config_json TEXT NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def get_user_config(user_id: int) -> dict:
    """获取用户配置，未设置时返回默认值"""
    conn = _get_conn()
    row = conn.execute("SELECT config_json FROM user_config WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        stored = json.loads(row["config_json"])
        # 合并默认值（保证新增字段有默认值）
        cfg = {**DEFAULT_CONFIG, **stored}
        return cfg
    return dict(DEFAULT_CONFIG)


def save_user_config(user_id: int, config: dict) -> dict:
    """保存用户配置（只保存与默认值不同的字段以节省空间）"""
    # 清理：只保留合法字段
    clean = {}
    for k in DEFAULT_CONFIG:
        if k in config:
            clean[k] = config[k]
    conn = _get_conn()
    conn.execute("""
        INSERT INTO user_config (user_id, config_json, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET config_json = excluded.config_json, updated_at = CURRENT_TIMESTAMP
    """, (user_id, json.dumps(clean, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return {**DEFAULT_CONFIG, **clean}


def reset_user_config(user_id: int) -> dict:
    """重置为默认配置"""
    conn = _get_conn()
    conn.execute("DELETE FROM user_config WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return dict(DEFAULT_CONFIG)


def get_effective_llm_config(user_id: int) -> dict:
    """
    获取实际可用的 LLM 配置（用户配置优先，否则回退到系统 .env 配置）。
    返回：{api_key, api_url, model}
    """
    cfg = get_user_config(user_id)
    import config as sys_cfg

    api_key = cfg.get("llm_api_key") or sys_cfg.DEEPSEEK_API_KEY or ""
    api_url = cfg.get("llm_api_url") or "https://api.deepseek.com"
    model = cfg.get("llm_model") or "deepseek-chat"

    # 如果用户选了 openai 但没有填 url，修正
    if cfg.get("llm_provider") == "openai" and not cfg.get("llm_api_url"):
        api_url = "https://api.openai.com"

    return {"api_key": api_key, "api_url": api_url, "model": model}


def get_effective_embedding_config(user_id: int) -> dict:
    """获取实际可用的 Embedding 配置"""
    cfg = get_user_config(user_id)
    return {
        "api_key": cfg.get("embedding_api_key") or cfg.get("llm_api_key") or "",
        "api_url": cfg.get("embedding_api_url") or "https://api.openai.com",
        "model": cfg.get("embedding_model") or "text-embedding-3-small",
    }


# ==================== 本地模式（无登录，JSON文件存储） ====================

LOCAL_CONFIG_FILE = Path(__file__).resolve().parent / "local_config.json"


def _read_local_config() -> dict:
    """读取本地配置文件"""
    if LOCAL_CONFIG_FILE.exists():
        try:
            return json.loads(LOCAL_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_local_config(config: dict):
    """写入本地配置文件"""
    LOCAL_CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def get_local_config() -> dict:
    """获取本地配置（合并默认值）"""
    stored = _read_local_config()
    return {**DEFAULT_CONFIG, **stored}


def save_local_config(config: dict) -> dict:
    """保存本地配置"""
    clean = {k: config[k] for k in DEFAULT_CONFIG if k in config}
    _write_local_config(clean)
    return {**DEFAULT_CONFIG, **clean}


def reset_local_config() -> dict:
    """重置本地配置"""
    if LOCAL_CONFIG_FILE.exists():
        LOCAL_CONFIG_FILE.unlink()
    return dict(DEFAULT_CONFIG)


def get_effective_llm_config(user_id: int = 0) -> dict:
    """
    获取实际可用的 LLM 配置（多模型优先，否则回退默认/环境变量）。
    返回：{api_key, api_url, model, provider, model_name}
    """
    cfg = get_local_config()
    import config as sys_cfg

    # 1. 优先使用 active 模型（多模型列表）
    models = cfg.get("models") or []
    active_id = cfg.get("active_model_id", "")
    if models:
        active = None
        if active_id:
            active = next((m for m in models if m.get("id") == active_id), None)
        if not active:
            active = models[0]
        if active:
            return {
                "api_key": active.get("api_key") or "",
                "api_url": (active.get("api_url") or "https://api.deepseek.com").rstrip("/"),
                "model": active.get("model") or "deepseek-chat",
                "provider": active.get("provider") or "custom",
                "model_name": active.get("name") or active.get("model"),
            }

    # 2. 回退到单模型配置
    api_key = cfg.get("llm_api_key") or sys_cfg.DEEPSEEK_API_KEY or ""
    api_url = cfg.get("llm_api_url") or "https://api.deepseek.com"
    model = cfg.get("llm_model") or "deepseek-chat"

    if cfg.get("llm_provider") == "openai" and not cfg.get("llm_api_url"):
        api_url = "https://api.openai.com"

    return {"api_key": api_key, "api_url": api_url, "model": model, "provider": cfg.get("llm_provider", "deepseek"), "model_name": model}
