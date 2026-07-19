# 🚀 无尽的拉格朗日 · AI战术推演中心

> 基于RAG增强检索的专业战斗推演智能体 | 169艘舰船 | 局域网部署

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Ships](https://img.shields.io/badge/舰船数据-169艘-orange)](lagrange_docs/ship_database.json)

## ✨ 特性

- 🧠 **AI战术分析** — DeepSeek大模型 + RAG向量检索 + 游戏机制知识增强
- ⚔ **战斗模拟器** — 真实游戏公式(装甲/护盾/暴击/拦截/系统破坏)
- 📚 **169艘舰船图鉴** — 完整HP/装甲/武器模块/评级(S-D)数据
- 💾 **云端存档** — SQLite绑定账号，跨设备登录同步
- 🔧 **管理员后台** — Token充值 + 对账日志 + 数据库备份
- 🌐 **局域网部署** — 纯本地运行，手机/其他电脑同WiFi可访问

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置密钥
copy .env.template .env
# 编辑 .env 填入 DeepSeek API Key

# 3. 解析舰船数据库
node parse_ships.js

# 4. 启动服务
python main.py

# 5. 浏览器访问
# 本机: http://127.0.0.1:3000
# 局域网: http://<你的内网IP>:3000
```

## 📁 项目结构

```
├── main.py              # FastAPI 主入口
├── battle_engine.py     # 战斗模拟引擎(游戏公式)
├── fleet_optimizer.py   # AI舰队推荐
├── rag_service.py       # FAISS向量检索
├── chat_service.py      # DeepSeek对话
├── game_knowledge.py    # 游戏知识增强
├── static/              # 前端SPA
│   ├── index.html       # 主页面(v3)
│   ├── theme.css        # 独立主题
│   ├── compare_ships.html # 舰船对比工具
│   └── service_worker.js  # PWA离线
├── serene/              # 星港指挥中心(品牌站)
├── lagrange_docs/       # 知识库文档
├── deploy/              # 部署教程+脚本
└── exports/             # CSV/TSV数据导出
```

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 · FastAPI · SQLite |
| AI | DeepSeek API · FAISS · TF-IDF · jieba |
| 前端 | Vanilla JS · CSS3 · Service Worker |
| 工具 | Node.js · PowerShell · Batch · Shell |

## 📖 多语言源码

项目包含 **30+ 编程语言** 的舰船数据模型/工具实现：

`Python` `JavaScript` `TypeScript` `Go` `C` `C++` `Rust` `Java` `Kotlin` `Ruby` `Perl` `Lua` `R` `Dart` `Swift` `C#` `Objective-C` `Scala` `Erlang` `Elixir` `Haskell` `Julia` `Pascal` `Fortran` `PHP` `SQL` `GraphQL` `Protobuf` `JSX` `TSX` `Vue` `Svelte`

## ⚠ 免责声明

本工具为玩家社区自制分析工具，与网易及《无尽的拉格朗日》官方无关。AI分析结论仅供参考。

## 📄 许可证

MIT License — 仅供学习交流使用
