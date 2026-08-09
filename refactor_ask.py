# -*- coding: utf-8 -*-
import sys

content = open('agent_orchestrator.py', 'r', encoding='utf-8').read()

# 1. 顶部加 import uuid 和 pending_asks 缓存
content = content.replace(
    "import json\nimport time\nfrom typing import AsyncGenerator, Optional",
    "import json\nimport time\nimport uuid\nfrom typing import AsyncGenerator, Optional"
)
content = content.replace(
    'SYSTEM_PROMPT = """你是《无尽的拉格朗日》专业AI战术顾问。你必须严格遵守以下规则：',
    '''# 挂起的AI提问会话（ask_id → 消息状态）
# 模型调用 ask_user 工具时暂停对话，等待用户回答后恢复
pending_asks = {}


def _cleanup_pending_asks():
    """清理超过30分钟的挂起提问"""
    now = time.time()
    expired = [k for k, v in pending_asks.items() if now - v.get("created_at", 0) > 1800]
    for k in expired:
        pending_asks.pop(k, None)


SYSTEM_PROMPT = """你是《无尽的拉格朗日》专业AI战术顾问。你必须严格遵守以下规则：'''
)

# 2. agent_chat_stream 签名加 ask_answer
content = content.replace(
    "async def agent_chat_stream(\n    user_message: str,\n    history: list = None,\n    user_id: int = 0,\n    simulator_state: dict = None,\n) -> AsyncGenerator[str, None]:",
    "async def agent_chat_stream(\n    user_message: str,\n    history: list = None,\n    user_id: int = 0,\n    simulator_state: dict = None,\n    ask_answer: dict = None,\n) -> AsyncGenerator[str, None]:"
)

# 3. api_key检查后插入 ask_answer 恢复分支
ask_resume = '''
    # ============ 提问恢复分支（用户已回答AI提问，继续对话） ============
    if ask_answer:
        ask_id = ask_answer.get("ask_id", "")
        pending = pending_asks.pop(ask_id, None)
        if not pending:
            yield _sse("error", "提问会话已过期（超过30分钟），请重新提问")
            return
        messages = pending["messages"]
        all_rag_docs = pending.get("all_rag_docs", [])
        web_results = pending.get("web_results", [])
        # 找到最后一条assistant tool_calls的id，作为ask_user的工具结果
        tc_id = None
        for m in reversed(messages):
            if m.get("tool_calls"):
                tc_id = m["tool_calls"][-1].get("id")
                break
        if not tc_id:
            yield _sse("error", "提问状态异常，请重新发送消息")
            return
        selections = ask_answer.get("selections", []) or []
        free_text = ask_answer.get("free_text", "") or ""
        parts = []
        if selections:
            parts.append("用户选择：" + "、".join(str(s) for s in selections))
        if free_text and str(free_text).strip():
            parts.append("用户补充说明：" + str(free_text).strip())
        answer_text = "\\n".join(parts) if parts else "用户未作答（跳过）"
        messages.append({"role": "tool", "tool_call_id": tc_id, "content": answer_text[:4000]})
        # 继续Agent循环（不重新检索）
        async for ev in _run_loop(messages, user_message, all_rag_docs, web_results, api_key, base_url, model, user_id):
            yield ev
        return

'''
old_block = '''    if not api_key:
        yield _sse("error", "请先在设置页面配置大模型API Key（右上角⚙️）")
        return

    # ============ 步骤1：启动子代理并行检索 ============'''
new_block = '''    if not api_key:
        yield _sse("error", "请先在设置页面配置大模型API Key（右上角⚙️）")
        return
''' + ask_resume + '''    # ============ 步骤1：启动子代理并行检索 ============'''
if old_block not in content:
    print("ERROR: api_key block not found")
    sys.exit(1)
content = content.replace(old_block, new_block)

# 4. 提取循环体
start_marker = "    # 步骤5：Agent 循环（最多50轮推理+工具调用）"
end_marker = '    yield _sse("error", f"达到最大迭代次数({max_iterations})，请简化问题重试")'
s = content.find(start_marker)
e = content.find(end_marker)
if s < 0 or e < 0:
    print("ERROR: loop markers not found", s, e)
    sys.exit(1)

run_loop_fn = '''async def _run_loop(messages, user_message, all_rag_docs, web_results, api_key, base_url, model, user_id=0):
    """
    Agent 主循环：工具调用 + 质检 + 输出，yield SSE事件。
    支持 ask_user 暂停：模型提问时保存状态并结束当前流，等待用户回答后由 agent_chat_stream 恢复。
    """
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

                        # ======== ask_user 特殊处理：暂停对话，向用户提问 ========
                        if func_name == "ask_user":
                            clean_tc = {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": func_name, "arguments": tc["function"]["arguments"]}
                            }
                            assist_msg = {"role": "assistant", "content": msg.get("content"), "tool_calls": [clean_tc]}
                            if reasoning:
                                assist_msg["reasoning_content"] = reasoning
                            messages.append(assist_msg)
                            # 生成提问ID并保存状态
                            ask_id = "ask_" + uuid.uuid4().hex[:12]
                            _cleanup_pending_asks()
                            pending_asks[ask_id] = {
                                "messages": list(messages),
                                "all_rag_docs": all_rag_docs,
                                "web_results": web_results,
                                "created_at": time.time(),
                            }
                            question = func_args.get("question", "请告诉我你的需求")
                            options = func_args.get("options") or []
                            qtype = func_args.get("type") or ("multiple" if len(options) > 1 else "free")
                            required = func_args.get("required", True)
                            yield _sse("ask_user", question, {
                                "ask_id": ask_id,
                                "options": options,
                                "type": qtype,
                                "required": required,
                            })
                            yield _sse("awaiting_user", "⏸️ 等待用户回答...")
                            return  # 结束当前流，等待用户回答

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

                # 质检（质检Agent也会读取检索资料）
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
                    messages.append({"role": "user", "content": f"【质检反馈】你的回答未通过质检，请根据以下意见修改：\\n{qc_result.get('feedback', '')}\\n\\n请重新生成回答。"})
                    continue

        except httpx.TimeoutException:
            yield _sse("error", "API请求超时，请稍后重试")
            return
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Agent Error] {tb}", flush=True)
            yield _sse("error", f"Agent异常: {str(e)[:200]}")
            return

    # 达到最大迭代次数
    yield _sse("error", f"达到最大迭代次数({max_iterations})，请简化问题重试")


'''

# 替换循环体为调用
content = content[:s] + "    # ============ 步骤5：进入Agent循环 ============\n    async for ev in _run_loop(messages, user_message, all_rag_docs, web_results, api_key, base_url, model, user_id):\n        yield ev\n\n\n" + content[e+len(end_marker):]

# 在 _sse 定义前插入 _run_loop 函数
marker = "def _sse(event: str, data: str, meta: dict = None) -> str:"
if marker not in content:
    print("ERROR: _sse marker not found")
    sys.exit(1)
content = content.replace(marker, run_loop_fn + "\n" + marker, 1)

open('agent_orchestrator.py', 'w', encoding='utf-8').write(content)
print("重构完成")
