# -*- coding: utf-8 -*-
"""
Agent 工具系统
--------------
定义 Agent 可调用的所有工具（DeepSeek function calling 格式）。
每个工具有 schema 定义 + 执行函数。
"""

import json
import os
from typing import Optional
from pathlib import Path

# ==================== 工具 Schema 定义 ====================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "搜索向量知识库。知识库包含：舰船数据、战斗机制文档、真人讲解范例。当用户询问游戏机制、舰船参数、战术问题且互联网未找到答案时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询，使用中文关键词"},
                    "category": {
                        "type": "string",
                        "enum": ["舰船数据", "战斗机制", "讲解范例", "全部"],
                        "description": "按类别过滤，不指定则搜索全部"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "battle_simulate",
            "description": "调用战斗模拟器测试舰队配置。当用户询问舰队配置、配队方案、战斗结果分析时必须调用此工具。返回多环境下的DPS、战损、胜率等实测数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "fleet_config": {
                        "type": "object",
                        "description": "舰队配置JSON，包含ally_ships和enemy_ships数组，每艘船有id和count"
                    },
                    "scenario": {
                        "type": "string",
                        "enum": ["escort", "bomb", "direct"],
                        "description": "战斗场景：escort=护航战, bomb=轰炸战, direct=正面对抗"
                    }
                },
                "required": ["fleet_config", "scenario"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ship_data",
            "description": "精确查询某艘舰船的完整参数（HP、护甲、武器、模块等）。当用户问及具体舰船时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ship_name": {"type": "string", "description": "舰船名称或ID，如'CAS066级'、'阋神重炮'、'爱奥'"}
                },
                "required": ["ship_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_simulator_state",
            "description": "读取当前模拟器状态（已配置的舰队、最近的战斗结果）。当用户的问题涉及'当前'、'这场'、'刚才'等上下文时必须调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "state_type": {
                        "type": "string",
                        "enum": ["fleet", "battle_result", "all"],
                        "description": "读取的状态类型"
                    }
                },
                "required": ["state_type"]
            }
        }
    }
]


# ==================== 工具执行 ====================

def execute_tool(tool_name: str, arguments: dict, user_id: int = 0) -> str:
    """执行工具并返回结果字符串"""
    if tool_name == "search_knowledge_base":
        return _search_kb(arguments.get("query", ""), arguments.get("category", "全部"))
    elif tool_name == "battle_simulate":
        return _battle_sim(arguments.get("fleet_config", {}), arguments.get("scenario", "escort"))
    elif tool_name == "get_ship_data":
        return _get_ship(arguments.get("ship_name", ""))
    elif tool_name == "read_simulator_state":
        return _read_state(arguments.get("state_type", "all"))
    else:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)


def _search_kb(query: str, category: str = "全部") -> str:
    """搜索向量知识库"""
    try:
        from rag_service import search_similar_documents
        docs = search_similar_documents(query, top_k=5)
        if not docs:
            return "未在知识库中找到相关内容。"
        results = []
        for d in docs:
            results.append({
                "source": d.get("source", "未知"),
                "score": round(d.get("score", 0), 3),
                "content": d.get("content", "")[:500]
            })
        return json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"知识库检索失败: {str(e)}"}, ensure_ascii=False)


