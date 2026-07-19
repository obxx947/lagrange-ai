# -*- coding: utf-8 -*-
"""
AI 对话服务模块
---------------
封装 DeepSeek API 调用逻辑，包括：
- 系统约束提示词强制拼接
- RAG 检索结果注入
- 多轮对话上下文管理
- Token 用量统计
"""

import json
from typing import List, Optional, AsyncGenerator

import httpx

import config
from rag_service import search_similar_documents, format_rag_context
from game_knowledge import build_enhanced_system_prompt, get_combat_knowledge_text

# ==================== 系统强制约束提示词（增强版） ====================
# 从 game_knowledge 模块动态构建，包含完整游戏机制知识
# 此提示词每一轮 AI 推理都必须完整拼接，代码层面不可删减、忽略、篡改

SYSTEM_PROMPT = build_enhanced_system_prompt()


# ==================== DeepSeek API 调用 ====================

def _build_messages(
    user_message: str,
    rag_context: str,
    history: List[dict] = None
) -> List[dict]:
    """
    构建发送给 DeepSeek 的完整消息列表
    
    结构：
    1. system: 系统约束提示词 + RAG 检索上下文
    2. history: 多轮对话历史（最近N轮）
    3. user: 当前用户消息
    """
    messages = []
    
    # 系统消息：强制约束 + RAG上下文
    system_content = SYSTEM_PROMPT
    if rag_context:
        system_content += f"\n\n【本次检索到的资料库参考内容】\n{rag_context}"
    else:
        system_content += "\n\n【注意】本次未检索到相关资料，若问题超出资料库范围请回复标准拒绝语。"
    
    messages.append({"role": "system", "content": system_content})
    
    # 多轮对话历史（仅保留最近20轮避免超长）
    if history:
        for h in history[-20:]:
            if h.get("role") in ("user", "assistant"):
                messages.append({
                    "role": h["role"],
                    "content": h.get("content", "")
                })
    
    # 当前用户消息
    messages.append({"role": "user", "content": user_message})
    
    return messages


async def chat_with_deepseek(
    user_message: str,
    history: List[dict] = None,
    stream: bool = False
) -> dict:
    """
    调用 DeepSeek API 进行对话
    
    Args:
        user_message: 用户提问
        history: 多轮对话历史
        stream: 是否流式输出
    
    Returns:
        {
            "answer": "AI回复",
            "source_docs": [...],
            "prompt_tokens": 输入Token数,
            "completion_tokens": 输出Token数,
            "total_tokens": 总Token数,
        }
    """
    # 1. RAG 检索相关文档
    source_docs = search_similar_documents(user_message)
    rag_context = format_rag_context(source_docs)
    
    # 2. 构建消息
    messages = _build_messages(user_message, rag_context, history)
    
    # 3. 调用 DeepSeek API
    url = f"{config.DEEPSEEK_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEEPSEEK_CHAT_MODEL,
        "messages": messages,
        "temperature": 0.3,         # 低温度确保输出稳定
        "max_tokens": 2048,
        "stream": stream,
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            error_detail = response.text
            print(f"[DeepSeek] API 调用失败：{response.status_code} - {error_detail}")
            raise Exception(f"AI 服务调用失败（{response.status_code}），请稍后重试")
        
        result = response.json()
    
    # 4. 提取结果
    choice = result["choices"][0]
    answer = choice["message"]["content"]
    
    usage = result.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    
    # 5. 格式化返回资料来源
    formatted_docs = []
    for doc in source_docs:
        formatted_docs.append({
            "file_name": doc["source"],
            "snippet": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
        })
    
    return {
        "answer": answer,
        "source_docs": formatted_docs,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


async def chat_simulator_analysis(
    fleet_config: dict,
    battle_mode: str = "escort"
) -> dict:
    """
    模拟器 AI 战术分析 — 使用 DeepSeek 分析舰队配置
    
    与普通对话共用同一套 Token 计费和 RAG 检索逻辑
    
    Args:
        fleet_config: 舰队配置 JSON
        battle_mode: 战斗模式（escort / bomb）
    
    Returns:
        同 chat_with_deepseek 返回值
    """
    # 构建模拟器分析专用提示
    fleet_summary = _summarize_fleet_config(fleet_config)
    
    analysis_prompt = f"""请分析以下《无尽的拉格朗日》舰队配置（{battle_mode}模式）：

{fleet_summary}

请从以下角度分析：
1. 舰队整体强度评估
2. 前排/后排搭配合理性
3. 舰船之间的协同效果
4. 潜在弱点与改进建议
5. 对该配置的实战预期表现

请严格基于资料库数据进行分析，标注引用来源。"""
    
    # 使用标准对话流程（含RAG检索和Token计费）
    return await chat_with_deepseek(analysis_prompt, history=None)


def _summarize_fleet_config(fleet_config: dict) -> str:
    """将舰队配置JSON转换为可读的文本摘要"""
    lines = []
    
    fleet_names = {
        "ally-escort": "己方护航舰队",
        "ally-escorted": "己方被护航舰队",
        "enemy-escort": "敌方护航舰队",
        "enemy-escorted": "敌方被护航舰队",
        "bomb-fleet": "轰炸机编队",
    }
    
    for fleet_key, fleet_name in fleet_names.items():
        fleet = fleet_config.get(fleet_key, {})
        if not fleet:
            continue
        
        main_ships = fleet.get("main", [])
        if main_ships:
            lines.append(f"\n{fleet_name}（主力）：")
            for ship in main_ships:
                name = ship.get("name", ship.get("id", "未知舰船"))
                count = ship.get("count", 1)
                lines.append(f"  - {name} x{count}")
        
        # 如果有增援舰队也加入
        reinforcement = fleet.get("reinforcement", [])
        if reinforcement:
            lines.append(f"  增援：")
            for ship in reinforcement:
                name = ship.get("name", ship.get("id", "未知舰船"))
                count = ship.get("count", 1)
                lines.append(f"    - {name} x{count}")
    
    return "\n".join(lines) if lines else "空舰队配置"


async def get_embedding(text: str) -> List[float]:
    """
    获取文本的嵌入向量（用于RAG检索备选方案）
    当前使用 ChromaDB 自带的嵌入模型，此函数为扩展预留
    """
    # ChromaDB 内部已处理嵌入，此函数保留用于未来扩展
    return []
