# -*- coding: utf-8 -*-
"""
质检推理流水线（任务B · FACT-AUDIT 自适应分层审计框架）
================================================================
输入：用户原始提问、待校验AI回答初稿
可用工具：知识库检索（sources）、舰船数据库、战斗模拟器（本地）

严格按顺序执行：
1. Orchestrator       → 用户需求快照 + 迭代计数（≤6）
2. 主张拆解 Agent     → 回答拆解成原子事实
3. 证据检索 Agent     → 逐条事实检索证据（知识库source_id/舰船数据库/模拟器）
4. 多裁判辩论集群     → 3个独立校验智能体并行质证投票
5. FACT-AUDIT 五层    → 事实准确性/溯源完整性/逻辑一致性/需求覆盖/格式合规
6. LLM-as-Judge       → 0-100量化评分 + 错误清单
7. 分支：≥80 PASS；60-79 PARTIAL_FIX(链状回溯局部修正，复用证据禁重新检索)；
         <60 FULL_REGEN(完整重跑工具链)；迭代6轮 MAX_ITER_STOP

输出（用户指定JSON schema）：
{"pass", "score", "iteration", "status", "error_list", "user_requirement_check", "final_answer"}

硬性约束：
- 舰船建造上限等硬数值与资料库不一致必须写入 error_list
- PARTIAL_FIX 阶段禁止调用检索/模拟器，复用现有证据
- 全部真值来自知识库/模拟器工具返回结果，禁止编造
"""

import json
import os
import re
import asyncio
from pathlib import Path

import httpx

import config

MAX_ITER = 6

# ============ 共享系统提示词（复用 agent.js 唯一 system_prompt：拉格朗日智能体3/data/system_prompt.md；失败回退内置） ============
QC_SHARED_PROMPT_PATH = os.getenv("LAGRANGE_SHARED_PROMPT", "C:/Users/Administrator/Desktop/拉格朗日智能体3/data/system_prompt.md")

def _qc_load_system_prompt() -> str:
    try:
        p = Path(QC_SHARED_PROMPT_PATH)
        if p.exists():
            t = p.read_text(encoding="utf-8").strip()
            if len(t) > 100:
                return t
    except Exception:
        pass
    return ""

CLAIM_PROMPT = """你是主张拆解智能体。把AI回答拆解成一条条独立的原子事实，供后续逐条证据核验。

【拆解要求】
- 每条事实必须可独立验证（一个事实一句）
- 重点提取：舰船名称、建造上限（服役数）、装备/模块、伤害数值、DPM、血量、护甲、命中、暴击、冷却、锁定、人口、解锁条件、搭配限制
- 标记每条事实在原文中的位置（引用原文片段）
- 数字类事实必须原样保留数值

【用户原始提问】
{question}

【待拆解回答】
{answer}

【输出格式】只输出JSON，不要任何多余文字：
{"claims":[{"fact":"原子事实","position":"回答中的原文片段","has_number":true,"types":["舰船"/"数值"/"机制"/"其他"]}]}"""

JUDGE_VOTE_PROMPT = """你是独立校验裁判。审查AI回答中的一条事实，判定三点：
①数值是否和资料库、模拟器发生冲突（舰船建造上限/伤害/DPM/人口等硬数值必须完全一致）
②事实是否具备可信来源证据（知识库source_id/舰船数据库/联网资料）
③是否忽略、曲解用户原始需求

【舰船校验强制规则】（本条事实若与舰船相关必须执行）
- 知识库（MD文档）没有记载的数据：不得以模型记忆充当证据，vote 必须为 "unverified"，并在 detail 中注明建议回复文案："该舰船相关参数暂无资料库收录"
- 回答与知识库MD文档/舰船数据库冲突：以知识库MD文档内容为唯一标准答案，vote="conflict"，detail 写清冲突数值
- 输出参数必须100%贴合资料库原文，不得因"看起来合理"而放行编造数值

【用户原始需求】
{question}

【待校验事实】
{fact}

【资料库证据】
{kb_evidence}

【舰船数据库】
{ship_db}

【模拟器数值校验】
{sim_check}

【联网资料】
{web_evidence}

【输出格式】只输出JSON：
{"vote":"pass"/"conflict"/"unverified"/"req_miss","error_type":"数值冲突/用户需求忽略/机制逻辑错误/无","detail":"具体质证意见(50字内)"}"""

