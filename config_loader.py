# -*- coding: utf-8 -*-
"""
配置加载器
---------
验证并加载所有格式的配置文件：.env / .yaml / .toml / .ini / .cfg / .properties / .xml
确保每种配置格式都可以被程序实际读取使用
"""

import os
import json
import configparser
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent


def load_dotenv() -> Dict[str, str]:
    """加载 .env 文件"""
    env_path = BASE_DIR / ".env"
    result = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    result[key.strip()] = val.strip()
    return result


def load_yaml_config() -> Dict:
    """加载 YAML 配置文件（需要 pyyaml，失败则返回空）"""
    try:
        import yaml
        yaml_path = BASE_DIR / "config.yaml"
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except ImportError:
        pass
    return {}


def load_toml_config() -> Dict:
    """加载 TOML 配置文件（Python 3.11+内置，失败则返回空）"""
    try:
        if hasattr(__import__('tomllib', fromlist=['load']), 'load'):
            import tomllib
            toml_path = BASE_DIR / "config.toml"
            if toml_path.exists():
                with open(toml_path, "rb") as f:
                    return tomllib.load(f)
    except (ImportError, Exception):
        # 降级使用第三方 toml 库
        try:
            import toml
            toml_path = BASE_DIR / "config.toml"
            if toml_path.exists():
                with open(toml_path, "r", encoding="utf-8") as f:
                    return toml.load(f)
        except ImportError:
            pass
    return {}


def load_ini_config() -> Dict:
    """加载 INI/CFG 配置文件（兼容有/无节头的格式）"""
    result = {}
    for fname in ["config.ini", "settings.cfg", "setup.cfg"]:
        path = BASE_DIR / fname
        if not path.exists():
            continue
        
        content = path.read_text(encoding="utf-8")
        
        # 检查是否有节头（[Section]）
        if '[' in content and ']' in content:
            parser = configparser.ConfigParser()
            parser.read_string(content)
            for section in parser.sections():
                result[section] = dict(parser.items(section))
        else:
            # 无节头的CFG格式：key value
            section = {}
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith(';'):
                    parts = line.split(None, 1)  # 用空白分割
                    if len(parts) == 2:
                        section[parts[0]] = parts[1]
            if section:
                result[Path(fname).stem] = section
    return result


def load_properties_config() -> Dict:
    """加载 Java Properties 配置文件"""
    result = {}
    path = BASE_DIR / "lagrange.properties"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    # 支持点号嵌套
                    keys = key.strip().split(".")
                    d = result
                    for k in keys[:-1]:
                        d = d.setdefault(k, {})
                    d[keys[-1]] = val.strip()
    return result


def load_xml_config() -> Dict:
    """加载 XML 配置文件"""
    result = {"ships": []}
    path = BASE_DIR / "ships.xml"
    if path.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(str(path))
            root = tree.getroot()
            result["game"] = root.get("game", "")
            result["count"] = root.get("count", "0")
            # 提取分类
            cats = root.find("categories")
            if cats is not None:
                result["categories"] = []
                for cat in cats.findall("category"):
                    result["categories"].append({
                        "id": cat.get("id", ""),
                        "name": cat.get("name", ""),
                    })
            # 提取样例舰船
            samples = root.find("sampleShips")
            if samples is not None:
                for ship in samples.findall("ship"):
                    result["ships"].append({
                        "id": ship.get("id", ""),
                        "name": ship.findtext("name", ""),
                        "type": ship.findtext("type", ""),
                        "hp": int(ship.findtext("hp", "0")),
                    })
        except Exception:
            pass
    return result


def load_json_config() -> Dict:
    """加载 JSON 配置文件"""
    result = {}
    for fname in ["package.json"]:
        path = BASE_DIR / fname
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    result[fname] = json.load(f)
            except Exception:
                pass
    return result


def validate_all_configs() -> Dict[str, bool]:
    """验证所有配置文件是否可加载"""
    results = {}
    
    # .env
    env = load_dotenv()
    results[".env"] = len(env) > 0
    
    # YAML
    yaml_cfg = load_yaml_config()
    results["config.yaml"] = len(yaml_cfg) > 0
    
    # TOML
    toml_cfg = load_toml_config()
    results["config.toml"] = len(toml_cfg) > 0
    
    # INI
    ini_cfg = load_ini_config()
    results["config.ini"] = len(ini_cfg) > 0
    
    # Properties
    props = load_properties_config()
    results["lagrange.properties"] = len(props) > 0
    
    # XML
    xml_cfg = load_xml_config()
    results["ships.xml"] = len(xml_cfg.get("categories", [])) > 0 or len(xml_cfg.get("ships", [])) > 0
    
    # JSON
    json_cfg = load_json_config()
    results["package.json"] = len(json_cfg) > 0
    
    return results


def get_merged_config() -> Dict[str, Any]:
    """合并所有配置源到一个统一字典"""
    merged = {}
    
    # 优先级：.env > TOML > YAML > INI > Properties
    merged.update(load_properties_config())
    merged.update(load_ini_config())
    merged.update(load_yaml_config())
    merged.update(load_toml_config())
    
    # .env 覆盖（最高优先级）
    env = load_dotenv()
    merged["env"] = env
    
    return merged


# ==================== 测试 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("  配置文件验证器")
    print("=" * 50)
    
    results = validate_all_configs()
    for fname, ok in results.items():
        status = "✅ 可加载" if ok else "❌ 不可用"
        print(f"  {status}  {fname}")
    
    print("\n合并配置:")
    merged = get_merged_config()
    print(f"  配置项总数: {sum(1 for _ in _flatten(merged))}")
    
    # 显示部分配置
    env = load_dotenv()
    print(f"\n  .env 配置项: {len(env)}")
    for k in list(env.keys())[:5]:
        val = env[k]
        if "KEY" in k or "SECRET" in k or "PASSWORD" in k:
            val = val[:4] + "***"
        print(f"    {k} = {val}")


def _flatten(d, parent_key=''):
    """展平嵌套字典"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten(v, new_key))
        else:
            items.append((new_key, v))
    return items
