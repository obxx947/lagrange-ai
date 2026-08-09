# -*- coding: utf-8 -*-
"""
知识库开发流水线（任务A · 批量知识库开发，与聊天问答完全分离）
================================================================
Orchestrator 总控启动批量任务，读取 lagrange_docs/ 全部原始文档：

1. 摄入清洗 Agent    → 清洗文本（BOM/乱码/重复段落/无效换行）+ 提取元数据
2. Chunk 决策 Agent  → 语义分块（父子块：子块≤500字符检索、父块完整章节上下文）+ 打标签
3. 实体抽取 Agent    → LLM 批量抽取知识图谱三元组 (主体, 关系, 客体)
4. 冲突检测仲裁 Agent→ LLM 跨文档比对 + 多裁判辩论质证 + 勘误报告

产物输出到 kb_dev_output/：
- cleaned/          清洗后文档（txt）
- chunks.json       父子块分块数据集
- kg.json           知识图谱三元组
- 勘误报告.md       冲突明细与修正建议

硬性约束：
- 任意任务最大迭代 6 轮，到达上限直接终止
- 全部真值来自原始文档，禁止模型编造
- 批量任务与问答质检任务分开运行

用法: python kb_pipeline.py
"""

import json
import re
import time
import asyncio
from pathlib import Path

import httpx

from user_config import get_effective_llm_config

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "lagrange_docs"
OUT_DIR = BASE_DIR / "kb_dev_output"

MAX_ITER = 6          # 全局迭代上限
CHUNK_SIZE = 500      # 子块大小
CHUNK_OVERLAP = 50    # 子块重叠
MAX_CONFLICTS = 30    # 最多仲裁的冲突组数

TAG_KEYWORDS = {
    "舰船": ["护卫舰", "驱逐舰", "巡洋舰", "战列", "战机", "护航艇", "航母", "舰船", "旗舰", "级", "人口"],
    "装备": ["武器", "模块", "炮", "导弹", "鱼雷", "机库", "装甲", "防空", "机载"],
    "机制": ["伤害", "拦截", "防空", "冷却", "锁定", "维修", "命中", "暴击", "闪避", "系统", "机制", "公式"],
    "公式": ["公式", "=", "%", "×", "÷"],
    "案例": ["例子", "实战", "配置", "配队", "人口", "战报", "实例"],
}

# ==================== 步骤1：摄入清洗 Agent ====================

def clean_text(raw: str, source_id: str) -> dict:
    t = str(raw or "")
    t = t.lstrip("\ufeff")                                   # BOM
    t = re.sub(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]", "", t)  # 控制字符
    t = re.sub(r"[\u200B\u200C\u200D]", "", t)               # 零宽字符
    t = t.replace("\r\n", "\n").replace("\r", "\n")          # 统一换行
    t = re.sub(r"[ \t]+", " ", t)                            # 压缩空白
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    seen = {}
    out = []
    for line in lines:
        seen[line] = seen.get(line, 0) + 1
        if seen[line] >= 3:                                  # 重复段落
            continue
        out.append(line)
    t = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return {"text": t, "meta": extract_meta(t, source_id)}


def extract_meta(text: str, source_id: str) -> dict:
    doc_name = str(source_id).replace(".txt", "").replace("舰船资料/", "")
    meta = {"source_id": source_id, "doc_name": doc_name, "chapters": []}
    m = re.search(r"(19|20)\d{2}|v\d+(\.\d+)?", str(source_id), re.I)
    meta["version"] = m.group(0) if m else ""
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"^[一二三四五六七八九十百]+、", s) or re.match(r"^第[一二三四五六七八九十百]+[章节部分]", s) \
           or re.match(r"^[0-9]+[\.、]", s) or re.match(r"^#+ ", s) or re.match(r"^【.+】", s):
            meta["chapters"].append(s[:40])
    return meta


# ==================== 步骤2：Chunk 决策 Agent ====================

def tag_text(content: str) -> list:
    tags = []
    for tag, kws in TAG_KEYWORDS.items():
        if any(k in content for k in kws):
            if tag == "公式" and "=" not in content and not re.search(r"\d+[%×÷]", content):
                continue
            if tag not in tags:
                tags.append(tag)
    return tags or ["其他"]