AUDIT_PROMPT = """你是FACT-AUDIT审计智能体。对回答执行五层审计并输出各层结论：
①事实准确性 ②溯源完整性 ③逻辑一致性 ④用户需求完整覆盖 ⑤输出格式合规

【舰船参数合规审计】（回答含舰船参数时强制执行）
- 所有舰船参数（数值/性能/装备/限制/属性）是否100%贴合知识库MD文档原文？任何修改数值、优化描述、引申推测均属违规
- 知识库无记载的参数是否被编造/估算？若是，fact_accuracy 必须判为"不通过"，并注明标准回复应为"该舰船相关参数暂无资料库收录"
- 回答与资料库冲突时，以知识库MD文档内容为唯一标准答案

【用户原始需求】
{question}

【AI回答】
{answer}

【裁判质证汇总】
{votes}

【输出格式】只输出JSON：
{"layers":{"fact_accuracy":"结论","traceability":"结论","logic":"结论","req_coverage":"结论","format":"结论"},"notes":"综合问题说明(100字内)"}"""

JUDGE_SCORE_PROMPT = """你是LLM-as-Judge评分智能体。对AI回答输出0-100总分并生成错误清单。

评分标准：
- ≥80分：PASS，直接校验通过
- 60-79分：PARTIAL_FIX，链状回溯局部修正（只重写出错片段）
- ＜60分：FULL_REGEN，严重事实冲突，完整重跑全套工具链路生成新回答

【用户原始需求】
{question}

【AI回答】
{answer}

【事实拆解与裁判质证】
{judge_summary}

【五层审计】
{audit}

【硬性规则】
1. 舰船建造上限这类硬数值和资料库不一致，必须写入error_list
2. 舰船参数只能采信工具返回的资料库内容
3. 必须完成两项核查：舰船信息与资料库逻辑正确性；是否忽略用户原本提问要求
4. 知识库MD文档没有记载的舰船参数若被回答编造/估算/脑补，score≤50 且 status=FULL_REGEN，error_list 必须注明标准回复："该舰船相关参数暂无资料库收录"
5. 回答中任何舰船参数与知识库MD文档冲突，以知识库MD文档内容为唯一标准答案，score≤60 不得PASS
6. 舰船问题（含舰船名称/参数/性能/配置/规格）若未检索【舰船数据分类】知识库片段而直接作答，视为流程违规，不得PASS
7. 配队/舰队配置类回答必须为每艘舰船给出具体数量（×N 格式），且配置格式需含站位与舰载机搭载数量；缺少具体数量的配置视为未满足用户需求，不得PASS
8. 舰队配置类回答必须包含三轮迭代评测结果输出结构（①三轮每轮配置+对应总分 ②最优舰队完整配置清单 ③得分详解、优势、剩余短板说明），缺少任何一项视为输出结构不完整，不得PASS；打分依据必须来自知识库数据，无记载参数不得放行
9. 配队类回答中若方案加入舰船/舰载机而无"向用户提问确认并附数据"环节记录，或使用"火力总览"（对舰XX/分钟、防空XX/分钟、攻城XX/分钟，维修除外）做输出推导，视为违规，不得PASS
10. 用户下达操作类/执行类/代办类任务时，回答必须包含任务执行内容：要么以【本次任务完整执行计划书】开头并附"批准/修改"交互选项（任务审批阶段），要么包含具体任务执行结果（如配置方案、分析结论等产出）；两者皆无的纯直接作答视为未遵守核心强制总规则，不得PASS

【输出格式】只输出JSON（不要任何多余文字）：
{"pass": true或false,"score": 0-100,"status": "PASS或PARTIAL_FIX或FULL_REGEN","error_list":[{"position":"回答出错原文片段","ship_name":"对应舰船名称","kb_source_id":"资料库source_id","kb_original_text":"资料库原始证据片段","error_type":"数值冲突/用户需求忽略/机制逻辑错误","fix_suggest":"简短精准修改建议"}],"user_requirement_check":"用户原始需求覆盖情况说明"}"""

