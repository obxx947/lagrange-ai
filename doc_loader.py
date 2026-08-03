# -*- coding: utf-8 -*-
"""
文档加载模块
-----------
程序启动时自动扫描 Windows 桌面「质料」文件夹，
将合规文档（txt/md/pdf）复制/加载至项目根目录 lagrange_docs 文件夹。
自动过滤 exe、压缩包、图片等非文本文件。
"""

import os
import shutil
from pathlib import Path
from typing import List

import config

# ==================== 允许的文档扩展名 ====================
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".html", ".htm"}

# ==================== 向量化允许的扩展名（HTML模拟器文件排除） ====================
VECTORIZE_EXTENSIONS = {".txt", ".md", ".pdf"}

# ==================== 被过滤的危险/非文本扩展名 ====================
BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
    ".bat", ".cmd", ".ps1", ".sh", ".msi",
}


def get_desktop_materials_path() -> Path:
    """获取桌面「质料」文件夹路径"""
    return Path(config.DESKTOP_MATERIALS_PATH)


def get_lagrange_docs_path() -> Path:
    """获取项目 lagrange_docs 文件夹路径"""
    docs_path = Path(config.LAGRANGE_DOCS_PATH)
    docs_path.mkdir(parents=True, exist_ok=True)
    return docs_path


def check_desktop_folder_exists() -> bool:
    """
    检查桌面「质料」文件夹是否存在
    不存在时打印提示但不阻断程序运行
    """
    path = get_desktop_materials_path()
    if not path.exists():
        print(f"[提示] 桌面「质料」文件夹不存在：{path}")
        print(f"       请确保桌面有名为「质料」的文件夹，放入游戏资料后可重启程序加载")
        return False
    if not path.is_dir():
        print(f"[提示] 桌面「质料」路径不是文件夹：{path}")
        return False
    return True


def is_allowed_file(file_path: Path) -> bool:
    """
    判断文件是否为合规文档
    
    - 文件扩展名在允许列表中
    - 文件扩展名不在阻止列表中
    - 文件可以正常读取
    """
    ext = file_path.suffix.lower()
    
    # HTML 文件允许（模拟器源码需要嵌入前端）
    if ext in ALLOWED_EXTENSIONS:
        # 确保文件可读
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                f.read(100)  # 尝试读取前100字符
            return True
        except Exception:
            return False
    
    return False


def is_vectorizable(file_path: Path) -> bool:
    """
    判断文件是否应参与向量化
    HTML 文件（模拟器源码）不参与向量检索
    """
    return file_path.suffix.lower() in VECTORIZE_EXTENSIONS


def sync_desktop_to_lagrange_docs() -> dict:
    """
    将桌面「质料」文件夹中的合规文档同步到 lagrange_docs
    
    同步规则：
    - 仅同步 txt/md/pdf/html 文件
    - 自动过滤 exe/压缩包/图片等非文本文件
    - 覆盖同名文件（以桌面源文件为准）
    
    Returns:
        {
            "total_found": 总共找到的文件数,
            "synced": 成功同步的文件数,
            "skipped": 跳过的文件数,
            "files": [同步的文件名列表],
            "skipped_files": [跳过的文件名列表]
        }
    """
    result = {
        "total_found": 0,
        "synced": 0,
        "skipped": 0,
        "files": [],
        "skipped_files": [],
    }
    
    desktop_path = get_desktop_materials_path()
    docs_path = get_lagrange_docs_path()
    
    if not desktop_path.exists():
        print(f"[文档加载] 桌面「质料」文件夹不存在，跳过同步")
        return result
    
    # 遍历桌面「质料」内所有文件
    for item in desktop_path.iterdir():
        if not item.is_file():
            continue
        
        result["total_found"] += 1
        
        if is_allowed_file(item):
            dest_path = docs_path / item.name
            try:
                shutil.copy2(str(item), str(dest_path))
                result["synced"] += 1
                result["files"].append(item.name)
                print(f"[文档加载] ✓ 已同步：{item.name}")
            except Exception as e:
                result["skipped"] += 1
                result["skipped_files"].append(f"{item.name} (错误: {e})")
                print(f"[文档加载] ✗ 同步失败：{item.name} - {e}")
        else:
            result["skipped"] += 1
            result["skipped_files"].append(item.name)
            print(f"[文档加载] - 已过滤非文本文件：{item.name}")
    
    print(f"[文档加载] 同步完成：共 {result['total_found']} 个文件，"
          f"同步 {result['synced']} 个，跳过 {result['skipped']} 个")
    return result


def get_vectorizable_files() -> List[Path]:
    """
    获取 lagrange_docs 中所有应参与向量化的文件列表
    
    排除：
    - HTML 模拟器文件（仅用于前端渲染）
    - 非文本格式文件
    """
    docs_path = get_lagrange_docs_path()
    if not docs_path.exists():
        return []
    
    vector_files = []
    for item in docs_path.rglob("*"):
        if item.is_file() and is_vectorizable(item):
            vector_files.append(item)
    
    return vector_files


def get_html_simulator_files() -> List[Path]:
    """
    获取 lagrange_docs 中的 HTML 模拟器文件
    这些文件不参与向量化，仅用于前端嵌入
    """
    docs_path = get_lagrange_docs_path()
    if not docs_path.exists():
        return []
    
    html_files = []
    for item in docs_path.iterdir():
        if item.is_file() and item.suffix.lower() in {".html", ".htm"}:
            html_files.append(item)
    
    return html_files


def load_text_file(file_path: Path) -> str:
    """
    读取文本文件内容，自动处理编码问题
    
    优先尝试 UTF-8，失败则尝试 GBK（Windows中文环境常见编码）
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="gbk") as f:
                return f.read()
        except Exception:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
