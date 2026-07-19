# -*- coding: utf-8 -*-
"""
用户端 API 路由模块
------------------
提供面向普通用户的全部 API 端点：
- 注册 / 登录
- 用户信息查询
- AI 对话（含 RAG 检索 + Token 计费）
- 模拟器编队存档（CRUD）
- 模拟器 AI 战术分析
- 向量库重建接口
"""

from fastapi import APIRouter, HTTPException, Depends, Request

from models import (
    RegisterRequest, LoginRequest, ChatRequest,
    TokenResponse, UserInfoResponse, ChatResponse,
    SimulatorSaveRequest, SimulatorSaveResponse,
    SimulatorAnalyzeRequest, SimulatorAnalyzeResponse,
    MessageResponse,
)
from auth import register_user, login_user, get_user_by_id
from middleware import get_current_user
from chat_service import chat_with_deepseek, chat_simulator_analysis
from billing_service import deduct_tokens, get_user_tokens
from simulator_service import (
    save_fleet_config, get_user_saves, delete_save, get_save_by_id
)
from rag_service import build_vector_index, is_index_built
from database import get_sync_connection
from doc_loader import get_lagrange_docs_path, load_text_file
from pathlib import Path
import re
import json as json_mod

# ==================== 创建路由 ====================
router = APIRouter(prefix="/api", tags=["用户接口"])


# ==================== 认证接口 ====================

@router.post("/register", response_model=TokenResponse)
async def api_register(req: RegisterRequest):
    """
    用户注册接口
    
    - 用户名 2-32 字符，密码 4-64 字符
    - 仅需用户名+密码，不采集手机号/邮箱等隐私信息
    - 新用户自动赠送 10000 免费试用平台Token
    - 注册成功后自动签发 JWT 并返回
    """
    success, message, user_data = register_user(req.username, req.password)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # 注册成功后自动登录
    success2, msg2, login_data = login_user(req.username, req.password)
    if not success2:
        raise HTTPException(status_code=500, detail="注册成功但自动登录失败，请手动登录")
    
    return TokenResponse(**login_data)


@router.post("/login", response_model=TokenResponse)
async def api_login(req: LoginRequest):
    """
    用户登录接口
    
    - 验证用户名密码
    - 签发 JWT，有效期 7 天
    - 返回用户Token余额
    """
    success, message, login_data = login_user(req.username, req.password)
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    return TokenResponse(**login_data)


# ==================== 用户信息接口 ====================

@router.get("/user/me", response_model=UserInfoResponse)
async def api_get_user_info(payload: dict = Depends(get_current_user)):
    """
    获取当前登录用户信息
    
    - 返回用户基本信息和平台Token余额
    - 需要有效的 JWT 凭证
    """
    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return UserInfoResponse(**user)


# ==================== AI 对话接口 ====================

