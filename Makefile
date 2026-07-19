# ============================================================
# 拉格朗日AI — Makefile 构建文件
# 跨平台构建/管理任务定义
# 用法: make [target]
#   make start    - 启动服务
#   make stop     - 停止服务
#   make install  - 安装依赖
#   make test     - 运行测试
#   make backup   - 备份数据库
#   make clean    - 清理缓存
#   make rebuild  - 重建向量索引
#   make export   - 导出舰船数据
#   make all      - 完整安装+启动
# ============================================================

PYTHON := D:/Python312/python.exe
PIP := D:/Python312/Scripts/pip.exe
NODE := node
PORT := 3000

.PHONY: help start stop restart status install test backup clean rebuild export all

help: ## 显示帮助信息
	@echo "拉格朗日AI — Makefile 命令列表"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

start: ## 启动服务
	@echo "[启动] 拉格朗日AI服务..."
	@cmd /c start /MIN $(PYTHON) main.py
	@sleep 3
	@curl -s http://127.0.0.1:$(PORT)/health

stop: ## 停止服务
	@echo "[停止] 拉格朗日AI服务..."
	@taskkill /F /IM python.exe 2>nul || true

restart: stop start ## 重启服务

status: ## 检查服务状态
	@curl -s http://127.0.0.1:$(PORT)/health 2>/dev/null && echo "" || echo "[已停止]"

install: ## 安装Python依赖
	@echo "[安装] Python依赖..."
	@$(PIP) install -r requirements.txt --no-cache-dir
	@echo "[解析] 舰船数据库..."
	@$(NODE) parse_ships.js lagrange_docs/lglrmax.html lagrange_docs/ship_database.json

test: ## 运行自动化测试
	@echo "[测试] API测试..."
	@$(PYTHON) test_api.py

backup: ## 备份数据库
	@echo "[备份] 数据库..."
	@$(PYTHON) -c "from database import backup_database; print(backup_database())"

clean: ## 清理缓存和临时文件
	@echo "[清理] 缓存文件..."
	@rm -rf __pycache__ *.pyc chroma_db/faiss_index.bin 2>/dev/null || true
	@$(PYTHON) -c "from database import cleanup_expired_data; print(cleanup_expired_data())"

rebuild: ## 重建向量索引
	@echo "[重建] 向量索引..."
	@curl -s -X POST http://127.0.0.1:$(PORT)/api/rebuild-index 2>/dev/null || $(PYTHON) -c "from rag_service import build_vector_index; print(build_vector_index())"

export: ## 导出舰船数据
	@echo "[导出] 舰船数据..."
	@$(PYTHON) export_ships.py all

ships-json: ## 解析舰船数据库JSON
	@$(NODE) parse_ships.js lagrange_docs/lglrmax.html lagrange_docs/ship_database.json

lint: ## 代码检查
	@echo "[检查] Python语法..."
	@$(PYTHON) -m py_compile *.py

all: install ships-json start ## 完整安装并启动

dev: ## 开发模式启动
	@echo "[开发] 热重载模式..."
	@$(PYTHON) -c "import uvicorn; uvicorn.run('main:app',host='0.0.0.0',port=$(PORT),reload=True)"
