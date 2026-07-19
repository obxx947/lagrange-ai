# 《无尽的拉格朗日》AI 战术推演中心 — API 接口文档

> 基础地址：`http://127.0.0.1:3000` 或 `http://<本机内网IP>:3000`
>
> Swagger 交互文档：`http://127.0.0.1:3000/docs`
>
> 所有接口返回 JSON 格式数据。

---

## 目录
1. [认证接口](#1-认证接口)
2. [用户接口](#2-用户接口)
3. [AI对话接口](#3-ai对话接口)
4. [模拟器存档接口](#4-模拟器存档接口)
5. [模拟器AI分析接口](#5-模拟器ai分析接口)
6. [舰船数据库接口](#6-舰船数据库接口)
7. [向量库管理接口](#7-向量库管理接口)
8. [管理员接口](#8-管理员接口)
9. [通用接口](#9-通用接口)
10. [错误码说明](#10-错误码说明)

---

## 1. 认证接口

### 1.1 用户注册
```
POST /api/register
```
**请求体：**
```json
{
  "username": "testuser",
  "password": "mypassword"
}
```
**响应：**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 604800,
  "username": "testuser",
  "platform_tokens": 10000
}
```
**说明：** 新用户自动赠送 10,000 平台Token。注册成功后自动登录返回JWT。

---

### 1.2 用户登录
```
POST /api/login
```
**请求体：**
```json
{
  "username": "testuser",
  "password": "mypassword"
}
```
**响应：**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 604800,
  "username": "testuser",
  "platform_tokens": 9500
}
```
**说明：** JWT 有效期 7 天，过期后需重新登录。

---

## 2. 用户接口

### 2.1 获取当前用户信息
```
GET /api/user/me
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`

**响应：**
```json
{
  "id": 1,
  "username": "testuser",
  "platform_tokens": 9500,
  "deepseek_input_tokens": 1500,
  "deepseek_output_tokens": 800,
  "created_at": "2024-01-15 10:30:00"
}
```

---

## 3. AI对话接口

### 3.1 发送对话
```
POST /api/chat
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`  
**限流：** 单用户每小时最多 10 次

**请求体：**
```json
{
  "message": "光追级和卡利斯托级哪个更强？",
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！请问有什么可以帮你的？"}
  ]
}
```
**响应：**
```json
{
  "answer": "根据资料库分析，光追级在防空能力上...\n【资料来源：战斗机制.txt】...",
  "source_docs": [
    {
      "file_name": "战斗机制.txt",
      "snippet": "光追级拥有全游戏顶尖的防空能力..."
    }
  ],
  "prompt_tokens": 450,
  "completion_tokens": 320,
  "total_tokens": 770,
  "platform_tokens_remaining": 8730
}
```

---

### 3.2 获取对话历史
```
GET /api/chat/history?limit=50
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`

**响应：**
```json
{
  "history": [
    {
      "question": "光追级和卡利斯托级哪个更强？",
      "answer": "...",
      "source_docs": "...",
      "total_tokens": 770,
      "created_at": "2024-01-15 11:00:00"
    }
  ],
  "count": 1
}
```

---

## 4. 模拟器存档接口

### 4.1 保存编队
```
POST /api/simulator/save
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`

**请求体：**
```json
{
  "save_name": "主力编队_v1",
  "fleet_config": {
    "ally-escort": {"main": [{"id":"cr_light_chaser","name":"光追级","count":5}]},
    "ally-escorted": {"main": []},
    "enemy-escort": {"main": []},
    "enemy-escorted": {"main": []},
    "bomb-fleet": {"main": []}
  }
}
```
**响应：**
```json
{
  "id": 1,
  "save_name": "主力编队_v1",
  "fleet_config": { ... },
  "created_at": "2024-01-15 12:00:00",
  "updated_at": "2024-01-15 12:00:00"
}
```

---

### 4.2 获取存档列表
```
GET /api/simulator/saves
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`

**响应：**
```json
{
  "saves": [
    {
      "id": 1,
      "user_id": 1,
      "save_name": "主力编队_v1",
      "fleet_config": { ... },
      "created_at": "2024-01-15 12:00:00",
      "updated_at": "2024-01-15 12:00:00"
    }
  ],
  "count": 1
}
```

---

### 4.3 删除存档
```
DELETE /api/simulator/save/{save_id}
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`

**响应：**
```json
{
  "success": true,
  "message": "存档已删除"
}
```

---

## 5. 模拟器AI分析接口

### 5.1 AI战术分析
```
POST /api/simulator/analyze
```
**请求头：** `Authorization: Bearer <JWT_TOKEN>`  
**限流：** 单用户每小时最多 10 次（与AI对话共用限额）

**请求体：**
```json
{
  "fleet_config": { ... },
  "battle_mode": "escort"
}
```
**响应：**
```json
{
  "analysis": "根据舰队配置分析如下：\n1. 前排坦度充足...",
  "source_docs": [{ "file_name": "战斗机制.txt", "snippet": "..." }],
  "prompt_tokens": 380,
  "completion_tokens": 520,
  "total_tokens": 900,
  "platform_tokens_remaining": 7830
}
```

---

## 6. 舰船数据库接口

### 6.1 获取舰船数据
```
GET /api/ships
```
**无需鉴权**

**响应：**
```json
{
  "ships": [
    {
      "id": "cr_light_chaser",
      "name": "光追级",
      "variant": "",
      "type": "cruiser",
      "size": "small",
      "position": "mid",
      "hp": 85000,
      "physicalArmor": 45,
      "energyArmor": 10,
      "commandValue": 18,
      "serviceLimit": 5,
      "speed": {"cruise": 650, "warp": 4200},
      "ratings": {"antiShip":"A","antiAir":"A","siege":"C","survival":"B","strategy":"B"}
    }
  ],
  "count": 138,
  "source": "lglrmax.html"
}
```

---

## 7. 向量库管理接口

### 7.1 重建向量索引
```
POST /api/rebuild-index
```
**无需鉴权**

**响应：**
```json
{
  "success": true,
  "status": "success",
  "message": "向量索引构建完成，共 2 个文件、45 个文本块",
  "file_count": 2,
  "chunk_count": 45
}
```

---

### 7.2 查询索引状态
```
GET /api/index-status
```
**响应：**
```json
{
  "is_built": true
}
```

---

## 8. 管理员接口

> ⚠ 所有管理员接口**仅限本机 127.0.0.1 访问**，局域网其他设备无法调用。

### 8.1 管理员登录
```
POST /api/admin/login
```
**请求体：**
```json
{
  "password": "admin_lagrange_2024"
}
```
**响应：**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "message": "管理员登录成功"
}
```

---

### 8.2 用户Token充值
```
POST /api/admin/recharge
```
**请求头：** `Authorization: Bearer <ADMIN_JWT>`  
**IP限制：** 仅 127.0.0.1

**请求体：**
```json
{
  "target_username": "testuser",
  "amount": 5000
}
```
**响应：**
```json
{
  "success": true,
  "message": "充值成功：testuser 增加 5000 Token（9500 → 14500）",
  "detail": {
    "target_username": "testuser",
    "amount": 5000,
    "old_balance": 9500,
    "new_balance": 14500
  }
}
```

---

### 8.3 查询充值日志
```
GET /api/admin/logs?limit=50
```
**请求头：** `Authorization: Bearer <ADMIN_JWT>`  
**IP限制：** 仅 127.0.0.1

**响应：**
```json
{
  "logs": [
    {
      "id": 1,
      "admin_id": 1,
      "admin_name": "admin",
      "target_user_id": 2,
      "target_name": "testuser",
      "amount": 5000,
      "created_at": "2024-01-15 12:30:00"
    }
  ],
  "count": 1
}
```

---

### 8.4 备份数据库
```
POST /api/admin/backup
```
**请求头：** `Authorization: Bearer <ADMIN_JWT>`  
**IP限制：** 仅 127.0.0.1

**响应：**
```json
{
  "success": true,
  "message": "数据库备份成功",
  "backup_path": "./db_backup/lagrange_backup_20240115_120000.db"
}
```

---

### 8.5 清理过期数据
```
POST /api/admin/cleanup
```
**请求头：** `Authorization: Bearer <ADMIN_JWT>`  
**IP限制：** 仅 127.0.0.1

**响应：**
```json
{
  "success": true,
  "message": "[清理] 已清理 3 条过期会话、15 条过期聊天记录"
}
```

---

## 9. 通用接口

### 9.1 服务首页
```
GET /
```
返回一体化前端页面（HTML）。

### 9.2 健康检查
```
GET /health
```
**响应：**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T12:00:00",
  "index_built": true
}
```

### 9.3 API 文档（Swagger）
```
GET /docs
```
交互式 Swagger UI 文档页面。

---

## 10. 错误码说明

| HTTP状态码 | 含义 | 说明 |
|-----------|------|------|
| 200 | 成功 | 请求处理成功 |
| 400 | 请求参数错误 | 参数校验失败 |
| 401 | 未授权 | Token无效或已过期，需重新登录 |
| 402 | 余额不足 | 平台Token余额不足以完成本次请求 |
| 403 | 禁止访问 | 管理员接口非本机访问 / 普通用户访问管理功能 |
| 404 | 资源不存在 | 请求的资源（用户/存档等）不存在 |
| 429 | 请求过于频繁 | 超过每小时10次限流阈值 |
| 500 | 服务器内部错误 | 后端异常 |
| 502 | AI服务异常 | DeepSeek API 调用失败 |
| 503 | 服务不可用 | 向量索引未构建 |

### 通用错误响应格式
```json
{
  "detail": "错误描述信息",
  "error_code": "RATE_LIMITED"
}
```

---

## 接口访问示例

### curl 示例

```bash
# 注册
curl -X POST http://127.0.0.1:3000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"player1","password":"pass1234"}'

# 登录（保存返回的 access_token）
curl -X POST http://127.0.0.1:3000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"player1","password":"pass1234"}'

# AI对话（使用上一步获取的token）
curl -X POST http://127.0.0.1:3000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOi..." \
  -d '{"message":"光追级的防空能力如何？","history":[]}'

# 保存模拟器编队
curl -X POST http://127.0.0.1:3000/api/simulator/save \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOi..." \
  -d '{"save_name":"我的编队","fleet_config":{}}'

# 局域网访问（其他设备）
# 将 127.0.0.1 替换为服务器内网IP即可
curl -X GET http://192.168.1.100:3000/health
```

### Python 示例

```python
import requests

BASE = "http://127.0.0.1:3000"

# 登录
resp = requests.post(f"{BASE}/api/login", json={
    "username": "player1", "password": "pass1234"
})
token = resp.json()["access_token"]

# AI对话
headers = {"Authorization": f"Bearer {token}"}
resp = requests.post(f"{BASE}/api/chat", json={
    "message": "分析一下永恒风暴级的强度",
    "history": []
}, headers=headers)

print(resp.json()["answer"])
```