def is_chapter_title(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r"^[一二三四五六七八九十百]+、", s) or re.match(r"^第[一二三四五六七八九十百]+[章节部分]", s)
                or re.match(r"^[0-9]+[\.、]", s) or re.match(r"^#+ ", s) or re.match(r"^【.+】", s))


def chunk_text(cleaned: dict) -> list:
    meta = cleaned["meta"]
    chunks = []
    parent_idx = 0
    child_idx = 0
    lines = cleaned["text"].split("\n")
    cur = {"title": "全文", "parts": []}
    parents = []
    for line in lines:
        if is_chapter_title(line):
            parents.append(cur)
            cur = {"title": line.strip()[:40], "parts": [line]}
        else:
            cur["parts"].append(line)
    parents.append(cur)

    for p in parents:
        parent_content = "\n".join(p["parts"]).strip()
        if not parent_content:
            continue
        pid = f"{meta['source_id']}#p{parent_idx}"
        parent_idx += 1
        chunks.append({
            "id": pid, "parent_id": None, "source_id": meta["source_id"],
            "chapter": p["title"], "tag": tag_text(parent_content),
            "content": parent_content, "level": "parent",
        })
        # 子块：段落合并至≤500字符，带50字符重叠
        buf = ""
        for para in parent_content.split("\n"):
            para = para.strip()
            if not para:
                continue
            if buf and len(buf + "\n" + para) > CHUNK_SIZE:
                chunks.append({
                    "id": f"{pid}#c{child_idx}", "parent_id": pid,
                    "source_id": meta["source_id"], "chapter": p["title"],
                    "tag": tag_text(buf), "content": buf, "level": "child",
                })
                child_idx += 1
                buf = buf[-CHUNK_OVERLAP:] + "\n" + para
            else:
                buf = buf + "\n" + para if buf else para
        if buf:
            chunks.append({
                "id": f"{pid}#c{child_idx}", "parent_id": pid,
                "source_id": meta["source_id"], "chapter": p["title"],
                "tag": tag_text(buf), "content": buf, "level": "child",
            })
            child_idx += 1
    return chunks


# ==================== LLM 调用 ====================

ENTITY_PROMPT = """你是知识图谱实体抽取智能体。从下面的游戏资料文本中抽取全部关键事实，输出知识图谱三元组。

【抽取范围】
- 舰船：名称、级别、类型、定位、人口占用、建造上限（服役数）
- 数值：伤害、护甲、护盾、命中、暴击、冷却、锁定、DPM、血量
- 机制：公式、规则、条件
- 装备/模块：名称、效果、获取/解锁条件

【输出格式】只输出JSON，不要任何多余文字：
{"entities":[{"subject":"主体(如 云海级护卫舰)","relation":"关系(如 建造上限)","object":"客体(如 10)","evidence":"原文片段(20字以内)"}]}

【资料文本】
{text}"""

JUDGE_PROMPT = """你是冲突仲裁裁判。资料库中同一实体出现了不同取值，请基于"原始证据"判定基准真值。

【冲突项】主体: {subject} | 属性: {relation}
【候选值】:
{values}

【判定规则】
- 以资料原文证据为准，证据更具体、更权威（官方/资料文件）的取值优先
- 若无法判定，verdict="存疑"，保留全部候选
- 禁止编造资料外的数值

【输出格式】只输出JSON：
{"verdict":"确定/存疑","correct_value":"选定的正确值(存疑时留空)","reason":"判定理由(30字内)"}"""


def parse_json_loose(text: str):
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
    a = re.search(r"\[[\s\S]*\]", text)
    if a:
        try:
            return json.loads(a.group(0))
        except Exception:
            pass
    return None


async def call_llm(client, api_key, base_url, model, messages, temperature=0.1, max_tokens=2048):
    resp = await client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"API {resp.status_code}: {resp.text[:150]}")
    return resp.json()["choices"][0]["message"]


# ==================== 步骤3：实体抽取 Agent ====================

