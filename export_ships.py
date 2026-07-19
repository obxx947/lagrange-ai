# -*- coding: utf-8 -*-
"""
舰船数据导出工具
---------------
将169艘舰船数据库导出为多种格式：
- CSV（Excel可打开）
- JSON（美化格式）
- 纯文本摘要

用法：python export_ships.py [csv|json|txt|all]
"""

import json
import csv
import sys
from pathlib import Path
from datetime import datetime

# 获取 lagrange_docs 路径
DOCS_PATH = Path(__file__).resolve().parent / "lagrange_docs"
OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def load_ships():
    json_path = DOCS_PATH / "ship_database.json"
    if not json_path.exists():
        print(f"❌ 舰船数据库未找到: {json_path}")
        print("   请先运行: node parse_ships.js")
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def export_csv(ships):
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"ships_{datetime.now().strftime('%Y%m%d')}.csv"
    
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID", "名称", "变体", "类型", "大小", "位置",
            "HP", "物理装甲", "能量抗性%", "指挥值", "服役上限",
            "巡航速度", "曲率速度",
            "对舰评级", "防空评级", "攻城评级", "生存评级", "战略评级",
            "是否航母", "战机槽位", "护航艇槽位"
        ])
        
        for s in ships:
            r = s.get("ratings", {})
            ac = s.get("aircraftSlots", {})
            writer.writerow([
                s.get("id", ""), s.get("name", ""), s.get("variant", ""),
                s.get("type", ""), s.get("size", ""), s.get("position", ""),
                s.get("hp", 0), s.get("physicalArmor", 0), s.get("energyArmor", 0),
                s.get("commandValue", 0), s.get("serviceLimit", 0),
                s.get("speed", {}).get("cruise", 0), s.get("speed", {}).get("warp", 0),
                r.get("antiShip", ""), r.get("antiAir", ""), r.get("siege", ""),
                r.get("survival", ""), r.get("strategy", ""),
                "是" if s.get("isCarrier") else "否",
                ac.get("fighter", 0), ac.get("corvette", 0)
            ])
    
    print(f"✅ CSV已导出: {path} ({len(ships)}艘)")


def export_json(ships):
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"ships_{datetime.now().strftime('%Y%m%d')}.json"
    
    # 精简版（只保留关键字段）
    simple = []
    for s in ships:
        simple.append({
            "id": s.get("id"), "name": s.get("name"), "variant": s.get("variant"),
            "type": s.get("type"), "hp": s.get("hp"),
            "armor": s.get("physicalArmor"), "shield": s.get("energyArmor"),
            "cv": s.get("commandValue"), "ratings": s.get("ratings"),
            "speed": s.get("speed", {}).get("cruise"),
        })
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(simple, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON已导出: {path} ({len(ships)}艘)")


def export_txt(ships):
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"ships_{datetime.now().strftime('%Y%m%d')}.txt"
    
    types = {}
    for s in ships:
        t = s.get("type", "other")
        types.setdefault(t, []).append(s)
    
    type_names = {
        "battleship": "战列舰", "battlecruiser": "战列巡洋舰",
        "aircraftcarrier": "航空母舰", "support": "支援舰",
        "cruiser": "巡洋舰", "destroyer": "驱逐舰", "frigate": "护卫舰",
        "fighter": "战机", "corvette": "护航艇"
    }
    
    lines = [f"无尽的拉格朗日 — 舰船数据库 (共{len(ships)}艘)", 
             f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 60]
    
    for stype, type_ships in sorted(types.items()):
        type_name = type_names.get(stype, stype)
        lines.append(f"\n## {type_name} ({len(type_ships)}艘)")
        lines.append("-" * 40)
        
        for s in sorted(type_ships, key=lambda x: x.get("hp", 0), reverse=True):
            name = f"{s.get('name','')}{s.get('variant','')}"
            hp = s.get("hp", 0)
            r = s.get("ratings", {})
            ratings_str = " | ".join([f"{k}={v}" for k, v in r.items()])
            lines.append(
                f"  {name:<20s} HP:{hp:>8,}  "
                f"装甲:{s.get('physicalArmor',0):>4} 护盾:{s.get('energyArmor',0):>3}%  "
                f"CV:{s.get('commandValue',0):>3}  [{ratings_str}]"
            )
    
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ TXT已导出: {path} ({len(ships)}艘)")


if __name__ == "__main__":
    ships = load_ships()
    if not ships:
        sys.exit(1)
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print(f"导出169艘舰船数据 (模式: {mode})")
    print("-" * 40)
    
    if mode in ("csv", "all"):
        export_csv(ships)
    if mode in ("json", "all"):
        export_json(ships)
    if mode in ("txt", "all"):
        export_txt(ships)
    
    print("\n✅ 导出完成！文件位于 exports/ 目录")
