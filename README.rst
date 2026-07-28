================================================================================
拉格朗日AI 战术推演中心 — reStructuredText 文档
================================================================================

.. title:: 无尽的拉格朗日 AI战术推演中心
.. author:: Lagrange AI Community
.. date:: 2026-07-27
.. version:: 2.0.0
.. sectnum::
.. contents:: 目录
   :depth: 2
   :local:

概述
====

《无尽的拉格朗日》AI战术推演中心是一个基于 RAG（检索增强生成）技术的
专业战斗推演智能体系统。系统整合了169艘舰船的完整数据库、详细的战斗机制
资料库，并通过 DeepSeek 大模型提供 AI 驱动的战术分析。

核心功能
--------

* **AI战术顾问** — 基于RAG技术的智能问答，回答关于舰船搭配、战斗策略、
  武器选择等战术问题
* **战斗模拟器** — 可视化编队搭建，AI分析对阵胜负，提供战术建议
* **舰船百科全书** — 169艘舰船完整数据，按类型/阵营/武器分类检索
* **舰队优化器** — 基于数学优化模型的舰队组合推荐引擎
* **向量检索** — FAISS + TF-IDF + jieba双语言混合检索策略

系统架构
========

后端技术栈
----------

- **Web框架**: FastAPI 0.110+ (Python 3.12)
- **数据库**: SQLite via SQLAlchemy 2.0 + aiosqlite (5张核心表)
- **向量检索**: FAISS + TF-IDF + jieba 分词 + rank-bm25
- **AI模型**: DeepSeek Chat API (via OpenAI compatible SDK)
- **认证**: JWT + bcrypt (cost=12)
- **异步任务**: Celery + Redis
- **监控**: Prometheus + Grafana + Jaeger

核心模块
--------

.. code-block:: text

    main.py                  # FastAPI 主入口，路由注册
    config.py                # Pydantic Settings 配置管理
    database.py              # SQLAlchemy 异步数据库层
    battle_engine.py         # 战斗模拟核心引擎
    fleet_optimizer.py       # 舰队组合优化推荐
    rag_service.py           # RAG 向量检索与重排序
    chat_service.py          # AI 对话服务（RAG增强）
    game_knowledge.py        # 游戏领域知识增强注入
    auth_service.py          # JWT认证与权限管理
    admin_routes.py          # 管理员接口（充值/备份/日志）
    api_routes.py            # 公共API路由
    parse_ships.js           # Node.js 舰船数据解析（169艘）
    export_ships.py          # 舰船数据导出工具

数据表结构
==========

==== ================ ========================================== ============
表名                  用途                                      数据保留
==== ================ ========================================== ============
users                 用户账号 + 平台Token余额                   永久保存
session_login         登录会话日志                               7天自动清理
chat_record           AI对话记录（含RAG上下文）                   14天自动清理
recharge_log          管理员充值对账日志                         永久保存
simulator_save        模拟器编队存档（绑定用户）                   永久保存
==== ================ ========================================== ============

战斗引擎公式
============

能量伤害公式
------------

::

    能量伤害 = 基础伤害 x (1 + 伤害加成% - 目标护盾%) x 调校系数 x 策略系数 x 暴击倍率

实弹/动能伤害公式
----------------

::

    实弹伤害 = max(基础伤害 x (1 + 伤害加成) - 目标装甲, 基础伤害 x 10%) x 调校系数 x 射击精度

拦截机制公式
------------

::

    拦截率 = 1 - (1-自身拦截率) x Π(1-同排拦截率_i) x Π(1-全局拦截率_j)

其中自身拦截率、同排舰船拦截率和全局拦截率的计算均遵循概率独立性原则。
拦截系统每个子目标可被多艘拦截舰船重复拦截，实际拦截率取各层拦截的联合概率。

命中率公式
----------

::

    命中率 = min(基础命中率 x (1 + 命中加成 - 目标闪避), 95%) x 武器类型系数

舰队总战斗力评估
----------------

::

    DPM = Σ(单舰DPM_i x 存活概率_i(t))
    舰队战力 = DPM x min(持续时间, 弹药续航) x 阵型系数

