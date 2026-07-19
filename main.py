# -*- coding: utf-8 -*-
"""
《无尽的拉格朗日》AI 智能体 — FastAPI 主入口
==========================================
完整集成：
- 用户注册/登录（JWT鉴权 + bcrypt密码加密）
- AI 对话（DeepSeek + ChromaDB RAG 检索增强）
- 模拟器编队存档（SQLite 持久化，绑定用户账号）
- 管理员后台（127.0.0.1 白名单，Token充值 + 对账日志）
- 向量库管理（一键重建索引）
- 定时任务（自动清理过期数据 + 每日备份）
- 静态页面托管（一体化前端 + 原品牌展示站）

运行方式：
    python main.py
    或
    uvicorn main:app --host 0.0.0.0 --port 3000
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from database import init_database
from middleware import RateLimitMiddleware
from api_routes import router as api_router
from admin_routes import router as admin_router
from doc_loader import sync_desktop_to_lagrange_docs, check_desktop_folder_exists
from rag_service import build_vector_index, is_index_built
from scheduler import start_scheduler, stop_scheduler


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理
    
    启动时：
    1. 验证 API Key 配置
    2. 初始化 SQLite 数据库
    3. 同步桌面「质料」文件夹
    4. 构建 ChromaDB 向量索引
    5. 启动后台定时任务
    
    关闭时：
    1. 停止定时任务
    2. 清理资源
    """
    # ============ 启动逻辑 ============
    print("=" * 60)
    print("  《无尽的拉格朗日》AI 战术推演中心")
    print("  局域网版本 — 仅本地部署")
    print("=" * 60)
    
    # 1. 验证配置
    print(f"\n[启动] API Key 已配置: {'✓' if config.DEEPSEEK_API_KEY else '✗'}")
    print(f"[启动] 管理密码已配置: {'✓' if config.ADMIN_PASSWORD else '✗'}")
    
    # 2. 初始化数据库
    try:
        init_database()
        print("[启动] ✓ 数据库初始化完成")
    except Exception as e:
        print(f"[启动] ✗ 数据库初始化失败: {e}")
    
    # 3. 同步桌面「质料」文件夹
    print(f"\n[启动] 检查桌面「质料」文件夹: {config.DESKTOP_MATERIALS_PATH}")
    folder_exists = check_desktop_folder_exists()
    if folder_exists:
        sync_result = sync_desktop_to_lagrange_docs()
        print(f"[启动] 文档同步: 同步 {sync_result['synced']} 个, 跳过 {sync_result['skipped']} 个")
    else:
        print("[启动] 桌面「质料」文件夹不存在，跳过文档同步（程序可正常运行）")
    
    # 4. 构建向量索引（首次启动或索引为空时）
    if not is_index_built():
        print("\n[启动] 向量索引为空，开始构建...")
        try:
            build_result = build_vector_index()
            print(f"[启动] ✓ 向量索引构建完成: {build_result.get('chunk_count', 0)} 个文本块")
        except Exception as e:
            print(f"[启动] ✗ 向量索引构建失败: {e}")
            print("         AI对话功能可能无法正常工作，请稍后调用 /api/rebuild-index 重建")
    else:
        print("[启动] ✓ 向量索引已就绪")
    
    # 5. 启动定时任务
    start_scheduler()
    
    print(f"\n[启动] 服务监听: http://{config.HOST}:{config.PORT}")
    print(f"[启动] 本机访问: http://127.0.0.1:{config.PORT}")
    print(f"[启动] 局域网访问: http://<本机内网IP>:{config.PORT}")
    print("=" * 60)
    
    yield  # 应用运行中...
    
    # ============ 关闭逻辑 ============
    print("\n[关闭] 正在停止服务...")
    stop_scheduler()
    print("[关闭] 服务已停止")


# ==================== 创建 FastAPI 应用 ====================

app = FastAPI(
    title="无尽的拉格朗日 AI 战术推演中心",
    description="基于 RAG 增强检索的拉格朗日专业战斗推演智能体，仅限局域网本地部署",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",       # Swagger UI 文档
    redoc_url="/redoc",     # ReDoc 文档
)


# ==================== CORS 跨域配置 ====================
# 允许局域网内所有设备访问 API

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # 允许所有来源（局域网环境安全可控）
    allow_credentials=True,
    allow_methods=["*"],            # 允许所有 HTTP 方法
    allow_headers=["*"],            # 允许所有请求头
)


# ==================== 限流中间件 ====================
# 单用户每小时最多 10 次 AI/模拟器请求

app.add_middleware(RateLimitMiddleware)


# ==================== 注册 API 路由 ====================

app.include_router(api_router)     # 用户端 API
app.include_router(admin_router)   # 管理员 API


# ==================== 静态文件挂载 ====================

# 主前端页面（一体化 SPA）
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 原品牌展示站（React 项目）
serene_dir = Path(__file__).resolve().parent / "serene"
if serene_dir.exists():
    app.mount("/serene", StaticFiles(directory=str(serene_dir), html=True), name="serene")

# 数据导出目录（CSV/TSV等）
exports_dir = Path(__file__).resolve().parent / "exports"
if exports_dir.exists():
    app.mount("/exports", StaticFiles(directory=str(exports_dir)), name="exports")


# ==================== 根路由 ====================

@app.get("/")
async def root():
    """
    根路径 → 返回一体化前端主页面
    """
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": "无尽的拉格朗日 AI 战术推演中心",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    健康检查接口（供局域网设备测试连通性）
    """
    return {
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "index_built": is_index_built(),
    }


# ==================== 直接运行入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    print(f"\n启动 {__file__} ...")
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,           # 生产模式关闭热重载
        log_level="info",
    )
