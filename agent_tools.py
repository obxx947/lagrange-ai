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
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "当用户需求不明确、需要澄清时（如配队偏好、资源限制、目标场景、可选方案选择等），向用户提问。支持单选/多选/自由输入。提问后对话会暂停等待用户回答，用户回答后继续。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要向用户提出的问题，尽量具体"},
                    "options": {"type": "array", "items": {"type": "string"}, "description": "选项列表，可空（空则纯自由输入）"},
                    "type": {"type": "string", "enum": ["single", "multiple", "free"], "description": "single=单选 multiple=多选 free=自由输入（不提供选项时用free）"},
                    "required": {"type": "boolean", "description": "是否必答，默认true"}
                },
                "required": ["question"]
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

        # Simplified combat calculation（基于战斗机制.txt公式）
        TUNE = 1.3          # 调校系数
        CRIT_RATE = 0.15    # 基础暴击率
        CRIT_MULT = 1.5     # 基础暴击伤害

        def weapon_cycle(w):
            """一轮攻击时间 = max(冷却, 锁定) + 攻击持续时间（锁定与冷却同时进行，文档公式）"""
            cd = max(w.get("cooldown", 8) or 1, 1)
            lock = w.get("lockTime", 5) or 0
            atk_dur = w.get("atkDuration", 0) or 0
            return max(cd, lock) + atk_dur

        def weapon_hit(w):
            """平均命中率 = 基础命中区间均值 × (1 + 命中加成 - 闪避)"""
            tgts = w.get("targets") or []
            if tgts:
                hits = [(t.get("hitMin", 50), t.get("hitMax", 70)) for t in tgts if isinstance(t, dict)]
                if hits:
                    return sum((a + b) / 2 for a, b in hits) / len(hits) / 100.0
            return 0.8

        def calc_fleet_power(ships_cfg, side_name):
            """汇总舰队：HP、护甲/护盾加权平均、逐武器基准DPM（未减抗，含命中/暴击期望）"""
            results = []
            total_hp = 0
            total_armor = 0
            total_shield = 0
            ship_count = 0
            weapon_dpms = []  # [{type, per_shot_tuned, shots, rate, hit, crit}]

            for cfg in ships_cfg:
                sid = cfg.get("id", "")
                count = cfg.get("count", 1)
                ship = ship_db.get(sid)
                if not ship:
                    continue

                hp = ship.get("hp", 50000)
                phys_armor = ship.get("physicalArmor", 0)
                energy_armor = ship.get("energyArmor", 5)

                ship_dpm = 0
                weapon_details = []
                for mod in ship.get("modules", {}).values():
                    if mod.get("type") == "weapon":
                        for w in mod.get("weapons", []):
                            base_dmg = w.get("singleDmg", 100)
                            ammo = w.get("ammo", 1)
                            attacks = w.get("attacks", 1)
                            dmg_type = w.get("dmgType", "physical")
                            cycle = weapon_cycle(w)
                            hit = weapon_hit(w)
                            crit_mult = (1 + CRIT_RATE * (CRIT_MULT - 1)) if w.get("crit") else 1.0
                            rate = 60 / cycle
                            shots = ammo * attacks
                            per_shot_tuned = base_dmg * TUNE  # 单发 × 调校
                            # 基准DPM = 单发×调校 × 弹数 × 60/周期 × 命中 × 暴击期望（未减目标抗性）
                            dpm = per_shot_tuned * shots * rate * hit * crit_mult
                            ship_dpm += dpm
                            weapon_dpms.append({
                                "type": dmg_type,
                                "per_shot_tuned": per_shot_tuned,
                                "shots": shots,
                                "rate": rate,
                                "hit": hit,
                                "crit": crit_mult,
                                "count": count,  # 该舰船数量（多艘叠加）
                            })
                            weapon_details.append({
                                "name": w.get("name", "?"),
                                "type": dmg_type,
                                "single_dmg": base_dmg,
                                "ammo": ammo,
                                "attacks": attacks,
                                "cooldown": w.get("cooldown", 8),
                                "lock_time": w.get("lockTime", 5),
                                "atk_duration": w.get("atkDuration", 0),
                                "cycle": round(cycle, 1),
                                "avg_hit": round(hit * 100, 1),
                                "dpm": round(dpm),
                            })

                total_hp += hp * count
                total_armor += phys_armor * count
                total_shield += energy_armor * count
                ship_count += count

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

            return {
                "ships": results,
                "total_hp": total_hp,
                "avg_phys_armor": total_armor / max(ship_count, 1),
                "avg_energy_shield": total_shield / max(ship_count, 1),
                "ship_count": ship_count,
                "weapon_dpms": weapon_dpms,
            }

        def net_dpm(weapon_dpms, armor, shield):
            """
            扣除目标抗性后的净DPM（战斗机制.txt公式）：
            - 能量单发 = 基础×(1+调校) × (1 - 目标护盾%)，护盾≥100%免疫
            - 物理单发 = 基础×(1+调校) - 目标护甲，不破防时保底 = 基础×10%×调校
            """
            total = 0.0
            for w in weapon_dpms:
                if w["type"] == "energy":
                    if shield >= 100:
                        per = 0.0
                    else:
                        per = w["per_shot_tuned"] * (1 - shield / 100.0)
                else:
                    per = max(w["per_shot_tuned"] - armor, w["per_shot_tuned"] * 0.1)
                total += per * w["shots"] * w["rate"] * w["hit"] * w["crit"] * w["count"]
            return total

        ally = calc_fleet_power(ally_cfg, "我方")
        enemy = calc_fleet_power(enemy_cfg, "敌方")

        # 我方输出吃敌方抗性，敌方输出吃我方抗性
        ally_net_dpm = net_dpm(ally["weapon_dpms"], enemy["avg_phys_armor"], enemy["avg_energy_shield"])
        enemy_net_dpm = net_dpm(enemy["weapon_dpms"], ally["avg_phys_armor"], ally["avg_energy_shield"])

        # 分伤机制：可被攻击的舰船数 = 总舰船数/2.5 取整（文档公式）
        ally_split = max(1, int(enemy["ship_count"] / 2.5))
        enemy_split = max(1, int(ally["ship_count"] / 2.5))

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
            ally_ttk = ally["total_hp"] / enemy_net_dpm * 60  # 我方存活时间
            enemy_ttk = enemy["total_hp"] / ally_net_dpm * 60  # 敌方存活时间（修复：原为ally hp）
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
                "total_dpm": round(net_dpm(ally["weapon_dpms"], 0, 0)),
                "avg_phys_armor": round(ally["avg_phys_armor"], 1),
                "avg_energy_shield": round(ally["avg_energy_shield"], 1),
                "net_dpm_vs_enemy": round(ally_net_dpm),
            },
            "enemy": {
                "ship_count": enemy["ship_count"],
                "total_hp": enemy["total_hp"],
                "total_dpm": round(net_dpm(enemy["weapon_dpms"], 0, 0)),
                "avg_phys_armor": round(enemy["avg_phys_armor"], 1),
                "avg_energy_shield": round(enemy["avg_energy_shield"], 1),
                "net_dpm_vs_ally": round(enemy_net_dpm),
            },
            "split_mechanism": {
                "ally_attackable_targets": ally_split,
                "enemy_attackable_targets": enemy_split,
                "formula": "可攻击舰船数 = 总舰船数 ÷ 2.5 取整（分伤机制）",
            },
            "prediction": {
                "winner": winner,
                "duration": duration,
                "ally_dpm_advantage": round(net_dpm(ally["weapon_dpms"], 0, 0) - net_dpm(enemy["weapon_dpms"], 0, 0)),
            },
            "note": "基于战斗机制.txt公式的简化推演：单发=(基础×调校1.3-抗性)，周期=max(冷却,锁定)+攻击持续，含命中/暴击期望与分伤机制。实际战斗还受拦截、系统损毁、维修、护航等因素影响。"
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
