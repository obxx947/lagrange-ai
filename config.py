# -*- coding: utf-8 -*-
"""
项目配置模块
-----------
从 .env 文件加载所有配置项，提供全局配置访问。
启动时若 DEEPSEEK_API_KEY 未配置则直接抛出错误，禁止无密钥运行。
"""

import os
from pathlib import Path

# ==================== 项目根目录 ====================
BASE_DIR = Path(__file__).resolve().parent

# ==================== 尝试加载 .env 文件 ====================
try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # .env 不存在时尝试加载模板提示
        print(f"[警告] 未找到 .env 文件，请在 {BASE_DIR} 创建 .env 文件并填入配置")
except ImportError:
    print("[警告] python-dotenv 未安装，将直接读取系统环境变量")

# ==================== DeepSeek API 配置 ====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    raise RuntimeError(
        "❌ 严重错误：DEEPSEEK_API_KEY 未在 .env 文件或环境变量中配置！\n"
        "   请复制 .env.template 为 .env 并填入有效的 API Key 后重新启动。"
    )

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")

# ==================== 管理员配置 ====================
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin_lagrange_2024")

# ==================== JWT 配置 ====================
JWT_SECRET = os.getenv("JWT_SECRET", "lagrange-jwt-secret-key-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7  # JWT 有效期 7 天

# ==================== 数据库配置 ====================
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "lagrange.db"))
DB_BACKUP_DIR = os.getenv("DB_BACKUP_DIR", str(BASE_DIR / "db_backup"))

# ==================== ChromaDB 向量库配置 ====================
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "chroma_db"))
CHROMA_COLLECTION_NAME = "lagrange_knowledge"

# ==================== 文档路径配置 ====================
LAGRANGE_DOCS_PATH = os.getenv("LAGRANGE_DOCS_PATH", str(BASE_DIR / "lagrange_docs"))
DESKTOP_MATERIALS_PATH = os.getenv(
    "DESKTOP_MATERIALS_PATH",
    str(Path.home() / "Desktop" / "质料")  # 适配中文路径
)

# ==================== 服务器配置 ====================
HOST = os.getenv("HOST", "0.0.0.0")  # 监听所有网卡，局域网可访问
PORT = int(os.getenv("PORT", "3000"))

# ==================== 限流配置 ====================
RATE_LIMIT_MAX = 10      # 每小时最大请求数
RATE_LIMIT_WINDOW = 3600 # 限流窗口（秒）

# ==================== 新用户默认Token ====================
DEFAULT_NEW_USER_TOKENS = 10000

# ==================== 文档分块配置 ====================
CHUNK_SIZE = 500      # 每个文本块字符数
CHUNK_OVERLAP = 50    # 块之间重叠字符数
RETRIEVAL_TOP_K = 5   # 检索返回的相关文档块数量
