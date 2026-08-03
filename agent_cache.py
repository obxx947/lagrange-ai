# -*- coding: utf-8 -*-
"""
缓存系统 + 联网搜索模块
-----------------------
- RAG 查询缓存：相同/相似查询直接命中缓存，统计命中率
- 联网搜索：Tavily API（如配置了Key），否则返回空结果
"""

import hashlib
import json
import time
from collections import OrderedDict
from typing import Optional

import httpx

# ==================== 缓存系统 ====================

class QueryCache:
    """简单LRU缓存：key=查询文本hash，value=检索结果"""

    def __init__(self, max_size: int = 200):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def _key(self, query: str, category: str = "") -> str:
        return hashlib.md5(f"{category}|{query}".encode()).hexdigest()

    def get(self, query: str, category: str = ""):
        key = self._key(query, category)
        if key in self._cache:
            self._hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, query: str, category: str, result):
        key = self._key(query, category)
        self._cache[key] = result
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def hit_rate(self) -> dict:
        total = self._hits + self._misses
        rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": round(rate, 1),
        }

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# 全局缓存实例
rag_cache = QueryCache(max_size=300)


def cached_search(query: str, category: str = "全部", top_k: int = 5, cache: QueryCache = None):
    """
    带缓存的RAG检索。返回 (结果列表, 是否命中缓存)
    """
    cache = cache or rag_cache
    cached = cache.get(query, category)
    if cached is not None:
        return cached, True

    from rag_service import search_similar_documents
    docs = search_similar_documents(query, top_k=top_k)
    # 缓存结果（限制content长度防止缓存过大）
    slim = [dict(d, content=d["content"][:500]) for d in docs]
    cache.put(query, category, slim)
    return slim, False


# ==================== 联网搜索 ====================

def web_search(query: str, api_key: str = "", api_url: str = "https://api.tavily.com") -> dict:
    """
    联网搜索。
    优先使用 Tavily（配置了Key时）；未配置Key时自动降级为 DuckDuckGo 免费搜索。
    返回: {"results": [...], "used": bool, "engine": "tavily"/"duckduckgo"/"none", "error": str?}
    """
    if api_key:
        return _tavily_search(query, api_key, api_url)
    # 无Key → Bing 免费搜索（任何情况下都能联网）
    return _bing_search(query)


def _tavily_search(query: str, api_key: str, api_url: str) -> dict:
    """Tavily 搜索"""
    try:
        resp = httpx.post(
            f"{api_url}/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": 5,
                "search_depth": "basic",
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for r in data.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],
                    "published_date": r.get("published_date", ""),
                })
            return {"used": True, "engine": "tavily", "results": results}
        # Tavily失败 → 降级Bing
        return _bing_search(query)
    except Exception as e:
        return _bing_search(query)


def _bing_search(query: str) -> dict:
    """Bing 免费搜索（国内可访问，无需API Key）"""
    import html as html_mod
    import re
    from urllib.parse import quote

    try:
        url = f"https://cn.bing.com/search?q={quote(query)}"
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=15.0,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return {"used": True, "engine": "bing", "results": [], "error": f"Bing HTTP {resp.status_code}"}

        page = resp.text
        results = []
        # 按 b_algo 块拆分解析
        blocks = re.split(r'<li class="b_algo"', page)[1:]
        for blk in blocks[:6]:
            href_m = re.search(r'href="(https?://(?!r\.bing\.com)[^"]+)"', blk)
            title_m = re.search(r'<h2[^>]*>\s*<a[^>]*>(.*?)</a>', blk, re.S)
            snip_m = re.search(r'<p[^>]*>(.*?)</p>', blk, re.S)
            if not href_m:
                continue
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
            snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip() if snip_m else ""
            results.append({
                "title": html_mod.unescape(title),
                "url": html_mod.unescape(href_m.group(1)),
                "content": html_mod.unescape(snippet)[:500],
                "published_date": "",
            })

        return {"used": True, "engine": "bing", "results": results}
    except Exception as e:
        return {"used": True, "engine": "bing", "results": [], "error": str(e)}


def _duckduckgo_search(query: str) -> dict:
    """DuckDuckGo HTML 免费搜索（备选，国内通常不可达）"""
    import html as html_mod
    import re
    from urllib.parse import quote

    try:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=15.0,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return {"used": True, "engine": "duckduckgo", "results": [], "error": f"DuckDuckGo HTTP {resp.status_code}"}

        page = resp.text
        results = []
        blocks = re.findall(
            r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a class="result__snippet"[^>]*>(.*?)</a>',
            page, re.S
        )
        for href, title_html, snippet_html in blocks[:6]:
            title = re.sub(r"<[^>]+>", "", title_html)
            snippet = re.sub(r"<[^>]+>", "", snippet_html)
            results.append({
                "title": html_mod.unescape(title).strip(),
                "url": html_mod.unescape(href).strip(),
                "content": html_mod.unescape(snippet).strip()[:500],
                "published_date": "",
            })
        return {"used": True, "engine": "duckduckgo", "results": results}
    except Exception as e:
        return {"used": True, "engine": "duckduckgo", "results": [], "error": str(e)}


def get_tavily_key() -> str:
    """从本地配置获取Tavily Key"""
    try:
        from user_config import get_local_config
        cfg = get_local_config()
        return cfg.get("web_search_api_key", "") or ""
    except Exception:
        return ""