@router.post("/chat", response_model=ChatResponse)
async def api_chat(
    req: ChatRequest,
    request: Request,
    payload: dict = Depends(get_current_user)
):
    """
    AI 对话接口（含 RAG 增强检索）
    
    - 用户提问自动匹配 lagrange_docs 内相关资料
    - 基于 DeepSeek 大模型生成回复
    - 自动扣减用户平台Token
    - 需登录后使用
    """
    user_id = int(payload["sub"])
    
    # 检查向量库是否已构建
    if not is_index_built():
        raise HTTPException(
            status_code=503,
            detail="知识库向量索引尚未构建，请先重建索引或等待自动构建完成"
        )
    
    try:
        # 调用 DeepSeek + RAG
        result = await chat_with_deepseek(
            user_message=req.message,
            history=req.history,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 服务调用失败：{str(e)}")
    
    # 扣减 Token
    success, msg, remaining = deduct_tokens(
        user_id,
        result["prompt_tokens"],
        result["completion_tokens"],
        result["total_tokens"],
    )
    
    if not success:
        raise HTTPException(status_code=402, detail=msg)
    
    # 保存对话记录到数据库
    _save_chat_record(
        user_id, req.message, result["answer"],
        result["source_docs"],
        result["prompt_tokens"], result["completion_tokens"],
        result["total_tokens"]
    )
    
    return ChatResponse(
        answer=result["answer"],
        source_docs=result["source_docs"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["total_tokens"],
        platform_tokens_remaining=remaining,
    )


@router.get("/chat/history")
async def api_chat_history(
    payload: dict = Depends(get_current_user),
    limit: int = 50
):
    """
    获取用户服务端对话历史（最近N条）
    注意：前端 localStorage 有完整历史，此接口作为备份/跨设备同步
    """
    user_id = int(payload["sub"])
    conn = get_sync_connection()
    rows = conn.execute(
        """SELECT question, answer, source_docs, total_tokens, created_at
           FROM chat_record
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            "question": row["question"],
            "answer": row["answer"],
            "source_docs": row["source_docs"],
            "total_tokens": row["total_tokens"],
            "created_at": row["created_at"],
        })
    
    return {"history": history, "count": len(history)}


# ==================== 模拟器存档接口 ====================

@router.post("/simulator/save", response_model=SimulatorSaveResponse)
async def api_save_fleet(
    req: SimulatorSaveRequest,
    payload: dict = Depends(get_current_user)
):
    """
    保存模拟器编队配置
    
    - 编队数据绑定当前登录用户账号
    - 存入 SQLite 数据库，跨设备登录可读取
    - 未登录用户无法保存
    """
    user_id = int(payload["sub"])
    
    success, message, saved_data = save_fleet_config(
        user_id, req.save_name, req.fleet_config
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return SimulatorSaveResponse(**saved_data)


@router.get("/simulator/saves")
async def api_list_saves(payload: dict = Depends(get_current_user)):
    """
    获取当前用户所有模拟器编队存档
    
    - 按更新时间倒序排列
    - 换设备重新登录后可读取全部存档
    """
    user_id = int(payload["sub"])
    saves = get_user_saves(user_id)
    
    return {"saves": saves, "count": len(saves)}


@router.delete("/simulator/save/{save_id}")
async def api_delete_save(
    save_id: int,
    payload: dict = Depends(get_current_user)
):
    """
    删除指定模拟器编队存档
    
    - 仅允许删除自己的存档
    - 权限校验：验证存档归属
    """
    user_id = int(payload["sub"])
    success, message = delete_save(user_id, save_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return MessageResponse(success=True, message=message)


# ==================== 模拟器 AI 分析接口 ====================

@router.post("/simulator/analyze", response_model=SimulatorAnalyzeResponse)
async def api_simulator_analyze(
    req: SimulatorAnalyzeRequest,
    payload: dict = Depends(get_current_user)
):
    """
    模拟器 AI 战术分析
    
    - 将舰队配置发送给 DeepSeek 进行战术分析
    - 结合 RAG 知识库提供专业推演建议
    - 与 AI 对话共用 Token 计费规则
    - 需登录后使用
    """
    user_id = int(payload["sub"])
    
    try:
        result = await chat_simulator_analysis(
            fleet_config=req.fleet_config,
            battle_mode=req.battle_mode,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 分析调用失败：{str(e)}")
    
    # 扣减 Token
    success, msg, remaining = deduct_tokens(
        user_id,
        result["prompt_tokens"],
        result["completion_tokens"],
        result["total_tokens"],
    )
    
    if not success:
        raise HTTPException(status_code=402, detail=msg)
    
    return SimulatorAnalyzeResponse(
        analysis=result["answer"],
        source_docs=result["source_docs"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["total_tokens"],
        platform_tokens_remaining=remaining,
    )


# ==================== 舰队推荐接口 ====================

@router.post("/fleet/recommend")
async def api_fleet_recommend(payload: dict = Depends(get_current_user)):
    """
    AI舰队推荐 — 基于169艘舰船数据库自动生成编队搭配
    
    使用 fleet_optimizer 模块的评分算法：
    - 前排坦克评分（生存+防空+装甲效率）
    - 中后排输出评分（对舰+攻城+指挥值效率）
    - 支援评分（战略+生存）
    - 指挥值上限500约束
    """
    user_id = int(payload["sub"])
    try:
        from fleet_optimizer import recommend_fleet
        result = recommend_fleet(max_cv=500)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐生成失败：{str(e)}")


# ==================== 向量库管理接口 ====================

@router.post("/rebuild-index")
async def api_rebuild_index():
    """
    一键重建 ChromaDB 向量索引
    
    - 修改/新增/删除 lagrange_docs 内文档后调用
    - 不需要登录即可调用（方便管理）
    """
    try:
        result = build_vector_index()
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"向量库重建失败：{str(e)}")


@router.get("/index-status")
async def api_index_status():
    """查询向量索引状态"""
    return {
        "is_built": is_index_built(),
    }


# ==================== 舰船数据库接口 ====================

# 舰船数据库缓存
_ship_db_cache = None
_ship_db_cache_time = 0

@router.get("/ships")
async def api_get_ship_database():
    """
    获取完整的舰船数据库（169艘舰船）
    
    优先读取预解析的 ship_database.json（由 parse_ships.js 生成），
    若不存在则尝试从 HTML 实时解析，最后降级到内置精简数据库。
    """
    global _ship_db_cache, _ship_db_cache_time
    
    import time as _time
    docs_path = get_lagrange_docs_path()
    
    # 1. 优先加载预解析的 JSON 数据库
    json_path = docs_path / "ship_database.json"
    if json_path.exists():
        try:
            # 缓存1分钟
            now = _time.time()
            if _ship_db_cache and (now - _ship_db_cache_time) < 60:
                return _ship_db_cache
            
            with open(json_path, "r", encoding="utf-8") as f:
                ships = json_mod.load(f)
            
            _ship_db_cache = {"ships": ships, "count": len(ships), "source": "ship_database.json (预解析完整数据库)"}
            _ship_db_cache_time = now
            print(f"[舰船数据] 从 JSON 加载 {len(ships)} 艘舰船")
            return _ship_db_cache
        except Exception as e:
            print(f"[舰船数据] JSON 加载失败: {e}")
    
    # 2. 降级：尝试从 HTML 文件实时解析（不推荐，因 JS→JSON 转换不可靠）
    for html_file in docs_path.glob("*.html"):
        try:
            content = load_text_file(html_file)
            # 查找 SHIP_DATABASE 对象
            match = re.search(r'const\s+SHIP_DATABASE\s*=\s*\{', content)
            if match:
                # 复杂对象解析不可靠，提示用户运行 parse_ships.js
                print(f"[舰船数据] 检测到 {html_file.name} 中的 SHIP_DATABASE，但建议运行 parse_ships.js 预解析")
                break
        except Exception:
            pass
    
    # 3. 最终降级：返回内置精简数据库
    print("[舰船数据] 使用内置精简数据库 (20艘)")
    builtin = _get_builtin_ships()
    return {"ships": builtin, "count": len(builtin), "source": "内置精简数据库（建议运行 parse_ships.js 获取完整169艘数据）"}


def _get_builtin_ships():
    """内置精简舰船数据库 — 完整169艘已移至 ship_database.json"""
    # 如果 JSON 可加载则使用完整数据
    json_path = Path(config.LAGRANGE_DOCS_PATH) / "ship_database.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json_mod.load(f)
        except Exception:
            pass
    
    # 否则返回核心降级数据
    return [
        # ========== 战列巡洋舰（超主力） ==========
        {"id":"bc_eternal_storm","name":"永恒风暴级","variant":"","type":"battlecruiser","size":"large","position":"front","hp":320000,"physicalArmor":120,"energyArmor":15,"commandValue":40,"serviceLimit":3,"speed":{"cruise":400,"warp":2400},"ratings":{"antiShip":"S","antiAir":"B","siege":"A","survival":"A","strategy":"S"}},
        {"id":"bc_plutus","name":"普卢托斯之盾级","variant":"","type":"battlecruiser","size":"large","position":"front","hp":350000,"physicalArmor":150,"energyArmor":20,"commandValue":42,"serviceLimit":3,"speed":{"cruise":380,"warp":2300},"ratings":{"antiShip":"A","antiAir":"C","siege":"A","survival":"S","strategy":"S"}},
        # ========== 战列舰（超主力） ==========
        {"id":"bb_constantine","name":"君士坦丁大帝级","variant":"M1","type":"battleship","size":"large","position":"mid","hp":280000,"physicalArmor":100,"energyArmor":18,"commandValue":38,"serviceLimit":2,"speed":{"cruise":350,"warp":2200},"ratings":{"antiShip":"S","antiAir":"D","siege":"S","survival":"A","strategy":"A"}},
        {"id":"bb_st59","name":"ST59级","variant":"电磁","type":"battleship","size":"large","position":"mid","hp":260000,"physicalArmor":90,"energyArmor":25,"commandValue":36,"serviceLimit":2,"speed":{"cruise":370,"warp":2250},"ratings":{"antiShip":"A","antiAir":"D","siege":"S","survival":"A","strategy":"B"}},
        # ========== 航空母舰 ==========
        {"id":"cv_cv3000","name":"CV3000级","variant":"","type":"aircraftcarrier","size":"large","position":"back","hp":240000,"physicalArmor":80,"energyArmor":12,"commandValue":35,"serviceLimit":1,"speed":{"cruise":320,"warp":2100},"ratings":{"antiShip":"C","antiAir":"S","siege":"C","survival":"B","strategy":"S"},"isCarrier":True,"aircraftSlots":{"fighter":8,"corvette":4}},
        # ========== 巡洋舰 ==========
        {"id":"cr_light_chaser","name":"光追级","variant":"","type":"cruiser","size":"small","position":"mid","hp":85000,"physicalArmor":45,"energyArmor":10,"commandValue":18,"serviceLimit":5,"speed":{"cruise":650,"warp":4200},"ratings":{"antiShip":"A","antiAir":"A","siege":"C","survival":"B","strategy":"B"}},
        {"id":"cr_callisto","name":"卡利斯托级","variant":"","type":"cruiser","size":"small","position":"mid","hp":78000,"physicalArmor":40,"energyArmor":8,"commandValue":16,"serviceLimit":5,"speed":{"cruise":680,"warp":4400},"ratings":{"antiShip":"A","antiAir":"C","siege":"B","survival":"B","strategy":"A"}},
        {"id":"cr_aion","name":"爱奥级","variant":"","type":"cruiser","size":"small","position":"front","hp":95000,"physicalArmor":55,"energyArmor":6,"commandValue":20,"serviceLimit":4,"speed":{"cruise":580,"warp":3800},"ratings":{"antiShip":"B","antiAir":"C","siege":"B","survival":"A","strategy":"B"}},
        # ========== 驱逐舰 ==========
        {"id":"dd_ionstorm","name":"阋神星重炮级","variant":"","type":"destroyer","size":"small","position":"mid","hp":28000,"physicalArmor":18,"energyArmor":5,"commandValue":8,"serviceLimit":10,"speed":{"cruise":850,"warp":5500},"ratings":{"antiShip":"A","antiAir":"D","siege":"D","survival":"C","strategy":"B"}},
        {"id":"dd_lancer","name":"枪骑兵级","variant":"","type":"destroyer","size":"small","position":"mid","hp":25000,"physicalArmor":15,"energyArmor":5,"commandValue":7,"serviceLimit":10,"speed":{"cruise":880,"warp":5700},"ratings":{"antiShip":"B","antiAir":"S","siege":"D","survival":"C","strategy":"A"}},
        # ========== 护卫舰 ==========
        {"id":"ff_carillion","name":"卡利莱恩级","variant":"","type":"frigate","size":"small","position":"front","hp":12000,"physicalArmor":12,"energyArmor":3,"commandValue":4,"serviceLimit":15,"speed":{"cruise":1000,"warp":6500},"ratings":{"antiShip":"C","antiAir":"B","siege":"D","survival":"B","strategy":"B"}},
        {"id":"ff_relia","name":"雷利亚特隐身级","variant":"","type":"frigate","size":"small","position":"mid","hp":10000,"physicalArmor":8,"energyArmor":4,"commandValue":4,"serviceLimit":15,"speed":{"cruise":1050,"warp":6800},"ratings":{"antiShip":"A","antiAir":"D","siege":"D","survival":"C","strategy":"S"}},
        {"id":"ff_chenghai","name":"澄海级","variant":"","type":"frigate","size":"small","position":"front","hp":14000,"physicalArmor":15,"energyArmor":2,"commandValue":5,"serviceLimit":12,"speed":{"cruise":900,"warp":6000},"ratings":{"antiShip":"C","antiAir":"C","siege":"D","survival":"A","strategy":"C"}},
        {"id":"ff_cishuimu","name":"刺水母级","variant":"","type":"frigate","size":"small","position":"back","hp":8000,"physicalArmor":6,"energyArmor":8,"commandValue":5,"serviceLimit":12,"speed":{"cruise":950,"warp":6200},"ratings":{"antiShip":"B","antiAir":"S","siege":"D","survival":"D","strategy":"A"}},
        # ========== 战机 ==========
        {"id":"ac_mistral","name":"米斯特拉","variant":"","type":"fighter","size":"aircraft","position":"air","hp":2500,"physicalArmor":2,"energyArmor":1,"commandValue":2,"serviceLimit":0,"speed":{"cruise":3000,"warp":0},"ratings":{"antiShip":"A","antiAir":"S","siege":"D","survival":"C","strategy":"A"},"aircraftType":"fighter","squadronSize":3},
        {"id":"ac_vitas_b","name":"维塔斯B","variant":"","type":"fighter","size":"aircraft","position":"air","hp":2200,"physicalArmor":2,"energyArmor":1,"commandValue":2,"serviceLimit":0,"speed":{"cruise":3200,"warp":0},"ratings":{"antiShip":"S","antiAir":"C","siege":"D","survival":"C","strategy":"B"},"aircraftType":"fighter","squadronSize":3},
        {"id":"ac_hive","name":"蜂巢","variant":"","type":"fighter","size":"aircraft","position":"air","hp":2800,"physicalArmor":3,"energyArmor":1,"commandValue":2,"serviceLimit":0,"speed":{"cruise":2800,"warp":0},"ratings":{"antiShip":"A","antiAir":"A","siege":"B","survival":"B","strategy":"A"},"aircraftType":"fighter","squadronSize":4},
        # ========== 护航艇 ==========
        {"id":"ac_cvt800","name":"CVT800脉冲炮艇","variant":"","type":"corvette","size":"aircraft","position":"air","hp":3500,"physicalArmor":4,"energyArmor":2,"commandValue":2,"serviceLimit":0,"speed":{"cruise":2500,"warp":0},"ratings":{"antiShip":"B","antiAir":"A","siege":"D","survival":"B","strategy":"B"},"aircraftType":"corvette","squadronSize":4},
        {"id":"ac_stingray","name":"鳐鱼级","variant":"","type":"corvette","size":"aircraft","position":"air","hp":3000,"physicalArmor":3,"energyArmor":2,"commandValue":2,"serviceLimit":0,"speed":{"cruise":2700,"warp":0},"ratings":{"antiShip":"S","antiAir":"D","siege":"B","survival":"B","strategy":"B"},"aircraftType":"corvette","squadronSize":3},
        {"id":"ac_br050","name":"BR050","variant":"","type":"corvette","size":"aircraft","position":"air","hp":3200,"physicalArmor":3,"energyArmor":2,"commandValue":2,"serviceLimit":0,"speed":{"cruise":2600,"warp":0},"ratings":{"antiShip":"A","antiAir":"B","siege":"D","survival":"B","strategy":"A"},"aircraftType":"corvette","squadronSize":4},
    ]


# ==================== 辅助函数 ====================

def _save_chat_record(
    user_id: int,
    question: str,
    answer: str,
    source_docs: list,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
):
    """保存对话记录到 chat_record 表"""
    import json
    try:
        conn = get_sync_connection()
        conn.execute(
            """INSERT INTO chat_record 
               (user_id, question, answer, source_docs, prompt_tokens, completion_tokens, total_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, question, answer,
                json.dumps(source_docs, ensure_ascii=False),
                prompt_tokens, completion_tokens, total_tokens
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[记录] 保存对话记录失败：{e}")