async def extract_entities(cleaned_docs, llm_cfg, log, iter_state):
    all_entities = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for doc in cleaned_docs:
            text = doc["text"]
            if not text.strip():
                continue
            for i in range(0, len(text), 6000):
                seg = text[i:i + 6000]
                log(f"🧠 实体抽取: {doc['meta']['source_id']}（分段 {i // 6000 + 1}）")
                try:
                    msg = await call_llm(
                        client, llm_cfg["api_key"], llm_cfg["base_url"], llm_cfg["model"],
                        [
                            {"role": "system", "content": "你是实体抽取Agent。严格只输出JSON，禁止编造资料中不存在的内容。"},
                            {"role": "user", "content": ENTITY_PROMPT.replace("{text}", seg)},
                        ], 0.1, 4096)
                    j = parse_json_loose(msg.get("content", ""))
                    for e in (j or {}).get("entities", []) or []:
                        if e.get("subject") and e.get("relation") and e.get("object"):
                            all_entities.append({
                                "subject": str(e["subject"]).strip(),
                                "relation": str(e["relation"]).strip(),
                                "object": str(e["object"]).strip(),
                                "evidence": str(e.get("evidence", "")).strip(),
                                "source_id": doc["meta"]["source_id"],
                            })
                    log(f"✅ 实体抽取完成: {doc['meta']['source_id']}（+{len((j or {}).get('entities', []) or [])}条）")
                except Exception as e:
                    log(f"⚠️ 实体抽取失败 {doc['meta']['source_id']}: {str(e)[:80]}")
                iter_state()
                if iter_state.count >= MAX_ITER:
                    return all_entities
    return all_entities


# ==================== 步骤4：冲突检测仲裁 Agent ====================

def group_conflicts(entities):
    groups = {}
    for e in entities:
        key = f"{e['subject']}|{e['relation']}"
        groups.setdefault(key, [])
        if not any(x["object"] == e["object"] for x in groups[key]):
            groups[key].append(e)
    return [(k, v) for k, v in groups.items() if len(v) > 1][:MAX_CONFLICTS]


async def arbitrate_conflicts(conflicts, llm_cfg, log, iter_state):
    report = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for key, candidates in conflicts:
            subject, relation = key.split("|")
            values = "\n".join(
                f"{i + 1}. 值=\"{c['object']}\"  来源={c['source_id']}  证据=\"{c['evidence']}\""
                for i, c in enumerate(candidates))
            log(f"⚖️ 冲突仲裁: {subject} 的{relation}（{len(candidates)}个候选）")
            votes = []
            try:
                results = await asyncio.gather(*[
                    call_llm(
                        client, llm_cfg["api_key"], llm_cfg["base_url"], llm_cfg["model"],
                        [
                            {"role": "system", "content": "你是质证裁判。严格只输出JSON，以证据为准，禁止编造。"},
                            {"role": "user", "content": JUDGE_PROMPT.replace("{subject}", subject).replace("{relation}", relation).replace("{values}", values)},
                        ], 0.1, 800)
                    for _ in range(2)
                ])
                for r in results:
                    j = parse_json_loose(r.get("content", ""))
                    if j:
                        votes.append(j)
            except Exception as e:
                log(f"⚠️ 仲裁调用失败: {str(e)[:80]}")
            if not votes:
                report.append({"subject": subject, "relation": relation, "candidates": candidates, "verdict": "存疑", "reason": "裁判调用失败"})
                iter_state()
                if iter_state.count >= MAX_ITER:
                    return report
                continue
            decided = [v for v in votes if v.get("verdict") == "确定" and v.get("correct_value")]
            agreed = {}
            for v in decided:
                agreed[v["correct_value"]] = agreed.get(v["correct_value"], 0) + 1
            best = max(agreed.items(), key=lambda x: x[1]) if agreed else None
            if best and best[1] >= 1:
                reason = next((v["reason"] for v in decided if v["correct_value"] == best[0]), "")
                report.append({"subject": subject, "relation": relation, "candidates": candidates,
                               "verdict": "确定", "correct_value": best[0], "reason": reason})
            else:
                report.append({"subject": subject, "relation": relation, "candidates": candidates,
                               "verdict": "存疑", "reason": "；".join(v.get("reason", "") for v in votes)})
            iter_state()
            if iter_state.count >= MAX_ITER:
                return report
    return report


# ==================== Orchestrator 总控 ====================

