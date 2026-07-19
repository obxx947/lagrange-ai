# ============================================================
# 拉格朗日AI — Dockerfile
# 构建：docker build -t lagrange-ai .
# 运行：docker run -p 3000:3000 lagrange-ai
# 注意：本项目为局域网单机部署，Dockerfile供参考
# ============================================================

FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要目录
RUN mkdir -p lagrange_docs chroma_db db_backup exports

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://127.0.0.1:3000/health', timeout=3)" || exit 1

# 启动命令
CMD ["python", "main.py"]