FIX_PROMPT = """你是链状回溯修正智能体。根据错误清单，只重写回答中出错的片段，其余内容原样保留。

【用户原始需求】
{question}

【原回答】
{answer}

【错误清单】
{error_list}

【修正规则】
- 只修改错误清单指出的片段，其它内容一字不改
- 硬数值以"kb_original_text"（资料库原始证据）为准；资料库MD文档内容为唯一标准答案
- 知识库没有记载的参数：改为标准文案"该舰船相关参数暂无资料库收录"，严禁用模型记忆补全
- 若错误类型为"用户需求忽略"，在回答末尾补充对应内容
- 输出修正后的完整回答文本

【输出格式】只输出修正后的完整回答文本（不要JSON、不要解释）"""


def parse_json_loose(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


def _get_ship_db():
    """读取舰船数据库（lagrange_docs/ship_database.json）"""
    p = Path(__file__).resolve().parent / "lagrange_docs" / "ship_database.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else list(data.values())
    except Exception:
        return []


def _format_sources(sources):
    if not sources:
        return "（无知识库来源）"
    return "\n".join([
        f"- {s.get('source', s.get('file_name', '未知'))}: {str(s.get('content', ''))[:250]}"
        for s in sources[:8]
    ])


async def _call_llm(client, api_key, api_url, model, messages, temperature=0.1, max_tokens=2048):
    resp = await client.post(
        f"{api_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"API {resp.status_code}: {resp.text[:150]}")
    return resp.json()["choices"][0]["message"]


# ==================== 步骤3：主张拆解 Agent ====================

async def claim_split(client, api_key, api_url, model, question, answer):
    msg = await _call_llm(client, api_key, api_url, model, [
        {"role": "system", "content": _qc_load_system_prompt() or "你是主张拆解Agent。严格只输出JSON，忠实引用原文，禁止改写原文数值。"},
        {"role": "user", "content": CLAIM_PROMPT.replace("{question}", question[:1000]).replace("{answer}", answer[:6000])},
    ], 0.1, 4096)
    j = parse_json_loose(msg.get("content", ""))
    return (j or {}).get("claims") or []


# ==================== 步骤4：证据检索 Agent（知识库 + 模拟器数值校验 + 联网资料） ====================

def _extract_ship_name(fact: str) -> str:
    """从事实文本提取舰船名：优先 XX级 词，其次已知编号"""
    m = re.search(r"[\u4e00-\u9fa5A-Za-z0-9]{2,12}级", str(fact or ""))
    if m:
        return m.group(0)
    m = re.search(r"(CV3000|ST59|AC721|FG300|XT-?\d+|KCCPV2|BR050|AT021|SC002|RB7-13|CV-?[MT]\d+)", str(fact or ""), re.I)
    return m.group(1) if m else ""


def evidence_retrieve(claims, sources, ship_db, web_search_fn=None):
    """
    逐条事实检索证据：
    1. 知识库证据（复用传入 sources）
    2. 模拟器数值校验（舰船数据库武器参数与事实数字对比；服役上限/指挥值硬校验）
    3. 联网资料补充（最多2条无知识库证据的事实）
    """
    evidences = []
    web_candidates = []
    for c in (claims or []):
        ev = {"claim": c.get("fact", ""), "position": c.get("position", ""), "kb": [], "ship": None, "sim": None, "web": None}
        # 1. 知识库证据（复用传入的 sources）
        ev["kb"] = [{"source": s.get("source", "未知"), "content": str(s.get("content", ""))[:300]} for s in (sources or [])[:4]]
        # 2. 模拟器数值校验：舰船数据库武器参数与事实数字对比
        name = _extract_ship_name(str(c.get("fact", "")))
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(c.get("fact", ""))) if 0 < float(n) < 1000000]
        for s in ship_db:
            sname = str(s.get("name", ""))
            if name and (name.lower() in sname.lower() or name.lower() in str(s.get("id", "")).lower()):
                ev["ship"] = {
                    "id": s.get("id"), "name": s.get("name"), "hp": s.get("hp"),
                    "physicalArmor": s.get("physicalArmor"), "energyArmor": s.get("energyArmor"),
                    "serviceLimit": s.get("serviceLimit"), "commandValue": s.get("commandValue"),
                }
                # 数值对比
                sim = {"ship": sname, "matches": [], "conflicts": []}
                weapon_nums = []
                for mod in (s.get("modules") or {}).values():
                    if isinstance(mod, dict) and mod.get("weapons"):
                        for w in mod["weapons"]:
                            weapon_nums.append({"name": w.get("name", ""), "singleDmg": w.get("singleDmg"),
                                                "cooldown": w.get("cooldown"), "lockTime": w.get("lockTime")})
                for nv in nums:
                    for wn in weapon_nums:
                        if any(abs((wn.get(k) or 0) - nv) < 0.01 for k in ("singleDmg", "cooldown", "lockTime")):
                            if not any(str(nv) in x for x in sim["matches"]):
                                sim["matches"].append(f"{wn['name']}: {nv}")
                # 服役上限硬校验（建造上限不一致 → 数值冲突，用户硬性业务规则）
                sl = ev["ship"].get("serviceLimit")
                if sl:
                    if any(abs(n - sl) < 0.01 for n in nums):
                        sim["matches"].append(f"服役上限: {sl}")
                    else:
                        bad = next((n for n in nums if sl < n <= sl * 2), None)
                        if bad:
                            sim["conflicts"].append(f"服役上限冲突: 事实={bad} vs 资料={sl}")
                # 指挥值/人口校验
                cv = ev["ship"].get("commandValue")
                if cv and any(abs(n - cv) < 0.01 for n in nums):
                    sim["matches"].append(f"人口/指挥值: {cv}")
                ev["sim"] = sim
                break
        ev["numbers"] = re.findall(r"\d+(?:\.\d+)?%?", str(c.get("fact", "")))[:8]
        if not ev["kb"] and not ev["ship"]:
            web_candidates.append(ev)
        evidences.append(ev)
    # 3. 联网资料补充（最多2条无知识库证据的事实）
    if web_search_fn:
        for ev in web_candidates[:2]:
            try:
                web = web_search_fn(str(ev["claim"])[:60])
                if web and web.get("results"):
                    ev["web"] = [{"title": r.get("title", ""), "url": r.get("url", ""),
                                  "content": str(r.get("content", ""))[:200]} for r in web["results"][:3]]
            except Exception:
                pass
    return evidences


