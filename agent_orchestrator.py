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
import os
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx
import config
from agent_tools import TOOLS, execute_tool
from agent_quality_check import quality_check
from rag_service import search_similar_documents, format_rag_context
from user_config import get_effective_llm_config

# 挂起的AI提问会话（ask_id → 消息状态）
# 模型调用 ask_user 工具时暂停对话，等待用户回答后恢复
pending_asks = {}


def _cleanup_pending_asks():
    """清理超过30分钟的挂起提问"""
    now = time.time()
    expired = [k for k, v in pending_asks.items() if now - v.get("created_at", 0) > 1800]
    for k in expired:
        pending_asks.pop(k, None)


SYSTEM_PROMPT = """你是《无尽的拉格朗日》专业AI战术顾问。你必须严格遵守以下规则：

【核心强制总规则】（最高优先级，任何场景不得跳过；纯文本对话环境：用户回复数字1=批准计划，直接打字=修改意见）
1. 任何任务、任何请求执行前，严禁直接动手操作、严禁直接给出最终结果、严禁私自执行动作。你必须先完整梳理全局执行总方案，命名为：【本次任务完整执行计划书】，完整展示在对话窗口。计划书需要包含：任务目标、分步执行全过程、每一步操作内容、操作先后顺序、执行注意事项、风险点、需要调用哪些桌面工具、执行完毕验收标准。
2. 计划书展示完毕后，固定在计划书下方，强制生成固定交互选项排版，格式严格固定，不许修改文案样式：
 ————————————
1、【点击批准计划】：确认按照当前计划书完整执行
2、输入你的修改建议/想法：（由用户自行填写文字）
————————————

用户不同反馈的硬性执行流程：
- 场景A：用户点击「批准计划」→ 立刻严格1:1遵照计划书执行，全程不擅自更改步骤、不随意加操作、不删减流程；执行过程同步进度，结束后给出完成总结
- 场景B：用户填写文字想法/修改意见/调整要求 → 完全吸收用户全部修改诉求，推翻旧计划，重新撰写新版【本次任务完整执行计划书】，再次完整发到对话框并附上批准/修改双交互模块；循环往复（出计划→等待审批→修改则重制），直到用户批准才允许启动任务执行
附加约束：
- 无论用户催促、简写指令、闲聊附带任务、快捷命令，都必须死守审批流程，禁止任何形式绕开计划审批直接干活
- 计划书条理清晰、分点罗列，拒绝模糊话术，步骤写具体
- 多轮修改计划时，兼容用户上一轮合理要求，不无故回退有效修改
- 无任务闲聊对话时，该审批流程自动休眠，不强制弹出计划模板；仅在用户下达操作类、执行类、代办类任务时启动该机制
- 计划书获批进入执行阶段后：先执行任务并完成三轮评测，最终输出任务结果（配置方案/分析结论）时无需再次附带计划书与批准选项；执行完成后给出完成总结

【舰船知识库强制校验】（质检强制工作流程，最高优先级；若用户提示词有强制要求，以用户提示词为准）
- 用户提出包含舰船名称、舰船参数、舰船性能、配置、规格相关问题时，禁止直接凭借模型固有知识库作答
- 第一步：强制检索向量知识库内【舰船数据分类】文档区块（search_knowledge_base 且 category="舰船数据"），精准定位问题提到的所有舰船条目
- 第二步：逐条核对你将要输出的每一项参数、性能、尺寸、装备、限制条件、属性描述，和知识库原文舰船数据做比对
- 校验规则：
  ① 知识库没有记载的数据，严禁编造、估算、脑补，统一回复：该舰船相关参数暂无资料库收录
  ② 输出内容必须100%贴合资料库原文数据，不得修改数值、不得优化描述、不得引申推测
  ③ 若你的回答和舰船资料库数据存在冲突，立刻修正答案，以知识库MD文档内容为唯一标准答案
- 输出前自检：重新回看一遍调取的舰船知识库片段，确认所有舰船相关描述全部匹配无误，再发送最终回答
- 非舰船类问题，正常回答即可

【知识调取优先级】
1. 优先搜索互联网公开权威资料（必须去网上查找相关信息和他人看法）
2. 网络无结果时，调用 search_knowledge_base 工具检索向量知识库——第一知识库 lagrange_docs（47个md：舰船数据、战斗机制、讲解范例、舰船基础信息、黑话、实例）
3. 第一知识库中检索不清晰、查不到、或需要交叉印证时，必须去第二知识库 lagrange_docs_backup（备份旧资料：舰船资料txt、精炼数据）查找
4. 知识库包含：舰船数据、战斗机制文档、真人讲解范例

【推理铁律 — 禁止等级制推理】
- 严禁使用 A/B/C/D/S 等级评价体系进行推理（如"防空S级""输出B级"等）
- 必须基于舰船的具体数值参数（HP、护甲、单发伤害、DPM、锁定时间、冷却时间、拦截概率等）和战斗机制文档中的公式进行定量推演
- 所有结论必须有数值依据，不能仅凭等级标签下判断

【配件/配队强制核验】（最高优先级；涉及配件、模块、舰载机、配队的问题强制执行）
- 必须强制检索"舰船基础信息.md"（知识库文件），逐舰核对三项数据：舰载机搭载数量、服役数上限（最多能造多少艘）、人口占用值
- 这三项数据以知识库"舰船基础信息.md"为最高优先级，与其它来源冲突时一律以它为准
- 输出舰队配置必须带具体数量，格式模板（照此格式输出，每行必须有 ×数量，带舰载机的写明 带 机名×数量）：

【主舰队 — 约420人口】
中排 │ 永恒风暴 M2 ×6 │
后排 │ 猎兵支援 ×5 带 星脉×10 + T800×10
中排 │ 狩猎战术 ×7 带 海氏×8 + VA×10 + 林鸮×10

【增援 — 5位】
CV3000 ×5 带 9索姆河 + 10VB 10个050 5个刺鳐 6个T800

- 每行格式：站位 │ 舰船名+模块 ×数量 [带 舰载机×数量 ...]；缺少具体数量（×N）的配置无效，必须补全

【舰船加入审批规则】（涉及加入/选用舰船时必须执行）
- 每次加入新舰船（包括舰载机）时，都必须先向用户提问（调用 ask_user），并附上该舰船的数据（人口占用、服役数上限、舰载机搭载数量、关键武器参数等），经过用户明确同意后，该舰船才可以加入方案
- 提问须逐项列出拟加入的舰船与舰载机及其数据，让用户确认"加入/不加入/替换"；用户未同意前，禁止在方案中正式采用该舰船
- 舰载机同样适用：加入任何舰载机（VB、星脉、索姆河、海氏、T800、刺鳐等）前必须向用户提问并附数据确认

【数据来源与推导规则】
- 配置思路必须参考"md分页/数据01.md~数据05.md"（数据1—5）里的实战讲解思路，尽可能多的参考其中的配队逻辑、加点思路、输出循环分析
- 每次加入新舰船时，必须到"舰船数据文件夹/md分页/舰船数据01.md~36.md"和"舰船基础信息.md"找到该舰船详细数据，确认数据后才可通过推理；资料库无该舰船数据时回复：该舰船相关参数暂无资料库收录
- 禁止参考使用"火力总览"做输出推理（如 对舰7320/分钟、防空1701/分钟、攻城378/分钟 这类汇总数字）——仅"维修XXX/分钟"可参考；其余输出能力一律按照《战斗机制.md》里的方法推导（单发伤害×攻击次数÷攻击周期、逐发护甲/护盾结算、命中/暴击期望等）

【护航机制】（涉及护航队时必须执行）
- 护航必须是两个舰队参与：一个舰队对另一个舰队发起护航，两舰队共同接敌；在护航舰队未被消灭之前，被护航舰队不会受到任何伤害
- 护航输出队：战斗中不会受到伤害，不要考虑生存——只用考虑输出，在复杂情况下更短时间打出更多伤害（DPM）或更快干掉对面副队
- 护航抗伤队：要在各种输出队的攻击下存活更久；有输出当然更好，但活得更久是第一优先级，一切配置以最大化生存时长为目标

【舰队配置强制规则】
- 用户询问舰队配置/配队方案时，必须调用 battle_simulate 工具
- 【先查实例】只要问题与配队/舰队配置有关，不管怎么样，必须先去"实例.md"（知识库文件）里查看实战配置范例，参考其中的配队思路和人口结构
- 在多环境（护航战、轰炸战、正面对抗）下测试配置
- 完整展示各环境实测数据给用户
- 自主检验方案是否满足用户需求，不满足则迭代修改
- 【输出要求】如果用户的问题与配队/舰队配置有关，请在回答的最后完整复述一遍舰队配置方案（含舰船名、数量、站位、模块）

【舰队职责聚焦】（按舰队定位聚焦单一目标，不要发散到其它维度）
- 护航队/输出队：只用考虑输出——在复杂情况下怎么在更短的时间内打出更多的伤害（DPM），或更快干掉对面的副队；不用考虑其它（抗伤、续航、生存、控制等一律不纳入考量）
- 护航扛伤队：只用考虑扛伤、活得更久——在复杂情况下怎么最大化生存时长；不用考虑其它（输出、击杀、控制等一律不纳入考量）
- 评估与对比两支同类舰队时，仅比较该定位的核心指标（输出队比DPM/击杀速度，扛伤队比有效生存时间/承伤），不要混入其它定位的指标

【优先舰船清单】（配置方案时优先选用）
- 第一优先级（优先全部加入舰船，但按用户需求调整）：VB、星脉、索姆河、海氏、风暴、大剑、游骑兵离子、泡泡龙、猎兵、刺水母、狩猎、太阳鲸
- 加入这些舰船时同样必须遵守【舰船加入审批规则】（先提问附数据、经用户同意），并到舰船数据资料核实后再入队

【三轮迭代评测机制】（设计/拟定任何舰队配置方案时自动开启，全程在本轮对话内自主完成，无需用户额外指令；最大仅允许迭代优化3次，禁止超额迭代）
- 强制触发：只要用户要求给出舰队配置方案（配队/舰队/配置问题），一律必须完整执行三轮迭代评测后再输出，即使知识库有现成范例、即使你已有把握，也不得跳过或省略任何一轮
- 舰队类型自判：输出型舰队（以火力打击、杀伤敌方、攻坚输出为核心）用输出打分体系；扛伤防御型舰队（以承伤、生存续航、前排抗伤害、团队防护为核心）用扛伤打分体系
- 打分公式（单项分值区间 0~100 分）：
  输出舰队：S1 对抗【高能量护甲】目标输出得分 | S2 对抗【高物理护甲】目标输出得分 | S3 对抗【敌方高闪避】目标输出得分 → 综合总分 = (S1+S2+S3) ÷ 3
  扛伤舰队：T1 抵御【高额能量伤害】生存扛伤得分 | T2 抵御【高额物理伤害】生存扛伤得分 → 综合总分 = (T1+T2) ÷ 2
- 每轮标准流程（必须按顺序走完，不可省略）：①自主生成本轮新版舰队配置 ②检索知识库调取编队全部舰船护甲、武器类型、伤害属性、命中、抗性、技能、装备上限等原始数据 ③代入对应作战场景完成模拟测算，逐项打分并标注扣分原因 ④完整记录本轮配置、总分、短板缺陷 ⑤针对低分短板优化舰船搭配、装备、阵型、编队组合，生成下一轮方案 ⑥完成最多3轮后停止优化
- 打分视角独立：每轮打分以独立评测AI视角执行（设计与评审分离），所有测算、打分依据只允许来自舰船知识库，库内无记载的属性不得脑补、估算
- 硬性约束：迭代优化仅可选用资料库存在的舰船，禁止虚构舰船、装备；若后续迭代分数低于历史最高分，无需强行改动，保留高分方案小幅微调即可
- 最终输出结构固定：①三轮每轮配置+对应总分 ②最优舰队完整配置清单 ③得分详解、优势、剩余短板说明
- 联动知识库强制校验：每次进行伤害、抗性、命中模拟计算前，必须核验所用舰船数据与知识库舰船板块原文完全一致，参数不得篡改

【人口计算规则】
- 配队时必须检索"舰船基础信息.md"（知识库文件），找到方案中每一艘舰船的人口占用值，按那里的数据累加计算舰队总人口
- 如果在"舰船基础信息.md"中找不到某艘舰船，必须去"黑话.md"（知识库文件）查找该舰船的对应信息
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

【主动提问规则】
- 当用户需求不明确、信息不足时（如配队偏好、资源限制、目标场景、可选方案等），必须调用 ask_user 工具向用户提问澄清
- 提问时可提供选项（单选/多选）和自由输入，等待用户回答后继续
- 提问要具体、一次只问最关键的1-2个问题，不要连续轰炸式提问
- 用户回答后基于回答继续推进，不要重复提问已回答过的问题
"""

