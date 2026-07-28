# 更新日志

本文档记录了拉格朗日智能体项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [2.0.0] - 2026-07-27

### 新增 🎉
- **战斗引擎 v2.0**: 完整的舰载机空战系统（独立/往复模式）
- **防空系统**: 反击/区域/主动三种防空模式，含特殊舰船识别
- **系统数值HP**: 从二元状态改为数值HP，支持分层伤害
- **策略技能系统**: 攻击/防御/机动/旗舰/支援 五大类策略技能
- **闪避系统**: per-target命中率 + 轰炸距离修正
- **分伤机制**: 可攻击目标数限制（N/2.5取整）
- **反拦截**: 反拦截系数 × 最终拦截率
- **轰炸模式**: 完整的距离→命中率→飞行时间链
- **Rust高性能核心** (`battle_engine_rs/`): PyO3绑定，蒙特卡洛批量模拟
- **C/C++模拟引擎** (`cpp_simcore/`): 动态库加速
- **形式化验证层** (`battle_formal/`):
  - Haskell: 战斗公式代数规约 + QuickCheck属性测试
  - Agda: 伤害计算正确性证明（能量免疫/实弹保底/非负性）
  - Idris2: 拦截率概率模型验证（单调性/有界性/保序性）
- **CI/CD流水线**: GitHub Actions全链路（校验→测试→构建→部署→回滚）
- **完整SQL Schema**: 8张表+索引+触发器+视图
- **Docker支持**: 多阶段构建+Rust交叉编译
- **部署脚本**: deploy.sh(Unix) + setup.bat(Windows) + start.ps1

### 改进 ⚡
- 舰队推荐引擎从评级字母改为基于DPM的评分
- 战斗回放可视化（Canvas动画+时间轴）
- 舰船数据库新增字段：evasion, strategySkills, flagshipEffects, antiIntercept
- 前端响应式优化

### 文件统计
- 新增文件: 40+
- 新增代码行: 8000+
- 测试用例: 50+

---

## [1.0.0] - 2024-12-01

### 初始发布 🚀
- **AI战术问答**: 基于DeepSeek + RAG（FAISS/TF-IDF）的智能对话
- **战斗模拟器**: 基础舰船对舰船战斗（660行）
- **舰队推荐**: 169艘舰船的评分推荐系统
- **舰船百科**: 可搜索的169艘舰船数据库
- **舰船对比**: 并排参数对比工具
- **云存档**: SQLite + JWT跨设备舰队存档
- **Token经济**: 用户注册/充值/扣费系统
- **管理后台**: 充值管理/审计日志/数据库备份
- **品牌站**: 深空科幻主题着陆页
- **PWA支持**: Service Worker离线缓存

### 技术栈
- 后端: Python 3.12, FastAPI, DeepSeek API
- RAG: FAISS, scikit-learn TF-IDF, jieba
- 数据库: SQLite (aiosqlite), 5张表
- 前端: Vanilla JavaScript SPA
- 认证: JWT + bcrypt