def _battle_sim(fleet_config: dict, scenario: str = "escort") -> str:
    """战斗模拟器 — 独立计算，不依赖外部API"""
    try:
        ship_db_path = Path(__file__).resolve().parent / "lagrange_docs" / "ship_database.json"
        if not ship_db_path.exists():
            return json.dumps({"error": "舰船数据库未找到"}, ensure_ascii=False)

        ships_data = json.loads(ship_db_path.read_text(encoding="utf-8"))
        # Build lookup
        ship_db = {}
        for ship in (ships_data if isinstance(ships_data, list) else ships_data.values()):
            sid = ship.get("id", "")
            if sid:
                ship_db[sid] = ship

        ally_cfg = fleet_config.get("ally_ships", [])
        enemy_cfg = fleet_config.get("enemy_ships", [])
        if not ally_cfg or not enemy_cfg:
            return json.dumps({"error": "请提供我方和敌方舰船配置"}, ensure_ascii=False)

        # Simplified combat calculation
        TUNE = 1.3

        def calc_fleet_power(ships_cfg, side_name):
            results = []
            total_dpm = 0
            total_hp = 0
            total_armor = 0
            total_energy_shield = 0

            for cfg in ships_cfg:
                sid = cfg.get("id", "")
                count = cfg.get("count", 1)
                ship = ship_db.get(sid)
                if not ship:
                    continue

                hp = ship.get("hp", 50000)
                phys_armor = ship.get("physicalArmor", 0)
                energy_armor = ship.get("energyArmor", 5)

                # Calculate weapon DPM
                ship_dpm = 0
                weapon_details = []
                for mod in ship.get("modules", {}).values():
                    if mod.get("type") == "weapon":
                        for w in mod.get("weapons", []):
                            base_dmg = w.get("singleDmg", 100)
                            ammo = w.get("ammo", 1)
                            attacks = w.get("attacks", 1)
                            cooldown = max(w.get("cooldown", 8), 1)
                            lock_time = w.get("lockTime", 5)
                            dmg_type = w.get("dmgType", "physical")
                            cycle_time = max(cooldown, lock_time)

                            # Raw DPM per weapon slot
                            shots_per_min = 60 / cycle_time
                            raw_dpm = base_dmg * ammo * attacks * shots_per_min
                            tuned_dpm = raw_dpm * TUNE
                            ship_dpm += tuned_dpm

                            weapon_details.append({
                                "name": w.get("name", "?"),
                                "type": dmg_type,
                                "single_dmg": base_dmg,
                                "ammo": ammo,
                                "attacks": attacks,
                                "cooldown": cooldown,
                                "lock_time": lock_time,
                                "cycle": round(cycle_time, 1),
                                "raw_dpm": round(raw_dpm),
                                "tuned_dpm": round(tuned_dpm),
                            })

                total_hp += hp * count
                total_armor += phys_armor * count
                total_energy_shield += energy_armor * count
                total_dpm += ship_dpm * count

                results.append({
                    "id": sid,
                    "name": ship.get("name", sid),
                    "count": count,
                    "hp": hp,
                    "phys_armor": phys_armor,
                    "energy_shield": energy_armor,
                    "ship_dpm": round(ship_dpm),
                    "weapons": weapon_details[:3],  # top 3 weapons
                })

            avg_armor = total_armor / max(len(results), 1)
            return {
                "ships": results,
                "total_hp": total_hp,
                "total_dpm": round(total_dpm),
                "avg_phys_armor": round(avg_armor, 1),
                "ship_count": sum(s.get("count", 1) for s in results),
            }

        ally = calc_fleet_power(ally_cfg, "我方")
        enemy = calc_fleet_power(enemy_cfg, "敌方")

        # Simulate engagement
        ally_effective_dpm = ally["total_dpm"]
        enemy_effective_dpm = enemy["total_dpm"]

        # Physical damage reduction from armor
        ally_armor = ally["avg_phys_armor"]
        enemy_armor = enemy["avg_phys_armor"]
        # Approximate: armor reduces DPM by armor*shots_per_min
        ally_armor_reduction = enemy_armor * enemy["ship_count"] * 10
        enemy_armor_reduction = ally_armor * ally["ship_count"] * 10

        ally_net_dpm = max(0, ally_effective_dpm - enemy_armor_reduction)
        enemy_net_dpm = max(0, enemy_effective_dpm - ally_armor_reduction)

        if ally_net_dpm <= 0 and enemy_net_dpm <= 0:
            winner = "平局（双方不破防）"
            duration = "∞"
        elif ally_net_dpm <= 0:
            winner = "敌方"
            duration = "N/A（我方不破防）"
        elif enemy_net_dpm <= 0:
            winner = "我方"
            duration = "N/A（敌方不破防）"
        else:
            ally_ttk = ally["total_hp"] / enemy_net_dpm * 60
            enemy_ttk = ally["total_hp"] / ally_net_dpm * 60
            if ally_ttk < enemy_ttk:
                winner = "我方"
                duration = f"{ally_ttk:.0f}秒"
            else:
                winner = "敌方"
                duration = f"{enemy_ttk:.0f}秒"

        return json.dumps({
            "scenario": scenario,
            "ally": {
                "ship_count": ally["ship_count"],
                "total_hp": ally["total_hp"],
                "total_dpm": ally["total_dpm"],
                "avg_armor": ally["avg_phys_armor"],
                "net_dpm_vs_enemy": round(ally_net_dpm),
            },
            "enemy": {
                "ship_count": enemy["ship_count"],
                "total_hp": enemy["total_hp"],
                "total_dpm": enemy["total_dpm"],
                "avg_armor": enemy["avg_phys_armor"],
                "net_dpm_vs_ally": round(enemy_net_dpm),
            },
            "prediction": {
                "winner": winner,
                "duration": duration,
                "ally_dpm_advantage": round(ally["total_dpm"] - enemy["total_dpm"]),
            },
            "note": "基于战斗机制.txt公式的简化推演。实际战斗受拦截、暴击、系统损毁、维修、护航等因素影响。"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({"error": f"战斗模拟失败: {str(e)}\n{traceback.format_exc()[:300]}"}, ensure_ascii=False)


def _get_ship(ship_name: str) -> str:
    """查询舰船数据"""
    try:
        ship_db_path = Path(__file__).resolve().parent / "lagrange_docs" / "ship_database.json"
        if not ship_db_path.exists():
            return json.dumps({"error": "舰船数据库未找到"}, ensure_ascii=False)

        ships = json.loads(ship_db_path.read_text(encoding="utf-8"))
        matches = []
        # Handle both list and dict formats
        items = ships if isinstance(ships, list) else ships.items()
        for item in items:
            if isinstance(item, tuple):
                sid, ship = item
            else:
                ship = item
                sid = ship.get("id", "")
            name = ship.get("name", "")
            if ship_name.lower() in name.lower() or ship_name.lower() in sid.lower():
                matches.append({
                    "id": sid,
                    "name": name,
                    "type": ship.get("type", ""),
                    "hp": ship.get("hp", 0),
                    "physicalArmor": ship.get("physicalArmor", 0),
                    "energyArmor": ship.get("energyArmor", 5),
                    "position": ship.get("position", ""),
                    "commandValue": ship.get("commandValue", 0),
                    "ratings": ship.get("ratings", {}),
                    "speed": ship.get("speed", {}),
                    "module_count": len(ship.get("modules", {})),
                })

        if not matches:
            # 模糊搜索
            from rag_service import search_similar_documents
            docs = search_similar_documents(ship_name, top_k=3)
            return json.dumps({
                "exact_match": False,
                "message": f"未找到精确匹配'{ship_name}'的舰船，以下是相关知识库内容",
                "related": [{"source": d.get("source",""), "content": d.get("content","")[:300]} for d in docs]
            }, ensure_ascii=False, indent=2)

        return json.dumps({"exact_match": True, "count": len(matches), "ships": matches}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"舰船查询失败: {str(e)}"}, ensure_ascii=False)


def _read_state(state_type: str = "all") -> str:
    """读取模拟器状态（占位，实际状态由前端传入）"""
    return json.dumps({
        "message": "模拟器状态读取功能已就绪。请在对话中附带当前舰队配置JSON或战斗结果数据，Agent将基于实际数据进行分析。",
        "state_type": state_type
    }, ensure_ascii=False)
