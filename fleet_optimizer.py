# -*- coding: utf-8 -*-
"""
舰队优化推荐服务
---------------
基于舰船数据库和游戏机制，提供AI驱动的舰队搭配建议。
结合RAG知识库检索玩家大神的配船经验。
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from doc_loader import get_lagrange_docs_path
from rag_service import search_similar_documents


# ==================== 评分规则 ====================

# 各位置推荐舰船类型
POSITION_RECOMMENDED = {
    "front": ["battlecruiser", "cruiser", "frigate", "battleship"],
    "mid": ["battleship", "cruiser", "destroyer"],
    "back": ["aircraftcarrier", "cruiser", "frigate", "support"],
}

# 评级分数映射
RATING_SCORES = {"S": 10, "A": 7, "B": 4, "C": 2, "D": 0}


@dataclass
class FleetRecommendation:
    """舰队推荐结果"""
    role: str           # 角色：前排坦克/中排输出/后排支援
    ship_name: str      # 舰船名称
    ship_id: str        # 舰船ID
    count: int          # 推荐数量
    reason: str         # 推荐理由
    score: float        # 综合评分


def load_ship_data() -> List[dict]:
    """加载完整舰船数据库"""
    json_path = get_lagrange_docs_path() / "ship_database.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def score_ship(ship: dict, role: str) -> float:
    """
    根据角色需求对舰船进行综合评分
    
    评分维度：
    - 生存评分（HP + 装甲 + 护盾）
    - 输出评分（对舰评级 + 攻城评级）
    - 防空评分（防空评级）
    - 战略评分（战略评级）
    - 指挥值效率（单位指挥值的战斗力）
    """
    hp = ship.get("hp", 10000)
    pa = ship.get("physicalArmor", 10)
    ea = ship.get("energyArmor", 5)
    cv = max(ship.get("commandValue", 1), 1)
    ratings = ship.get("ratings", {})
    stype = ship.get("type", "")
    position = ship.get("position", "mid")
    
    survival = RATING_SCORES.get(ratings.get("survival", "C"), 2)
    anti_ship = RATING_SCORES.get(ratings.get("antiShip", "C"), 2)
    anti_air = RATING_SCORES.get(ratings.get("antiAir", "C"), 2)
    siege = RATING_SCORES.get(ratings.get("siege", "C"), 2)
    strategy = RATING_SCORES.get(ratings.get("strategy", "C"), 2)
    
    # 基础生存分
    survival_score = (hp / 10000) * 3 + (pa / 20) * 2 + (ea / 10)
    survival_score += survival * 4
    
    # 指挥值效率
    efficiency = (hp / cv / 1000) * 5
    
    if role == "tank":
        # 坦克：生存 > 防空 > 其他
        pos_bonus = 5 if position == "front" else 0
        return survival_score * 0.5 + anti_air * 0.2 + strategy * 0.15 + efficiency * 0.1 + pos_bonus
    
    elif role == "dps":
        # 输出：对舰 > 攻城 > 生存
        pos_bonus = 5 if position in ("mid", "back") else 0
        return anti_ship * 0.4 + siege * 0.2 + survival_score * 0.25 + strategy * 0.1 + pos_bonus
    
    elif role == "support":
        # 支援：战略 > 生存 > 防空
        pos_bonus = 5 if position == "back" else 0
        return strategy * 0.4 + survival_score * 0.3 + anti_air * 0.2 + pos_bonus
    
    elif role == "carrier":
        # 航母：防空 > 战略 > 生存
        return anti_air * 0.4 + strategy * 0.3 + survival_score * 0.3
    
    return survival_score * 0.3 + anti_ship * 0.3 + anti_air * 0.2 + strategy * 0.2


def recommend_fleet(max_cv: int = 500) -> Dict:
    """
    基于169艘舰船数据库生成舰队推荐配置
    
    返回：
    {
        "tanks": [...],     # 前排坦克推荐
        "dps_ships": [...], # 中排输出推荐
        "support": [...],   # 后排支援推荐
        "carriers": [...],  # 航母推荐
        "total_cv": 500,
        "strategy": "说明文字",
    }
    """
    ships = load_ship_data()
    if not ships:
        return {"error": "舰船数据库未加载"}
    
    # 分类评分
    tanks, dps_list, supports, carriers = [], [], [], []
    
    for ship in ships:
        stype = ship.get("type", "")
        sid = ship.get("id", "")
        
        # 排除舰载机（单独处理）
        if ship.get("size") == "aircraft":
            continue
        
        entry = {
            "id": sid,
            "name": f"{ship.get('name','')}{ship.get('variant','')}",
            "type": stype,
            "cv": ship.get("commandValue", 10),
            "hp": ship.get("hp", 10000),
            "ratings": ship.get("ratings", {}),
            "tank_score": score_ship(ship, "tank"),
            "dps_score": score_ship(ship, "dps"),
            "support_score": score_ship(ship, "support"),
            "carrier_score": score_ship(ship, "carrier"),
        }
        
        tanks.append(entry)
        dps_list.append(entry)
        if stype in ("support", "frigate"):
            supports.append(entry)
        if stype == "aircraftcarrier":
            carriers.append(entry)
    
    # 排序取前N
    tanks.sort(key=lambda x: x["tank_score"], reverse=True)
    dps_list.sort(key=lambda x: x["dps_score"], reverse=True)
    supports.sort(key=lambda x: x["support_score"], reverse=True)
    carriers.sort(key=lambda x: x["carrier_score"], reverse=True)
    
    recommendations = {
        "tanks": [],
        "dps_ships": [],
        "supports": [],
        "carriers": [],
        "total_cv_used": 0,
        "strategy": "",
    }
    
    def add_ship(pool, role, max_count):
        nonlocal recommendations
        added = []
        used_cv = 0
        for ship in pool:
            if len(added) >= max_count:
                break
            cv = ship["cv"]
            count = min(5, (max_cv - recommendations["total_cv_used"] - used_cv) // cv)
            if count <= 0:
                continue
            added.append(FleetRecommendation(
                role=role,
                ship_name=ship["name"],
                ship_id=ship["id"],
                count=count,
                reason=f"综合评分{ship.get(role+'_score',0):.1f}，{ship['type']}类",
                score=ship.get(role+"_score", 0),
            ).__dict__)
            used_cv += count * cv
        return used_cv
    
    # 分配指挥值：坦克40%，输出35%，支援15%，航母10%
    tank_cv = int(max_cv * 0.40)
    dps_cv = int(max_cv * 0.35)
    sup_cv = int(max_cv * 0.15)
    car_cv = int(max_cv * 0.10)
    
    cv1 = add_ship(tanks, "tank", 4)
    recommendations["total_cv_used"] += cv1
    
    cv2 = add_ship(dps_list[:30], "dps", 6)
    recommendations["total_cv_used"] += cv2
    
    cv3 = add_ship(supports, "support", 3)
    recommendations["total_cv_used"] += cv3
    
    cv4 = add_ship(carriers, "carrier", 1)
    recommendations["total_cv_used"] += cv4
    
    recommendations["strategy"] = _generate_strategy(recommendations)
    
    return recommendations


def _generate_strategy(recs: Dict) -> str:
    """根据推荐编队生成战术策略说明"""
    tanks = recs.get("tanks", [])
    dps = recs.get("dps_ships", [])
    
    tank_names = [t["ship_name"] for t in tanks[:3]]
    dps_names = [d["ship_name"] for d in dps[:3]]
    
    strategy = f"前排{tank_names}承担伤害，中后排{dps_names}主力输出。"
    
    avg_survival = sum(t.get("score", 0) for t in tanks) / max(len(tanks), 1)
    if avg_survival > 25:
        strategy += "前排坦度充足，可适当增加输出舰船。"
    else:
        strategy += "建议提升前排生存能力，优先选择高装甲/高护盾舰船。"
    
    return strategy


def get_knowledge_recommendations(query: str = "最强舰队搭配") -> List[Dict]:
    """从RAG知识库检索玩家大神的配船经验"""
    docs = search_similar_documents(query, top_k=3)
    results = []
    for doc in docs:
        results.append({
            "source": doc["source"],
            "content": doc["content"][:300],
            "score": doc["score"],
        })
    return results


# ==================== 测试 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("  舰队优化推荐引擎")
    print("=" * 50)
    
    result = recommend_fleet(max_cv=500)
    
    for role in ["tanks", "dps_ships", "supports", "carriers"]:
        items = result.get(role, [])
        if items:
            print(f"\n{'🛡️ 坦克' if role=='tanks' else '⚔️ 输出' if role=='dps_ships' else '🏥 支援' if role=='supports' else '🛫 航母'}:")
            for item in items[:3]:
                print(f"  {item['ship_name']} x{item['count']} — {item['reason']}")
    
    print(f"\n指挥值: {result['total_cv_used']}/500")
    print(f"\n策略: {result['strategy']}")