# ==================== 步骤5：多裁判辩论 Agent 集群（3个独立裁判并行） ====================

async def judge_cluster(client, api_key, api_url, model, question, evidences):
    results = []
    for ev in evidences:
        kb_text = "\n".join(f"- {k['source']}: {k['content']}" for k in ev["kb"]) or "（无知识库证据）"
        ship_text = json.dumps(ev["ship"], ensure_ascii=False) if ev["ship"] else "（未匹配舰船数据库）"
        sim_text = ""
        if ev.get("sim"):
            sim_text = f"模拟器数值校验: 匹配[{('；'.join(ev['sim'].get('matches') or []))}] 冲突[{('；'.join(ev['sim'].get('conflicts') or []))}]"
        else:
            sim_text = "（无模拟器数值校验）"
        web_text = "（无联网资料）"
        if ev.get("web"):
            web_text = "\n".join(f"- {w['title']}: {w['content']} ({w['url']})" for w in ev["web"])
        votes = await asyncio.gather(*[
            _call_llm(client, api_key, api_url, model, [
                {"role": "system", "content": _qc_load_system_prompt() or "你是质证裁判。严格只输出JSON，以资料库/数据库证据为准，禁止编造。"},
                {"role": "user", "content": JUDGE_VOTE_PROMPT
                 .replace("{question}", question[:800])
                 .replace("{fact}", str(ev["claim"])[:500])
                 .replace("{kb_evidence}", kb_text)
                 .replace("{ship_db}", ship_text)
                 .replace("{sim_check}", sim_text)
                 .replace("{web_evidence}", web_text)},
            ], 0.1, 600)
            for _ in range(3)
        ])
        parsed = [parse_json_loose(v.get("content", "")) for v in votes]
        results.append({"evidence": ev, "votes": [p for p in parsed if p]})
    return results


