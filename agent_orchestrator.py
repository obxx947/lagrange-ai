# -*- coding: utf-8 -*-
"""
Agent 编排器
------------
主 Agent 循环：接收用户消息 → 调用DeepSeek function calling → 执行工具 → 推理 → 质检 → 输出

支持 SSE 流式输出，前端可实时看到：
- AI 思考过程
- 工具调用状态
- 质检结果
- 最终回答
"""

import json
import time
from typing import AsyncGenerator, Optional

import httpx
import config
from agent_tools import TOOLS, execute_tool
from agent_quality_check import quality_check
from rag_service import search_similar_documents, format_rag_context
from user_config import get_effective_llm_config

SYSTEM_PROMPT = """你是《无尽的拉格朗日》专业AI战术顾问。你必须严格遵守以下规则：

【知识调取优先级】
1. 优先搜索互联网公开权威资料（必须去网上查找相关信息和他人看法）
2. 网络无结果时，调用 search_knowledge_base 工具检索向量知识库
3. 知识库包含：舰船数据、战斗机制文档、真人讲解范例

【推理铁律 — 禁止等级制推理】
- 严禁使用 A/B/C/D/S 等级评价体系进行推理（如"防空S级""输出B级"等）
- 必须基于舰船的具体数值参数（HP、护甲、单发伤害、DPM、锁定时间、冷却时间、拦截概率等）和战斗机制文档中的公式进行定量推演
- 所有结论必须有数值依据，不能仅凭等级标签下判断

【舰队配置强制规则】
- 用户询问舰队配置/配队方案时，必须调用 battle_simulate 工具
- 【先查实例】只要问题与配队/舰队配置有关，不管怎么样，必须先去"实例.txt"（知识库文件）里查看实战配置范例，参考其中的配队思路和人口结构
- 在多环境（护航战、轰炸战、正面对抗）下测试配置
- 完整展示各环境实测数据给用户
- 自主检验方案是否满足用户需求，不满足则迭代修改
- 【输出要求】如果用户的问题与配队/舰队配置有关，请在回答的最后完整复述一遍舰队配置方案（含舰船名、数量、站位、模块）

【人口计算规则】
- 配队时必须检索"舰船人口.txt"（知识库文件），找到方案中每一艘舰船的人口占用值，按那里的数据累加计算舰队总人口
- 如果在"舰船人口.txt"中找不到某艘舰船，必须去"黑话.txt"（知识库文件）查找该舰船的对应信息
- "xxx+x"这种说法：前面的数字是这个舰队的总人口，后面是增援人口，这里说的是舰船数量
- 放在增援编队（reinforcement）里的舰船不占用总人口，放什么船都行
- 惯例：一般把人口占用最高的舰船放在增援编队里

【回答风格】
- 对标知识库内"真人讲解范例"的叙事风格：口语化、分点论证、同类对比
- 拒绝生硬制式文本

【信息溯源】
- 所有舰船参数必须来自 get_ship_data 工具或知识库检索
- 所有战术结论必须基于战斗机制文档
- 无法查阅的资料如实告知用户，严禁编造

【质检规则】
- 回答输出前会经过独立质检智能体验证
- 质检不通过时会收到修改意见，根据意见重新生成
"""


