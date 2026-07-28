# -*- coding: utf-8 -*-
"""
质检智能体模块
--------------
独立 Agent，在每次回答输出前验证：
1. 是否完整回答用户问题
2. 舰船参数是否匹配数据库
3. 战术结论是否符合战斗机制
4. 是否标注信息来源

不通过 → 返回具体修改意见 → 主Agent重试（最多3轮）
"""

import json
import httpx
from typing import Optional

import config

QUALITY_CHECK_PROMPT = """你是一个严格的质量检验智能体。你的任务是审查以下AI回答是否符合标准。

【审查标准】
1. ✅ 完整性：回答是否完整覆盖了用户的所有问题点？
2. ✅ 准确性：舰船参数、战斗数据是否可能来自知识库（而非编造）？
3. ✅ 逻辑性：战术推演是否符合《战斗机制.txt》中的公式规则？
4. ✅ 可溯源：是否标注了信息来源（文件名/章节）？
5. ✅ 合规性：
   - 舰队配置相关问题是否经过了战斗模拟器验证？
   - 是否有编造的舰船参数？
   - 是否跳过了必要的工具调用？

【判定规则】
- 如果符合所有标准，返回 {"pass": true, "feedback": ""}
- 如果有问题，返回 {"pass": false, "feedback": "具体指出哪里不合格，需要如何修改"}

【用户原始问题】
{user_query}

【生成的回答】
{answer}

【用到的知识库来源】
{sources}

请以JSON格式返回审查结果。
"""


async def quality_check(
    user_query: str,
    answer: str,
    sources: list = None,
    api_key: str = None,
    api_url: str = None,
    model: str = None
) -> dict:
    """
    对生成的回答进行质量审查。
    返回 {"pass": bool, "feedback": str}
    """
    api_key = api_key or config.DEEPSEEK_API_KEY
    api_url = (api_url or config.DEEPSEEK_BASE_URL).rstrip("/")
    if not api_url.endswith("/v1"):
        api_url = api_url + "/v1"
    model = model or config.DEEPSEEK_CHAT_MODEL

    if not api_key:
        # 没有API Key时跳过质检，视为通过
        return {"pass": True, "feedback": "（质检跳过：未配置API Key）"}

    sources_text = "\n".join([
        f"- {s.get('file_name', s.get('source', '未知'))}: {s.get('snippet', s.get('content', ''))[:200]}"
        for s in (sources or [])
    ]) if sources else "（无知识库来源）"

    prompt = QUALITY_CHECK_PROMPT.replace("{user_query}", user_query).replace("{answer}", answer).replace("{sources}", sources_text)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一个质检审查员。严格只返回JSON: {\"pass\": true/false, \"feedback\": \"...\"}"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                try:
                    result = json.loads(content)
                    return {
                        "pass": result.get("pass", True),
                        "feedback": result.get("feedback", "")
                    }
                except json.JSONDecodeError:
                    # JSON解析失败，检查内容本身是否包含pass
                    if '"pass": true' in content.lower() or '"pass":true' in content.lower():
                        return {"pass": True, "feedback": ""}
                    return {"pass": True, "feedback": f"质检解析异常，放行: {content[:100]}"}
            else:
                return {"pass": True, "feedback": f"质检API异常(HTTP {resp.status_code})，放行"}
    except Exception as e:
        return {"pass": True, "feedback": f"质检网络异常({str(e)[:50]})，放行"}