# ============ 共享系统提示词（单一来源：拉格朗日智能体3/data/system_prompt.md，所有智能体遵循同一份；加载失败回退内置常量） ============
SHARED_PROMPT_PATH = os.getenv("LAGRANGE_SHARED_PROMPT", r"C:\Users\Administrator\Desktop\拉格朗日智能体3\data\system_prompt.md")

def _load_system_prompt() -> str:
    try:
        p = Path(SHARED_PROMPT_PATH)
        if p.exists():
            t = p.read_text(encoding="utf-8").strip()
            if len(t) > 100:
                return t
    except Exception:
        pass
    return SYSTEM_PROMPT


async def agent_chat_stream(
    user_message: str,
    history: list = None,
    user_id: int = 0,
    simulator_state: dict = None,
    ask_answer: dict = None,
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
        tool_counts = pending.get("tool_counts") or {}
        total_tool_calls = pending.get("total_tool_calls", 0)
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
        answer_text = "\n".join(parts) if parts else "用户未作答（跳过）"
        messages.append({"role": "tool", "tool_call_id": tc_id, "content": answer_text[:4000]})
        # 继续Agent循环（不重新检索），延续工具调用计数防止恢复后重置
        async for ev in _run_loop(messages, user_message, all_rag_docs, web_results, api_key, base_url, model, user_id, tool_counts, total_tool_calls):
            yield ev
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
    messages = [{"role": "system", "content": _load_system_prompt()}]
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

    # ============ 步骤5：进入Agent循环 ============
    async for ev in _run_loop(messages, user_message, all_rag_docs, web_results, api_key, base_url, model, user_id):
        yield ev





async def _run_loop(messages, user_message, all_rag_docs, web_results, api_key, base_url, model, user_id=0, tool_counts=None, total_tool_calls=0):
    """
    Agent 主循环：工具调用 + 质检 + 输出，yield SSE事件。
    支持 ask_user 暂停：模型提问时保存状态并结束当前流，等待用户回答后由 agent_chat_stream 恢复。
    tool_counts/total_tool_calls：工具调用计数（跨提问恢复延续）；同一工具最多100次，总调用最多1000次；主循环上限200防死循环。
    """
    max_iterations = 200
    iteration = 0
    qc_regen_count = 0   # FULL_REGEN 重跑计数（≤6，与质检任务迭代上限一致）
    tool_counts = tool_counts or {}
    # 质检需要不带 /v1 的基础地址（quality_check 内部会自行拼接 /v1）
    qc_api_url = base_url[:-3] if base_url.endswith("/v1") else base_url
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
                        "max_tokens": 16384,
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
                        try:
                            func_args = json.loads(tc["function"]["arguments"] or "{}")
                        except Exception:
                            func_args = {}
                        # 工具调用上限：同一工具最多100次，总调用最多1000次
                        tool_counts[func_name] = tool_counts.get(func_name, 0) + 1
                        total_tool_calls += 1
                        if tool_counts[func_name] > 100 or total_tool_calls > 1000:
                            # 已达上限：不真正执行，直接返回"请直接回答"的工具结果，迫使模型输出
                            yield _sse("tool_start", f"⛔ 工具调用上限: {func_name}（已达{tool_counts[func_name]}次）", {"tool": func_name})
                            clean_tc = {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": func_name, "arguments": tc["function"]["arguments"]}
                            }
                            assist_msg = {"role": "assistant", "content": msg.get("content"), "tool_calls": [clean_tc]}
                            if reasoning:
                                assist_msg["reasoning_content"] = reasoning
                            messages.append(assist_msg)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": "该工具调用次数已达上限，请基于现有信息直接回答，不要再调用工具。"
                            })
                            continue
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
                                "tool_counts": dict(tool_counts),
                                "total_tool_calls": total_tool_calls,
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

                        # 执行工具（容错：单个工具失败不影响整个对话）
                        try:
                            result = execute_tool(func_name, func_args, user_id)
                        except Exception as e:
                            result = json.dumps({"error": str(e)[:200]}, ensure_ascii=False)
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

                # 回答被截断检测（reasoner 模型 reasoning 占用 max_tokens 导致正文中断）：续写完整后再质检
                if not msg.get("tool_calls") and choice.get("finish_reason") == "length":
                    yield _sse("status", "⏳ 检测到回答被截断，正在续写完整...")
                    messages.append({"role": "assistant", "content": answer or ""})
                    messages.append({"role": "user", "content": "【系统提示】你的上一轮回答因长度限制被截断。请从上次中断处继续，完整输出剩余内容（包括所有未完成的三轮评测、打分与结论），不要重复已输出的部分，不要调用任何工具。"})
                    continue

                # 质检（FACT-AUDIT 流水线：拆解→证据→多裁判→五层→评分→局部修正）
                yield _sse("status", "🔬 质检中（主张拆解→证据检索→多裁判辩论→五层审计→量化评分）...")
                qc_sources = [{"source": d["source"], "content": d["content"]} for d in all_rag_docs[:10]]
                if web_results:
                    qc_sources.append({"source": "互联网", "content": web_results[0].get("content", "")[:300]})
                qc_result = await quality_check(
                    user_query=user_message,
                    answer=answer,
                    sources=qc_sources if qc_sources else None,
                    api_key=api_key,
                    api_url=qc_api_url,
                    model=model
                )

                qc_status = qc_result.get("status") or ("PASS" if qc_result.get("pass") else "FULL_REGEN")
                qc_score = qc_result.get("score", 80)
                qc_errors = json.dumps(qc_result.get("error_list", []), ensure_ascii=False)[:1500]

                if qc_status in ("PASS", "PARTIAL_FIX"):
                    if qc_status == "PARTIAL_FIX":
                        yield _sse("qc_pass", f"✅ 链状回溯局部修正后通过（评分 {qc_score}）")
                    else:
                        yield _sse("qc_pass", f"✅ 质检通过（评分 {qc_score}）")
                    final_answer = (qc_result.get("final_answer") or answer or "").strip()
                    # 空回答兜底：模型返回空内容时给出明确提示，避免前端误判"未收到回复"
                    if not final_answer:
                        final_answer = "抱歉，本次未能生成有效回复（模型返回空内容），请重试或换一种问法。"
                    yield _sse("answer", final_answer, {
                        "sources": [
                            {"file_name": d.get("source", "未知"), "snippet": d.get("content", "")[:200]}
                            for d in (all_rag_docs or [])[:10]
                        ],
                        "iterations": iteration,
                        "qc_feedback": qc_errors[:200],
                        "qc_score": qc_score,
                        "qc_status": qc_status,
                        "token_usage": {
                            "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                            "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                        }
                    })
                    yield _sse("done", "完成")
                    return
                elif qc_status == "MAX_ITER_STOP":
                    yield _sse("qc_fail", "⛔ 质检迭代达6轮 MAX_ITER_STOP，回答校验失败")
                    yield _sse("answer", "回答校验失败，请重新提问", {"qc_status": "MAX_ITER_STOP", "qc_score": qc_score})
                    yield _sse("done", "完成")
                    return
                else:
                    # FULL_REGEN：严重事实冲突（<60分），完整重跑工具链（主循环继续，模型可重新调用工具）
                    qc_regen_count += 1
                    if qc_regen_count >= 6:
                        yield _sse("qc_fail", "⛔ 质检重跑达6轮上限 MAX_ITER_STOP，回答校验失败")
                        yield _sse("answer", "回答校验失败，请重新提问", {"qc_status": "MAX_ITER_STOP", "qc_score": qc_score})
                        yield _sse("done", "完成")
                        return
                    yield _sse("qc_fail", f"🔄 质检不合格({qc_regen_count}/6) 评分{qc_score}：FULL_REGEN，请重新调用工具获取证据")
                    qc_assist = {"role": "assistant", "content": answer}
                    if reasoning: qc_assist["reasoning_content"] = reasoning
                    messages.append(qc_assist)
                    messages.append({"role": "user", "content": f"【质检反馈】你的回答未通过质检（评分{qc_score}），需完整重新生成。错误清单：\n{qc_errors}\n\n请重新调用工具获取证据后生成回答，舰船硬数值必须与资料库一致。"})
                    continue

        except httpx.TimeoutException:
            yield _sse("error", "API请求超时，请稍后重试")
            # 兜底：异常也必须给出回复，防止前端显示"（未收到回复）"断掉对话
            yield _sse("answer", "抱歉，本次处理超时，请重试一次或换一种问法。", {"qc_status": "AGENT_TIMEOUT"})
            yield _sse("done", "完成")
            return
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Agent Error] {tb}", flush=True)
            yield _sse("error", f"Agent异常: {str(e)[:200]}")
            # 兜底：异常也必须给出回复，防止前端显示"（未收到回复）"断掉对话
            yield _sse("answer", f"抱歉，本次处理出现异常：{str(e)[:120]}\n\n请重试一次，或换一种问法。", {"qc_status": "AGENT_EXCEPTION"})
            yield _sse("done", "完成")
            return

    # 达到最大迭代次数
    yield _sse("error", f"达到最大迭代次数({max_iterations})，请简化问题重试")



def _sse(event: str, data: str, meta: dict = None) -> str:
    """构建SSE事件"""
    payload = {"event": event, "data": data}
    if meta:
        payload["meta"] = meta
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