async def agent_chat_stream(
    user_message: str,
    history: list = None,
    user_id: int = 0,
    simulator_state: dict = None,
) -> AsyncGenerator[str, None]:
    """
    Agent 主循环，SSE 流式输出。
    每一步都 yield JSON 事件，前端可以实时渲染。
    """

    # 获取用户配置
    llm_cfg = get_effective_llm_config(user_id)
    api_key = llm_cfg["api_key"]
    api_url = llm_cfg["api_url"].rstrip("/")
    # 自动修正：避免 /v1/v1 双重路径
    if api_url.endswith("/v1"):
        base_url = api_url
    else:
        base_url = api_url + "/v1"
    model = llm_cfg["model"]

    if not api_key:
        yield _sse("error", "请先在设置页面配置大模型API Key（右上角⚙️）")
        return

    # ============ 步骤1：启动子代理并行检索 ============
    yield _sse("sub_agent", "🚀 启动子代理集群...", {"agents": []})
    from agent_sub_agents import SUB_AGENTS, run_sub_agent
    from agent_cache import cached_search, rag_cache, web_search, get_tavily_key

    sub_results = []
    all_rag_docs = []
    for agent in SUB_AGENTS:
        yield _sse("sub_agent", f"{agent['icon']} {agent['name']} 正在检索...", {"agent": agent["name"]})
        try:
            r = run_sub_agent(agent["name"], user_message)
            sub_results.append(r)
            for item in r.get("results", []):
                all_rag_docs.append({
                    "source": item.get("source", "未知"),
                    "content": item.get("content", ""),
                })
            yield _sse("sub_agent", f"{agent['icon']} {agent['name']} 完成（找到 {r.get('result_count', 0)} 条资料）", {"agent": agent["name"], "count": r.get("result_count", 0)})
        except Exception as e:
            yield _sse("sub_agent", f"{agent['icon']} {agent['name']} 异常: {str(e)[:50]}", {"agent": agent["name"], "error": str(e)[:50]})

    # 缓存命中率显示
    cache_stats = rag_cache.hit_rate()
    yield _sse("cache", f"📊 缓存命中率: {cache_stats['hit_rate']}% ({cache_stats['hits']}次命中/{cache_stats['total']}次查询)", cache_stats)

    # ============ 步骤2：RAG检索（带缓存） ============
    yield _sse("status", "🔍 正在检索知识库...")
    docs, cache_hit = cached_search(user_message, top_k=5)
    all_rag_docs.extend([{"source": d.get("source", "未知"), "content": d.get("content", "")} for d in docs])

    # 去重
    seen_sources = set()
    unique_rag = []
    for d in all_rag_docs:
        if d["source"] not in seen_sources:
            seen_sources.add(d["source"])
            unique_rag.append(d)
    all_rag_docs = unique_rag

    rag_context = format_rag_context(docs) if docs else ""
    # 补充子代理检索到的额外资料
    sub_context_parts = []
    for r in sub_results:
        for item in r.get("results", []):
            src = item.get("source", "未知")
            sub_context_parts.append(f"【子代理资料：{src}】\n{item.get('content', '')[:600]}")
    if sub_context_parts:
        rag_context += "\n\n" + "\n\n".join(sub_context_parts[:10])

    # ============ 步骤3：联网搜索（任何情况都执行，无Key自动降级DuckDuckGo） ============
    web_results = []
    yield _sse("web_search", "🌐 正在联网搜索...")
    try:
        tavily_key = get_tavily_key()
        web = web_search(user_message, tavily_key)
        if web.get("results"):
            web_results = web["results"]
            engine = web.get("engine", "unknown")
            yield _sse("web_search", f"🌐 联网搜索完成（{engine} · {len(web_results)} 条结果）", {"count": len(web_results), "engine": engine})
        elif web.get("error"):
            yield _sse("web_search", f"🌐 联网搜索失败: {web['error'][:50]}")
        else:
            yield _sse("web_search", "🌐 联网搜索无结果")
    except Exception as e:
        yield _sse("web_search", f"🌐 联网搜索异常: {str(e)[:50]}")

    # 步骤4：构建消息（清理所有reasoning_content）
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if rag_context:
        messages.append({"role": "system", "content": f"【本次检索到的知识库资料（含子代理汇总）】\n{rag_context[:8000]}"})

    if web_results:
        web_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('content', '')[:300]} ({r.get('url', '')})"
            for r in web_results[:5]
        ])
        messages.append({"role": "system", "content": f"【互联网检索结果】\n{web_text}"})

    # 加入历史（只保留role和content）
    if history:
        for h in history[-20:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)[:2000]})

    # 加入模拟器状态
    if simulator_state:
        messages.append({"role": "system", "content": f"【用户当前模拟器状态】\n{json.dumps(simulator_state, ensure_ascii=False)}"})

    messages.append({"role": "user", "content": user_message})

    # 步骤5：Agent 循环（最多50轮推理+工具调用）
    source_docs = []
    max_iterations = 50
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    }
                )
                if resp.status_code != 200:
                    err = ""
                    try: err = resp.json().get("error",{}).get("message","")[:200]
                    except: err = resp.text[:200] if resp.text else ""
                    yield _sse("error", f"API {resp.status_code}: {err} (请求: {base_url}/chat/completions)")
                    return

                data = resp.json()
                if "choices" not in data or not data["choices"]:
                    yield _sse("error", f"API返回异常: {str(data)[:200]}")
                    return
                choice = data["choices"][0]
                msg = choice.get("message", {})
                # 保留reasoning_content（thinking模型需要原样带回）
                reasoning = msg.get("reasoning_content", None)
                # 推送给前端显示（AI自我思考内容）
                if reasoning:
                    yield _sse("thinking", reasoning[:2000], {"truncated": len(reasoning) > 2000})

                # 检查是否需要调用工具
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        func_name = tc["function"]["name"]
                        func_args = json.loads(tc["function"]["arguments"])
                        yield _sse("tool_start", f"🔧 调用工具: {func_name}", {
                            "tool": func_name,
                            "args": func_args
                        })

                        # 执行工具
                        result = execute_tool(func_name, func_args, user_id)
                        yield _sse("tool_result", result[:2000], {
                            "tool": func_name,
                            "result_preview": result[:300]
                        })

                        # 将工具调用加入消息（保留reasoning_content）
                        clean_tc = {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"]
                            }
                        }
                        assist_msg = {
                            "role": "assistant",
                            "content": msg.get("content"),
                            "tool_calls": [clean_tc]
                        }
                        if reasoning:
                            assist_msg["reasoning_content"] = reasoning
                        messages.append(assist_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result[:4000]
                        })

                    # 继续循环让AI处理工具结果
                    continue

                # 无工具调用 → 得到最终回答
                answer = msg.get("content", "")

                # 步骤4：质检（质检Agent也会读取子代理汇总的资料）
                yield _sse("status", "🔬 正在质检（查阅资料核验）...")
                qc_sources = [{"source": d["source"], "content": d["content"]} for d in all_rag_docs[:10]]
                if web_results:
                    qc_sources.append({"source": "互联网", "content": web_results[0].get("content", "")[:300]})
                qc_result = await quality_check(
                    user_query=user_message,
                    answer=answer,
                    sources=qc_sources if qc_sources else None,
                    api_key=api_key,
                    api_url=api_url,
                    model=model
                )

                if qc_result.get("pass"):
                    yield _sse("qc_pass", "✅ 质检通过")
                    yield _sse("answer", answer, {
                        "sources": [
                            {"file_name": d.get("source", "未知"), "snippet": d.get("content", "")[:200]}
                            for d in (all_rag_docs or [])[:10]
                        ],
                        "iterations": iteration,
                        "qc_feedback": qc_result.get("feedback", ""),
                        "token_usage": {
                            "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                            "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                        }
                    })
                    yield _sse("done", "完成")
                    return
                else:
                    # 质检不通过 → 加入反馈继续循环（保留reasoning_content）
                    yield _sse("qc_fail", f"⚠️ 质检不通过: {qc_result.get('feedback', '')[:200]}")
                    qc_assist = {"role": "assistant", "content": answer}
                    if reasoning: qc_assist["reasoning_content"] = reasoning
                    messages.append(qc_assist)
                    messages.append({"role": "user", "content": f"【质检反馈】你的回答未通过质检，请根据以下意见修改：\n{qc_result.get('feedback', '')}\n\n请重新生成回答。"})
                    continue

        except httpx.TimeoutException:
            yield _sse("error", "API请求超时，请稍后重试")
            return
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # Log full error to server console
            print(f"[Agent Error] {tb}", flush=True)
            yield _sse("error", f"Agent异常: {str(e)[:200]}")
            return

    # 达到最大迭代次数
    yield _sse("error", f"达到最大迭代次数({max_iterations})，请简化问题重试")


def _sse(event: str, data: str, meta: dict = None) -> str:
    """构建SSE事件"""
    payload = {"event": event, "data": data}
    if meta:
        payload["meta"] = meta
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
