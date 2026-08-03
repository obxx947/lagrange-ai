# -*- coding: utf-8 -*-
"""
RAG 知识库服务模块（轻量版）
------------------------------
基于 TF-IDF + FAISS 实现本地向量存储与检索。
使用 jieba 中文分词 + scikit-learn TfidfVectorizer 生成文本向量，
无需下载大型深度学习模型（torch/sentence-transformers），
在 200MB 磁盘空间即可运行。

启动时自动将 lagrange_docs 内合规文档切片、向量化，构建持久化向量库。
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional

import config
from doc_loader import get_vectorizable_files, load_text_file, get_lagrange_docs_path

# ==================== TF-IDF 向量化器（全局单例） ====================

_vectorizer = None          # TfidfVectorizer 实例
_vectorizer_fitted = False  # 是否已拟合


def _jieba_tokenizer(text):
    """jieba 中文分词器（模块级函数，确保可被 pickle 序列化）"""
    import jieba
    words = jieba.cut(text)
    return [w for w in words if len(w.strip()) > 1]


def _get_vectorizer():
    """获取或创建 TfidfVectorizer 实例"""
    global _vectorizer
    if _vectorizer is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        _vectorizer = TfidfVectorizer(
            tokenizer=_jieba_tokenizer,
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
    return _vectorizer


# ==================== FAISS 索引路径 ====================

def _get_index_dir() -> Path:
    """获取 FAISS 索引存储目录"""
    index_dir = Path(config.CHROMA_DB_PATH)  # 复用原 chroma_db 路径
    index_dir.mkdir(parents=True, exist_ok=True)
    return index_dir


def _get_index_path() -> Path:
    return _get_index_dir() / "vectors.npy"


def _get_metadata_path() -> Path:
    return _get_index_dir() / "faiss_metadata.pkl"


def _get_vectorizer_path() -> Path:
    return _get_index_dir() / "tfidf_vectorizer.pkl"


# ==================== 文本分块 ====================

def split_text_into_chunks(text: str, source_file: str) -> List[dict]:
    """
    将长文本按字符数分割成块，使用简单重叠策略
    """
    chunks = []
    chunk_size = config.CHUNK_SIZE
    overlap = config.CHUNK_OVERLAP
    
    if len(text) <= chunk_size:
        chunks.append({"content": text, "source": source_file, "chunk_index": 0})
        return chunks
    
    start = 0
    index = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append({
            "content": text[start:end],
            "source": source_file,
            "chunk_index": index,
        })
        index += 1
        start += chunk_size - overlap
    
    return chunks


# ==================== 向量库构建/重建 ====================

def build_vector_index() -> dict:
    """
    构建/重建 TF-IDF + FAISS 向量索引
    
    流程：
    1. 扫描 lagrange_docs 中所有合规文本文件
    2. 对每个文件进行文本切片
    3. 使用 TF-IDF 向量化所有切片
    4. 存入 FAISS 索引并持久化到磁盘
    """
    global _vectorizer, _vectorizer_fitted
    
    vector_files = get_vectorizable_files()
    
    if not vector_files:
        print("[RAG] 未找到可向量化的文档，跳过索引构建")
        return {
            "status": "no_docs",
            "message": "lagrange_docs 中无可向量化的文档（需要txt/md/pdf文件）",
            "file_count": 0, "chunk_count": 0,
        }
    
    print(f"[RAG] 开始构建向量索引（TF-IDF + FAISS），共 {len(vector_files)} 个文件...")
    
    # 收集所有文本块
    all_chunks = []
    for file_path in vector_files:
        try:
            content = load_text_file(file_path)
            if not content or len(content.strip()) < 10:
                print(f"[RAG] 跳过空文件或内容过短：{file_path.name}")
                continue
            # 使用相对路径作为来源名（子文件夹显示完整路径）
            rel_path = file_path.relative_to(config.LAGRANGE_DOCS_PATH).as_posix()
            chunks = split_text_into_chunks(content, rel_path)
            all_chunks.extend(chunks)
            print(f"[RAG] ✓ {rel_path} → {len(chunks)} 个文本块")
        except Exception as e:
            print(f"[RAG] ✗ 处理失败：{file_path.name} - {e}")
    
    if not all_chunks:
        print("[RAG] 没有有效的文本块，跳过索引构建")
        return {
            "status": "no_chunks",
            "message": "所有文档处理后无有效文本块",
            "file_count": len(vector_files), "chunk_count": 0,
        }
    
    total_chunks = len(all_chunks)
    print(f"[RAG] 共计 {total_chunks} 个文本块，正在向量化...")
    
    # TF-IDF 向量化
    texts = [c["content"] for c in all_chunks]
    vectorizer = _get_vectorizer()
    embeddings_matrix = vectorizer.fit_transform(texts).toarray().astype(np.float32)
    _vectorizer_fitted = True
    
    # L2 归一化（使内积等价于余弦相似度）
    norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings_matrix = embeddings_matrix / norms
    
    # 保存向量矩阵（numpy格式）
    dim = embeddings_matrix.shape[1]
    np.save(str(_get_index_path()), embeddings_matrix)
    
    metadata = {"chunks": all_chunks, "chunk_count": total_chunks}
    with open(_get_metadata_path(), "wb") as f:
        pickle.dump(metadata, f)
    
    # 保存 TF-IDF 向量化器
    with open(_get_vectorizer_path(), "wb") as f:
        pickle.dump(vectorizer, f)
    
    result = {
        "status": "success",
        "message": f"向量索引构建完成，共 {len(vector_files)} 个文件、{total_chunks} 个文本块（TF-IDF 维度: {dim}）",
        "file_count": len(vector_files),
        "chunk_count": total_chunks,
    }
    print(f"[RAG] {result['message']}")
    return result


# ==================== 向量检索 ====================

def _load_index():
    """加载向量矩阵（numpy格式）、元数据和向量化器"""
    index_path = _get_index_path()
    metadata_path = _get_metadata_path()
    vectorizer_path = _get_vectorizer_path()
    
    if not index_path.exists() or not metadata_path.exists():
        return None, None, None
    
    # 加载numpy向量矩阵替代FAISS
    embeddings = np.load(str(index_path))
    
    with open(metadata_path, "rb") as f:
        metadata = pickle.load(f)
    
    vectorizer = None
    if vectorizer_path.exists():
        with open(vectorizer_path, "rb") as f:
            vectorizer = pickle.load(f)
    else:
        vectorizer = _get_vectorizer()
    
    return embeddings, metadata, vectorizer


def search_similar_documents(query: str, top_k: int = None) -> List[dict]:
    """
    在向量库中检索与查询最相关的文档块
    
    Args:
        query: 用户查询文本
        top_k: 返回最相关的K个结果
    
    Returns:
        [{"content": "...", "source": "...", "chunk_index": 0, "score": 0.95}, ...]
    """
    if top_k is None:
        top_k = config.RETRIEVAL_TOP_K
    
    try:
        embeddings, metadata, vectorizer = _load_index()
        if embeddings is None or metadata is None:
            return []
        
        chunks = metadata["chunks"]
        if not chunks:
            return []
        
        # 使用 TF-IDF 向量化查询
        if vectorizer is None:
            vectorizer = _get_vectorizer()
        
        try:
            query_vec = vectorizer.transform([query]).toarray().astype(np.float32)
        except Exception:
            # 如果向量化器未拟合（没有训练数据），返回空
            return []
        
        # L2 归一化
        norms = np.linalg.norm(query_vec, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        query_vec = query_vec / norms
        
        # numpy 内积检索（替代FAISS）
        chunks = metadata["chunks"]
        scores = np.dot(embeddings, query_vec.T).flatten()  # 余弦相似度
        k = min(top_k, len(chunks))
        top_indices = np.argsort(scores)[-k:][::-1]  # 降序取top-k
        
        # 解析结果
        documents = []
        for idx in top_indices:
            score = float(scores[idx])
            if 0 <= idx < len(chunks):
                chunk = chunks[idx]
                documents.append({
                    "content": chunk["content"],
                    "source": chunk["source"],
                    "chunk_index": chunk["chunk_index"],
                    "score": round(max(0.0, min(1.0, score)), 4),
                })
        
        return documents
        
    except Exception as e:
        print(f"[RAG] 检索失败：{e}")
        return []


def format_rag_context(documents: List[dict]) -> str:
    """
    将检索到的文档块格式化为注入上下文的文本
    格式：【资料来源：文件名】\n内容...\n---
    """
    if not documents:
        return "暂无相关拉格朗日实战资料。"
    
    context_parts = []
    for doc in documents:
        source = doc.get("source", "未知文件")
        content = doc.get("content", "")
        context_parts.append(f"【资料来源：{source}】\n{content}\n---")
    
    return "\n".join(context_parts)


def is_index_built() -> bool:
    """检查向量索引是否已构建（numpy格式）"""
    return _get_index_path().exists() and _get_metadata_path().exists()
