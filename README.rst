================================================================================
拉格朗日AI 战术推演中心 — reStructuredText 文档
================================================================================

.. title:: 无尽的拉格朗日 AI战术推演中心
.. author:: 玩家社区
.. date:: 2026-07-20
.. version:: 2.0.0

概述
====

《无尽的拉格朗日》AI战术推演中心是一个基于 RAG（检索增强生成）技术的
专业战斗推演智能体系统。系统整合了169艘舰船的完整数据库、详细的战斗机制
资料库，并通过 DeepSeek 大模型提供 AI 驱动的战术分析。

系统架构
========

后端技术栈
----------

- **Web框架**: FastAPI (Python 3.12)
- **数据库**: SQLite (5张核心表)
- **向量检索**: FAISS + TF-IDF + jieba 分词
- **AI模型**: DeepSeek Chat API
- **认证**: JWT + bcrypt

核心模块
--------

.. code-block:: python

    main.py                  # FastAPI 主入口
    config.py                # 配置管理
    database.py              # 数据库层
    battle_engine.py         # 战斗模拟引擎
    fleet_optimizer.py       # 舰队优化推荐
    rag_service.py           # RAG 向量检索
    chat_service.py          # AI 对话服务
    game_knowledge.py        # 游戏知识增强

数据表结构
==========

==== ================ ==========================================
表名                  用途
==== ================ ==========================================
users                 用户账号 + 平台Token余额（永久保存）
session_login         登录会话日志（7天自动清理）
chat_record           AI对话记录（14天自动清理）
recharge_log          管理员充值对账（永久保存）
simulator_save        模拟器编队存档（绑定用户永久保存）
==== ================ ==========================================

战斗公式
========

能量伤害
--------

::

    能量伤害 = 基础伤害 × (1 + 伤害加成% - 目标护盾%) × 调校系数 × 策略系数

实弹伤害
--------

::

    实弹伤害 = max(基础伤害 × (1 + 伤害加成) - 目标装甲, 基础伤害 × 10%) × 调校系数

拦截公式
--------

::

    拦截率 = 1 - (1-自身率) × Π(1-同排率) × Π(1-全局率)

API 端点
========

==== ==== =================== ============================
方法 路径                    功能
==== ==== =================== ============================
POST /api/register            用户注册（赠10000 Token）
POST /api/login               用户登录（JWT 7天有效）
GET  /api/user/me             获取用户信息
POST /api/chat                AI对话（RAG增强+Token扣减）
GET  /api/ships               获取169艘舰船数据库
POST /api/simulator/save      保存模拟器编队
GET  /api/simulator/saves     获取编队存档列表
POST /api/simulator/analyze   AI战术分析
POST /api/admin/recharge      管理员充值（127.0.0.1）
GET  /api/admin/logs          充值对账日志
POST /api/admin/backup        数据库备份
POST /api/rebuild-index       重建向量索引
==== ==== =================== ============================

部署指南
========

1. 安装 Python 3.12
2. 运行 ``pip install -r requirements.txt``
3. 配置 ``.env`` 文件
4. 解析舰船数据: ``node parse_ships.js``
5. 启动服务: ``python main.py``
6. 访问 http://127.0.0.1:3000

许可证
======

本项目仅供玩家社区学习交流使用，与网易及游戏官方无关。

.. footer:: © 无尽的拉格朗日 AI战术推演中心 — 局域网版本