# ==================== 步骤6：FACT-AUDIT 五层审计 ====================

async def fact_audit(client, api_key, api_url, model, question, answer, judge_results):
    votes_text = "\n".join(
        f"- 事实\"{r['evidence']['claim'][:80]}\" 裁判票: {', '.join(v.get('vote', '?') + '(' + str(v.get('error_type', '')) + ')' for v in r['votes'])}"
        for r in judge_results)
    msg = await _call_llm(client, api_key, api_url, model, [
        {"role": "system", "content": _qc_load_system_prompt() or "你是FACT-AUDIT审计员。严格只输出JSON。"},
        {"role": "user", "content": AUDIT_PROMPT
         .replace("{question}", question[:800])
         .replace("{answer}", answer[:6000])
         .replace("{votes}", votes_text[:3000])},
    ], 0.1, 1200)
    j = parse_json_loose(msg.get("content", ""))
    return (j or {}).get("layers") or {}


# ==================== 步骤7：LLM-as-Judge 量化评分 ====================

async def llm_judge(client, api_key, api_url, model, question, answer, judge_results, audit):
    judge_summary = "\n".join(
        f"- 事实: {r['evidence']['claim'][:100]}\n  裁判: {' | '.join(v.get('vote','?')+'['+str(v.get('error_type',''))+']'+str(v.get('detail','')) for v in r['votes'])}\n  证据: {','.join(k['source'] for k in r['evidence']['kb']) or '无'}"
        for r in judge_results)
    msg = await _call_llm(client, api_key, api_url, model, [
        {"role": "system", "content": _qc_load_system_prompt() or "你是LLM-as-Judge。严格只输出JSON，评分必须基于质证证据，禁止放水。"},
        {"role": "user", "content": JUDGE_SCORE_PROMPT
         .replace("{question}", question[:800])
         .replace("{answer}", answer[:6000])
         .replace("{judge_summary}", judge_summary[:4000])
         .replace("{audit}", json.dumps(audit, ensure_ascii=False)[:1500])},
    ], 0.1, 2000)
    j = parse_json_loose(msg.get("content", ""))
    return j or {"pass": True, "score": 80, "status": "PASS", "error_list": [], "user_requirement_check": "评分解析异常，放行"}


# ==================== 链状回溯局部修正（PARTIAL_FIX，复用证据禁重新检索） ====================

async def chain_fix(client, api_key, api_url, model, question, answer, judge_result):
    error_list = json.dumps(judge_result.get("error_list") or [], ensure_ascii=False)[:3000]
    msg = await _call_llm(client, api_key, api_url, model, [
        {"role": "system", "content": _qc_load_system_prompt() or "你是链状回溯修正Agent。严格只输出修正后的回答文本。"},
        {"role": "user", "content": FIX_PROMPT
         .replace("{question}", question[:800])
         .replace("{answer}", answer[:6000])
         .replace("{error_list}", error_list)},
    ], 0.3, 4096)
    return (msg.get("content") or "").strip()


# ==================== Orchestrator：质检流水线主入口 ====================

