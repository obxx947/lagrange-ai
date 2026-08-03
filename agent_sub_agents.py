# -*- coding: utf-8 -*-
"""
子代理系统
----------
每个子代理负责检索知识库中特定分类的资料，汇总后汇报给主Agent。

子代理列表：
- 舰队配置子代理：检索所有与舰队配置/配队相关的资料文件
- 舰船数据子代理：检索舰船资料文件（护卫舰/驱逐舰/巡洋舰/战列/航母/战机/护航艇）
- 战斗机制子代理：检索战斗机制文档与公式
- 讲解范例子代理：检索真人讲解范例（例子1-30）

每个子代理执行时发出 SSE 事件，前端可实时显示活动状态。
"""

import json
import os
from pathlib import Path

from rag_service import search_similar_documents

# 资料分类 → 文件名关键词映射
CATEGORY_KEYWORDS = {
    "舰队配置": ["护航", "配队", "编队", "舰队", "战报", "航母", "支援", "轰炸", "站队", "阵容"],
    "舰船数据": ["护卫舰", "驱逐舰", "巡洋舰", "战列", "战机", "护航艇", "舰船", "旗舰"],
    "战斗机制": ["战斗机制", "公式", "伤害", "拦截", "防空", "维修", "系统", "武器"],
    "讲解范例": ["例子", "视频", "讲解", "分析", "评测", "蓝图", "实战"],
}

# 子代理定义
SUB_AGENTS = [
    {
        "name": "舰队配置子代理",
        "icon": "⚓",
        "description": "检索所有与舰队配置、配队、编队相关的资料文件，分析各舰船在队伍中的定位",
        "keywords": CATEGORY_KEYWORDS["舰队配置"],
    },
    {
        "name": "舰船数据子代理",
        "icon": "🚢",
        "description": "检索护卫舰/驱逐舰/巡洋舰/战列/航母/战机/护航艇全部舰船资料文件，提取具体数值参数",
        "keywords": CATEGORY_KEYWORDS["舰船数据"],
    },
    {
        "name": "战斗机制子代理",
        "icon": "⚙️",
        "description": "检索战斗机制文档，核对伤害公式、拦截系统、维修规则等底层机制",
        "keywords": CATEGORY_KEYWORDS["战斗机制"],
    },
    {
        "name": "讲解范例子代理",
        "icon": "🎙️",
        "description": "检索真人讲解范例（例子1-30），参考其分析风格与论证逻辑",
        "keywords": CATEGORY_KEYWORDS["讲解范例"],
    },
]


def run_sub_agent(agent_name: str, query: str, top_k: int = 4) -> dict:
    """
    运行单个子代理：按分类检索知识库并返回结果。
    """
    agent = next((a for a in SUB_AGENTS if a["name"] == agent_name), None)
    if not agent:
        return {"agent": agent_name, "results": [], "error": "未知子代理"}

    # 先按关键词扫描文件，再语义检索
    found = []
    keywords = agent["keywords"]
    kw_matches = _scan_files_by_keywords(query, keywords)
    if kw_matches:
        found.extend(kw_matches)

    # 语义检索
    try:
        docs = search_similar_documents(query, top_k=top_k)
        for d in docs:
            found.append({
                "source": d.get("source", "未知"),
                "score": round(d.get("score", 0), 3),
                "content": d.get("content", "")[:800],
            })
    except Exception as e:
        return {"agent": agent_name, "error": str(e), "results": found}

    # 去重（按source）
    seen = set()
    unique = []
    for f in found:
        key = f["source"]
        if key not in seen:
            seen.add(key)
            unique.append(f)
        elif len(unique) < len(found):
            # 同一文件多个chunk保留最高分
            pass

    return {
        "agent": agent_name,
        "icon": agent["icon"],
        "description": agent["description"],
        "results": unique[:8],
        "result_count": len(unique),
    }


def run_all_sub_agents(query: str) -> list:
    """并行运行所有子代理，返回汇总结果列表"""
    results = []
    for agent in SUB_AGENTS:
        r = run_sub_agent(agent["name"], query)
        results.append(r)
    return results


# 文件内容缓存（只读一次）
_file_cache = {}


def _get_file_contents() -> dict:
    """读取所有知识库文件内容（带缓存，只读一次）"""
    if _file_cache:
        return _file_cache

    docs_dir = Path(__file__).resolve().parent / "lagrange_docs"
    if not docs_dir.exists():
        return {}

    for file_path in docs_dir.rglob("*.txt"):
        try:
            rel = file_path.relative_to(docs_dir).as_posix()
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) >= 10:
                _file_cache[rel] = content
        except Exception:
            continue
    return _file_cache


def _scan_files_by_keywords(query: str, keywords: list) -> list:
    """
    按关键词扫描知识库文件（粗筛：文件名或内容包含关键词）。
    返回匹配的文件内容摘要。
    """
    all_files = _get_file_contents()
    if not all_files:
        return []

    matches = []
    for rel, content in all_files.items():
        # 文件名匹配 或 查询包含关键词
        if any(k in rel for k in keywords) or any(k in query for k in keywords):
            snippet = _find_relevant_snippet(content, query)
            matches.append({
                "source": rel,
                "score": 0.5,
                "content": snippet[:800],
            })
            if len(matches) >= 5:
                break
    return matches


def _find_relevant_snippet(content: str, query: str, max_len: int = 800) -> str:
    """在内容中查找与query最相关的片段"""
    # 简单策略：找query中第一个关键词出现的位置
    words = [w for w in query.split() if len(w) > 1]
    best_pos = -1
    for w in words[:5]:
        pos = content.find(w)
        if pos >= 0:
            best_pos = pos
            break

    if best_pos >= 0:
        start = max(0, best_pos - 100)
        return content[start:start + max_len]
    return content[:max_len]