def build_report_markdown(results):
    md = f"# 知识库勘误报告\n\n生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "## 统计\n"
    md += f"- 文档数: {len(results['cleaned'])}\n"
    md += f"- 分块数: {len(results['chunks'])}（父块 {sum(1 for c in results['chunks'] if c['level']=='parent')} / 子块 {sum(1 for c in results['chunks'] if c['level']=='child')}）\n"
    md += f"- 三元组: {len(results['entities'])}\n"
    md += f"- 冲突项: {len(results['report'])}\n\n## 冲突明细\n\n"
    for i, r in enumerate(results["report"], 1):
        md += f"### {i}. {r['subject']} → {r['candidates'][0]['relation']}\n"
        md += f"- 判定: **{r['verdict']}**" + (f" → 正确值: {r['correct_value']}\n" if r.get("correct_value") else "\n")
        md += f"- 理由: {r['reason']}\n- 候选:\n"
        for c in r["candidates"]:
            md += f"  - {c['object']}（来源: {c['source_id']}，证据: {c['evidence']}）\n"
        md += "\n"
    return md


class IterState:
    def __init__(self, max_iter=MAX_ITER):
        self.count = 0
        self.max = max_iter

    def __call__(self):
        self.count += 1

    @property
    def reached(self):
        return self.count >= self.max


async def run_pipeline():
    log = lambda msg: print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    llm_cfg = get_effective_llm_config(0)
    if not llm_cfg.get("api_key"):
        log("❌ 未配置API Key（user_config），实体抽取/冲突仲裁将跳过，仅完成清洗与分块")
    base_url = llm_cfg["api_url"].rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    llm_cfg["base_url"] = base_url

    # 读取全部原始文档
    docs = sorted(DOCS_DIR.rglob("*.txt")) if DOCS_DIR.exists() else []
    if not docs:
        log(f"❌ 未找到文档目录: {DOCS_DIR}")
        return
    log(f"🚀 Orchestrator 启动：读取 {len(docs)} 个原始文档")

    iter_state = IterState()

    # 步骤1：摄入清洗
    log("🧹 步骤1 摄入清洗Agent 开始...")
    cleaned = []
    for p in docs:
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
            cleaned.append(clean_text(raw, str(p.relative_to(DOCS_DIR)).replace("\\", "/")))
        except Exception as e:
            log(f"⚠️ 清洗失败 {p.name}: {str(e)[:60]}")
        iter_state()
        if iter_state.reached:
            log("⛔ 达到最大迭代上限，终止")
            break
    log(f"✅ 清洗完成：{len(cleaned)} 个文档")

    # 步骤2：Chunk 决策
    log("🧩 步骤2 Chunk决策Agent 开始（语义分块+父子块+打标签）...")
    chunks = []
    for doc in cleaned:
        chunks.extend(chunk_text(doc))
        iter_state()
        if iter_state.reached:
            break
    log(f"✅ 分块完成：{len(chunks)} 个块")

    entities = []
    report = []
    if llm_cfg.get("api_key"):
        # 步骤3：实体抽取
        log("🧠 步骤3 实体抽取Agent 开始（LLM批量）...")
        entities = await extract_entities(cleaned, llm_cfg, log, iter_state)
        log(f"✅ 实体抽取完成：{len(entities)} 条三元组")

        # 步骤4：冲突检测仲裁
        log("⚖️ 步骤4 冲突检测仲裁Agent 开始（跨文档比对+多裁判辩论）...")
        conflicts = group_conflicts(entities)
        log(f"🔍 发现 {len(conflicts)} 组冲突候选")
        report = await arbitrate_conflicts(conflicts, llm_cfg, log, iter_state)
        decided = sum(1 for r in report if r["verdict"] == "确定")
        log(f"✅ 仲裁完成：{len(report)} 项（确定 {decided} / 存疑 {len(report) - decided}）")
    else:
        log("⏭️ 跳过实体抽取与冲突仲裁（无API Key）")

    # 产物输出
    OUT_DIR.mkdir(exist_ok=True)
    clean_dir = OUT_DIR / "cleaned"
    clean_dir.mkdir(exist_ok=True)
    for doc in cleaned:
        safe = doc["meta"]["source_id"].replace("/", "_").replace("\\", "_")
        (clean_dir / safe).write_text(doc["text"], encoding="utf-8")
    (OUT_DIR / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "kg.json").write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "勘误报告.md").write_text(build_report_markdown({
        "cleaned": cleaned, "chunks": chunks, "entities": entities, "report": report,
    }), encoding="utf-8")
    log(f"🏁 知识库开发流水线完成，产物已输出到 {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