API 端点
========

==== ==== ======================= ===================================
方法 路径                      功能说明
==== ==== ======================= ===================================
POST /api/register              用户注册（赠10000 Token）
POST /api/login                 用户登录（JWT 7天有效期）
GET  /api/user/me               获取当前用户信息及Token余额
POST /api/chat                  AI战术对话（RAG增强+Token扣减）
GET  /api/ships                 查询舰船数据库（169艘，支持筛选）
GET  /api/ships/{ship_id}       单舰详细数据
POST /api/simulator/save        保存模拟器编队配置
GET  /api/simulator/saves       获取用户所有编队存档
POST /api/simulator/analyze     两支舰队AI战术对阵分析
POST /api/admin/recharge        管理员充值（仅127.0.0.1）
GET  /api/admin/logs            充值对账日志查询
POST /api/admin/backup          数据库备份
POST /api/rebuild-index         重建FAISS向量索引
GET  /health                    服务健康检查
GET  /metrics                   Prometheus监控指标
==== ==== ======================= ===================================

安装部署
========

环境要求
--------

- Python 3.10 ~ 3.12
- Node.js 18+ (用于解析舰船数据)
- Redis 7+ (可选，用于缓存和Celery)
- 至少 2GB 可用磁盘空间 (向量索引和数据库)

快速开始 (Docker)
-----------------

::

    git clone https://github.com/lagrange-ai/tactical-center.git
    cd tactical-center
    cp .env.template .env
    # 编辑 .env 填入 DeepSeek API Key
    docker compose up -d
    # 访问 http://localhost:3000

手动安装
--------

::

    # 1. 创建虚拟环境
    python3.12 -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate

    # 2. 安装依赖
    pip install -r requirements.txt

    # 3. 配置环境变量
    cp .env.template .env
    # 编辑 .env 填入你的配置

    # 4. 解析舰船数据库
    node parse_ships.js lagrange_docs/lglrmax.html lagrange_docs/ship_database.json

    # 5. 构建向量索引
    python -c "from rag_service import build_vector_index; build_vector_index()"

    # 6. 启动服务
    python main.py

    # 7. 访问 http://127.0.0.1:3000

开发安装
--------

::

    pip install -e ".[dev]"
    pre-commit install
    lagrange-server  # 启动开发服务器

生产部署 (Kubernetes)
---------------------

::

    kubectl create namespace lagrange
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secret.yaml
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml
    kubectl apply -f k8s/ingress.yaml

环境变量
========

======================== ================================== ============
变量名                   说明                               默认值
======================== ================================== ============
DEEPSEEK_API_KEY         DeepSeek API密钥                    (必填)
DEEPSEEK_BASE_URL        DeepSeek API地址                   api.deepseek.com
DEEPSEEK_CHAT_MODEL      使用的模型名称                     deepseek-chat
ADMIN_PASSWORD           管理员密码                          (必填)
JWT_SECRET               JWT签名密钥                         (必填)
DATABASE_PATH            SQLite数据库路径                    lagrange.db
CHROMA_DB_PATH           向量数据库路径                      chroma_db
HOST                     服务监听地址                        127.0.0.1
PORT                     服务监听端口                        3000
RATE_LIMIT_MAX           每用户小时请求限制                  10
CHUNK_SIZE               文本分块大小                        500
RETRIEVAL_TOP_K          RAG检索返回数量                     5
DEFAULT_NEW_USER_TOKENS  新用户赠送Token数                   10000
======================== ================================== ============

战斗模拟器使用
==============

1. 访问首页，进入"战斗模拟器"页面
2. 从左侧169艘舰船中选择，拖拽到编队中
3. 配置每艘舰船的数量（0-999）
4. 可选：设置敌方舰队
5. 点击"AI战术分析"按钮
6. 系统将调用战斗引擎计算对阵结果，AI生成战术建议

许可证
======

本项目以 MIT 许可证发布。本项目仅供玩家社区学习交流使用，
与网易及游戏官方无关。

.. footer:: © 无尽的拉格朗日 AI战术推演中心 — v2.0.0