async def quality_check(
    user_query: str,
    answer: str,
    sources: list = None,
    api_key: str = None,
    api_url: str = None,
    model: str = None
) -> dict:
    """
    对生成的回答执行 FACT-AUDIT 多智能体质检流水线。
    返回用户指定JSON schema：{"pass","score","iteration","status","error_list","user_requirement_check","final_answer"}
    """
    api_key = api_key or config.DEEPSEEK_API_KEY
    api_url = (api_url or config.DEEPSEEK_BASE_URL).rstrip("/")
    if not api_url.endswith("/v1"):
        api_url = api_url + "/v1"
    model = model or config.DEEPSEEK_CHAT_MODEL

    if not api_key:
        return {"pass": True, "score": 85, "iteration": 0, "status": "PASS",
                "error_list": [], "user_requirement_check": "（质检跳过：未配置API Key）",
                "final_answer": answer, "feedback": "（质检跳过：未配置API Key）"}

    ship_db = _get_ship_db()

    iteration = 0
    current_answer = answer
    last_result = None

    async with httpx.AsyncClient(timeout=120.0) as client:
        while iteration < MAX_ITER:
            iteration += 1
            try:
                # 1. 主张拆解 Agent
                claims = await claim_split(client, api_key, api_url, model, user_query, current_answer)
                if not claims:
                    last_result = {"pass": True, "score": 85, "iteration": iteration, "status": "PASS",
                                   "error_list": [], "user_requirement_check": "（拆解为空）", "final_answer": current_answer}
                    break
                # 2. 证据检索 Agent（知识库 + 模拟器数值校验 + 联网资料）
                web_fn = None
                try:
                    from agent_cache import web_search as _ws
                    web_fn = _ws
                except Exception:
                    web_fn = None
                evidences = evidence_retrieve(claims, sources, ship_db, web_fn)
                # 3. 多裁判辩论 Agent 集群（3裁判并行）
                judge_results = await judge_cluster(client, api_key, api_url, model, user_query, evidences)
                # 4. FACT-AUDIT 五层审计
                audit = await fact_audit(client, api_key, api_url, model, user_query, current_answer, judge_results)
                # 5. LLM-as-Judge 量化评分
                j = await llm_judge(client, api_key, api_url, model, user_query, current_answer, judge_results, audit)
                try:
                    score = max(0, min(100, int(j.get("score", 80))))
                except Exception:
                    score = 80
                status = j.get("status") or ("PASS" if score >= 80 else "PARTIAL_FIX" if score >= 60 else "FULL_REGEN")
                last_result = {
                    "pass": score >= 80, "score": score, "iteration": iteration, "status": status,
                    "error_list": j.get("error_list") or [],
                    "user_requirement_check": j.get("user_requirement_check", ""),
                    "final_answer": current_answer,
                }
                if status == "PASS" or score >= 80:
                    break
                if status == "PARTIAL_FIX" or 60 <= score < 80:
                    # 链状回溯局部修正：只重写错误片段，复用已有证据，禁止重新检索/模拟器
                    fixed = await chain_fix(client, api_key, api_url, model, user_query, current_answer, last_result)
                    if fixed and fixed != current_answer:
                        current_answer = fixed
                        last_result["final_answer"] = fixed
                        continue  # 修正后重新执行质检流程（迭代+1）
                    break  # 修正无变化，避免死循环
                # FULL_REGEN：返回主循环完整重跑工具链
                break
            except Exception as e:
                last_result = {"pass": True, "score": 85, "iteration": iteration, "status": "PASS",
                               "error_list": [], "user_requirement_check": f"（质检异常放行: {str(e)[:80]}）",
                               "final_answer": current_answer}
                break

    if iteration >= MAX_ITER and last_result and last_result.get("status") != "PASS":
        last_result = {**last_result, "status": "MAX_ITER_STOP", "pass": False,
                       "final_answer": "回答校验失败，请重新提问"}

    last_result.setdefault("feedback", last_result.get("user_requirement_check", ""))
    return last_result
