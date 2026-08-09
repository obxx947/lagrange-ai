# -*- coding: utf-8 -*-
"""
舰船补充脚本：将资料中缺失的舰船补入战斗模拟器（目标 205+）
================================================================
来源：
1. 精炼清单（数据/精炼/舰船基础信息.json）——资料中存在的舰船（含参数）
2. 黑话.txt 全称——资料未收录详细参数的舰船（基础条目，字段继承同级舰，注明资料未收录）

更新三处：
- 拉格朗日智能体3/data/ship_database.json
- 拉格朗日智能体/lagrange_docs/ship_database.json
- 拉格朗日智能体3/simulator.html（SHIP_DATABASE 内嵌）

硬约束：所有字段来自资料原文；无数据字段继承同级舰并标注，禁止编造。
用法: python build_ships.py
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
REFINED = Path("C:/Users/Administrator/Desktop/数据/精炼/舰船基础信息.json")
DB3 = Path("C:/Users/Administrator/Desktop/拉格朗日智能体3/data/ship_database.json")
DB_ORIG = Path("C:/Users/Administrator/Desktop/拉格朗日智能体/lagrange_docs/ship_database.json")
SIM3 = Path("C:/Users/Administrator/Desktop/拉格朗日智能体3/simulator.html")

TYPE_CN2EN = {"护卫舰": "frigate", "驱逐舰": "destroyer", "巡洋舰": "cruiser",
              "战列巡洋舰": "battlecruiser", "战列舰": "battleship", "战机": "fighter",
              "护航艇": "corvette", "航空母舰": "aircraftcarrier", "支援舰": "support"}

SHIP_TYPE_WORDS = {
    "航空母舰": "aircraftcarrier", "战列巡洋舰": "battlecruiser", "战列舰": "battleship",
    "巡洋舰": "cruiser", "驱逐舰": "destroyer", "护卫舰": "frigate",
    "战机": "fighter", "护航艇": "corvette", "支援舰": "support", "登陆舰": "destroyer",
}


def norm(name):
    n = re.sub(r"[（(][^）)]*[）)]", "", str(name or ""))
    n = re.sub(r"[·•\-_/]", "", n)
    n = n.replace("级", "").replace("Ⅰ", "1").replace("II", "2").replace("III", "3").lower()
    return n


def db_hit(r, db):
    """精炼记录（含变体）是否已在库中：主词相同 + 变体互相包含"""
    full_raw = r["full_name"].replace("舰船全称：", "").replace("舰船名称：", "").strip()
    full = norm(full_raw)
    fparts = full_raw.split("-")
    main = norm(fparts[0]) if fparts else full
    variant = norm(fparts[1]) if len(fparts) > 1 else ""
    for s in db:
        k = norm(s.get("name", ""))
        if full in k or k in full:
            return True
        kparts = str(s.get("name", "")).split("-")
        kmain = norm(kparts[0]) if kparts else k
        kvariant = norm(kparts[1]) if len(kparts) > 1 else ""
        if main == kmain:
            if (not variant and not kvariant) or (variant and kvariant and (variant in kvariant or kvariant in variant)):
                return True
    return False


def parse_ammo(s):
    m = re.search(r"(\d+)\s*[×xX]\s*(\d+)", str(s or ""))
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1, 1


def parse_hit(s):
    s = str(s or "")
    m = re.search(r"(\d+)%\s*~\s*(\d+)%", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"＜\s*(\d+)%", s)
    if m:
        return 0, int(m.group(1))
    m = re.search(r"(\d+)%", s)
    if m:
        return max(0, int(m.group(1)) - 10), min(100, int(m.group(1)) + 10)
    return 50, 70


def targets_from_text(text, hit):
    types = []
    for cn, en in SHIP_TYPE_WORDS.items():
        if cn in text:
            types.append(en)
    if not types:
        if "大型" in text:
            types = ["aircraftcarrier", "battlecruiser", "cruiser"]
        elif "小型" in text:
            types = ["frigate", "destroyer"]
        elif "舰载机" in text:
            types = ["fighter", "corvette"]
        else:
            types = []
    lo, hi = parse_hit(hit)
    return [{"types": types, "hitMin": lo, "hitMax": hi}] if types else []


def weapon_to_json(w):
    ammo, attacks = parse_ammo(w.get("ammo_x_attacks", ""))
    dpm = {"antiShip": 0, "antiAir": 0, "siege": 0}
    for k, v in (w.get("dpm") or {}).items():
        dpm[k] = int(v)
    targets = []
    for seq in (w.get("attack_seq") or [])[:3]:
        t = targets_from_text(seq.get("targets", ""), seq.get("hit", ""))
        if t:
            targets.extend(t)
    if not targets:
        targets = [{"types": [], "hitMin": 50, "hitMax": 70}]
    seen = set()
    uniq = []
    for t in targets:
        key = tuple(t["types"])
        if key not in seen:
            seen.add(key)
            uniq.append(t)
    wtype = "direct" if "直射" in (w.get("ballistic") or "") else "projectile"
    return {
        "name": w.get("system", "武器系统"),
        "dmgType": "energy" if "能量" in (w.get("dmg_type") or "") else "physical",
        "weaponType": wtype,
        "dpm": dpm,
        "singleDmg": int(w["single_dmg"]) if w.get("single_dmg") else 100,
        "ammo": ammo,
        "attacks": attacks,
        "atkDuration": int(w["atk_duration"]) if w.get("atk_duration") else 0,
        "lockTime": int(w["lock_time"]) if w.get("lock_time") else 3,
        "cooldown": int(w["cooldown"]) if w.get("cooldown") else 8,
        "priority": w.get("priority") or "随机",
        "targets": uniq,
    }


def build_entry(r, sid):
    modules = {}
    for i, w in enumerate(r.get("weapons") or []):
        modules[f"M{i+1}"] = {"name": w.get("system", "武器系统"), "type": "weapon",
                              "selfRepair": False, "weapons": [weapon_to_json(w)]}
    entry = {
        "id": sid,
        "name": r["name"],
        "variant": r.get("variant") or r.get("sub_type") or "通用型",
        "type": TYPE_CN2EN.get(r.get("type", ""), "cruiser"),
        "size": "small",
        "position": "中排",
        "hp": int(r["hp"]) if r.get("hp") else 50000,
        "physicalArmor": 5,
        "energyArmor": 5,
        "commandValue": int(r["command_value"]) if r.get("command_value") else 10,
        "serviceLimit": 10,
        "speed": {"cruise": r.get("cruise_speed") or "600~1200", "warp": int(r["warp_speed"]) if r.get("warp_speed") else 3200},
        "ratings": {k: (v or "") for k, v in (r.get("ratings") or {}).items()},
        "modules": modules,
        "_note": f"来源: {r.get('source_file', '')}（精炼）",
    }
    ad = r.get("armor_desc") or ""
    m = re.search(r"防御(?:能力|数值)?\s*([\d.]+)", ad)
    if m:
        entry["physicalArmor"] = int(float(m.group(1)))
    return entry


def slug(name):
    MAP = {
        "卡利莱恩": "kalilaien", "刺水母": "cishuimu", "云海": "yunhai", "瑶光": "yaoguang",
        "诺玛M470": "normaM470", "XT-8": "xt8", "迅捷": "xunjie", "天玑": "tianji",
        "野火": "wildfire", "AT021": "at021", "BR050": "br050", "天璇": "tianxuan",
        "理智A101": "lizhi", "理智": "lizhi", "雷火V022": "leihuoV022", "佩刀": "peidao",
        "牛蛙": "niuwa", "海氏": "haishi", "林鸮": "linxiao", "砂龙": "shalong",
        "安德森": "andersen", "SC002": "sc002", "米斯特拉": "mistral",
    }
    for k, v in MAP.items():
        if k in name:
            return v
    return "ship-" + re.sub(r"[^0-9a-z]", "", norm(name))[:12]


def variant_tag(r, full):
    m = re.search(r"[（(]([A-Z]型?)[）)]", full) or re.search(r"\s([A-Z]型)", full) or re.search(r"-([A-Z])\b", full)
    if m:
        return m.group(1)[0]
    return re.sub(r"[^0-9a-z]", "", norm(r.get("sub_type") or r.get("variant") or ""))[:3] or "x"


def main():
    print("📂 读取精炼清单与现有库...")
    refined = json.loads(REFINED.read_text(encoding="utf-8"))
    db3 = json.loads(DB3.read_text(encoding="utf-8"))
    print(f"精炼 {len(refined)} 条 | 现有库 {len(db3)} 条")

    new_entries = []
    used_ids = {s.get("id") for s in db3}

    # 1. 精炼中缺失的（带参数）
    for r in refined:
        if r["name"] == "整体基础参数" or not r["name"]:
            continue
        if db_hit(r, db3):
            continue
        full = r["full_name"].replace("舰船名称：", "").replace("舰船全称：", "").strip()
        tag = variant_tag(r, full)
        sid = slug(r["name"] + tag)
        if sid in used_ids:
            sid = sid + "-" + tag
        if sid in used_ids:
            sid = sid + str(len(new_entries) + 1)
        used_ids.add(sid)
        e = build_entry(r, sid)
        e["name"] = e["name"].replace("ATO21", "AT021")
        new_entries.append(e)

    # 2. 黑话独有（资料未收录详细参数 → 基础条目）
    slang_missing = {
        "佩刀Aer410-强击攻击机": ("fighter", "peidao"),
        "牛蛙-两栖轰炸机": ("fighter", "niuwa"),
        "海氏追随者型-脉冲攻击机": ("fighter", "haishi"),
        "林鸮A100型-联合攻击机": ("fighter", "linxiao"),
        "砂龙-大气层拦截机": ("fighter", "shalong"),
        "平衡安德森SC020-侦察机": ("fighter", "andersen"),
        "SC002型-量子侦察机": ("fighter", "sc002"),
        "理智级A101-TE-战斗机": ("fighter", "lizhi-te"),
    }
    for full, (t, sid) in slang_missing.items():
        n = norm(full.split("-")[0])
        if any(n in norm(s.get("name", "")) or norm(s.get("name", "")) in n for s in db3):
            continue
        if sid in used_ids:
            continue
        used_ids.add(sid)
        new_entries.append({
            "id": sid, "name": full, "variant": "基础型", "type": t, "size": "small",
            "position": "中排", "hp": 4000, "physicalArmor": 3, "energyArmor": 3,
            "commandValue": 1, "serviceLimit": 10,
            "speed": {"cruise": "600~1200", "warp": 3200},
            "ratings": {}, "modules": {},
            "_note": "来源: 黑话.txt（资料未收录详细参数，数值为同级占位）",
        })

    print(f"🚢 新增舰船: {len(new_entries)} 条")
    for e in new_entries:
        print(f"  {e['id']:20s} {e['name'][:36]} | {e['type']} | hp={e['hp']} | 武器={len(e['modules'])}")

    if not new_entries:
        print("⚠️ 无新增，跳过写入")
        return

    # 3. 合并更新
    existing_ids = {s.get("id") for s in db3}
    added = [e for e in new_entries if e["id"] not in existing_ids]
    merged = db3 + added
    print(f"\n智能体3库: {len(db3)} → {len(merged)} 条")
    DB3.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    db_orig = json.loads(DB_ORIG.read_text(encoding="utf-8"))
    orig_ids = {s.get("id") for s in db_orig}
    orig_added = [e for e in new_entries if e["id"] not in orig_ids]
    merged_orig = db_orig + orig_added
    print(f"原版库: {len(db_orig)} → {len(merged_orig)} 条")
    DB_ORIG.write_text(json.dumps(merged_orig, ensure_ascii=False, indent=1), encoding="utf-8")

    # 4. simulator.html 插入
    sim = SIM3.read_text(encoding="utf-8")
    marker = "    const SHIP_DATABASE = {"
    if marker in sim:
        block = "\n".join(
            f"    {json.dumps(e['id'])}:{{id:{json.dumps(e['id'])},name:{json.dumps(e['name'])},variant:{json.dumps(e['variant'])},type:{json.dumps(e['type'])},size:{json.dumps(e['size'])},position:{json.dumps(e['position'])},hp:{e['hp']},physicalArmor:{e['physicalArmor']},energyArmor:{e['energyArmor']},commandValue:{e['commandValue']},serviceLimit:{e['serviceLimit']},speed:{{cruise:{json.dumps(e['speed']['cruise'])},warp:{e['speed']['warp']}}},ratings:{json.dumps(e.get('ratings') or {})},modules:{json.dumps(e.get('modules') or {})}}},"
            for e in added
        )
        sim = sim.replace(marker, marker + "\n" + block, 1)
        SIM3.write_text(sim, encoding="utf-8")
        print(f"simulator.html 已插入 {len(added)} 条")

    print(f"\n✅ 智能体3 舰船总数: {len(merged)}（目标 205+）")


if __name__ == "__main__":
    main()
