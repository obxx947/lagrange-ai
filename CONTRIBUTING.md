# 贡献指南

感谢你对拉格朗日智能体的兴趣！本文档帮助你了解如何参与贡献。

## 行为准则

请遵循 [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) 行为准则。

## 如何贡献

### 报告Bug
1. 搜索 [Issues](https://github.com/user/lagrange-agent/issues) 确认未重复
2. 使用Bug模板创建新Issue
3. 包含: 环境信息、复现步骤、期望行为、实际行为

### 提交功能请求
1. 搜索Issues确认未重复
2. 描述功能及其价值
3. 如果可能，提供使用场景和设计思路

### 提交代码

1. Fork仓库
2. 创建功能分支: `git checkout -b feature/your-feature`
3. 遵循代码风格:
   - Python: 使用 `ruff format` 和 `ruff check`
   - Rust: 使用 `cargo fmt` 和 `cargo clippy`
   - JavaScript: 使用项目ESLint配置
4. 添加测试: 新功能必须有对应的单元测试
5. 确保所有测试通过: `make test`
6. 提交PR并描述变更

### 开发环境设置

```bash
git clone https://github.com/user/lagrange-agent.git
cd lagrange-agent
make setup-dev
cp .env.template .env
# 编辑.env填入你的DeepSeek API密钥
make run
```

### 项目结构

```
拉格朗日智能体/
├── main.py              # FastAPI入口
├── battle_engine/       # 战斗引擎模块
├── battle_engine_rs/    # Rust加速核心
├── cpp_simcore/         # C/C++模拟引擎
├── battle_formal/       # 形式化验证
├── static/              # 前端SPA
├── serene/              # 品牌站
├── lagrange_docs/       # 知识库
├── scripts/             # 运维脚本
├── tests/               # 测试
└── docs/                # 文档
```

### 测试

```bash
make test        # Python测试
make test-rust   # Rust测试
make test-cov    # 覆盖率报告
```

### 代码审查

所有PR需要至少1位维护者的审查。审查关注:
- 代码质量与可读性
- 测试覆盖
- 性能影响
- 安全性
