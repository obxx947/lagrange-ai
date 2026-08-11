# 拉格朗日智能体3：AI 思考/状态 布局修复（思考顶部 + 状态底部固定）

## 目标布局
```
聊天区：
┌──────────────────────────┐
│ 🤔 AI思考（固定顶部面板）   │ ← 新 #thinkPanel
│    当前对话推理实时、自动滚底 │
├──────────────────────────┤
│ 聊天消息流（可滚动）         │
├──────────────────────────┤
│ 🤖 AI状态（固定底部面板）    │ ← 新 #statusPanel
│    检索/工具/质检实时、自动滚底│
├──────────────────────────┤
│ 输入区                     │
└──────────────────────────┘
```

## 改动明细（chat.html，单文件）

### 1. 新增顶部思考面板 `#thinkPanel`
- `.chat-area` 内、`#chatMsgs` 之前，flex-shrink:0；头部"🤔 AI思考 · 当前对话 [展开/收起]" + 内容区 `.tp-body`（max-height:180px，overflow-y:auto）
- `addThinkingLine()` 重写：写入 #thinkPanel 的 .tp-body，**追加后自动 `scrollTop=scrollHeight`**（思考内容一直处于底部=最新可见）；无内容时面板隐藏；点击头部折叠
- **跟随对话**：send() 开始时清空面板（每轮重新累积）；switchConv/newChat 清空面板 + 重置 `window._currentAssistEl=null`（修脏引用）

### 2. 新增底部状态面板 `#statusPanel`
- `.chat-area` 内、`#chatMsgs` 之后、`.input-area` 之前，flex-shrink:0；头部"🤖 运行状态 · 当前对话 [展开/收起]" + 摘要 + 内容区 `.sp-body`（max-height:160px，overflow-y:auto）
- `addStatusLine()` 重写：写入 .sp-body 每行（icon+text），**自动滚动到底部**（修"后面的状态看不见"）
- send() 开始时清空（每轮独立）；切换对话清空；完成时折叠并显示"✅ 已完成"摘要

### 3. 移除旧机制并适配
- 删除旧 runGroup（ensureRunGroup/toggleRunGroup 对旧 DOM 的操作）与消息流内独立 thinking-box 插入逻辑，替换为面板逻辑
- send() 中"移除旧 runGroup + 新建"→"清空两个面板"
- 失败兜底 errMsg 提取（现读 #runGroupBody）→ 改读 #statusPanel
- collapseAllThinking() → 折叠 #statusPanel（保留最终状态）
- resumeChat 同步适配（不重建 runGroup）

### 4. 移动端适配（@media 700px 内）
- 两面板 max-height 收窄（思考 120px / 状态 120px），面板样式适配窄屏

### 5. 验证
- 桌面回归：消息流、提问卡片、计划操作栏、抽屉均正常
- 真实对话：思考实时出现于顶部面板并自动滚底、状态行实时追加于底部面板不被遮挡、切换对话两面板清空、无 JS 错误
- 390×844 竖屏：两面板固定显示、无横向溢出

## 范围
- 仅修改 拉格朗日智能体3/chat.html（原版 static/chat.html 如需要可后续同步）
- 不动：引擎/提示词/知识库/其它文件