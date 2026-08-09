# -*- coding: utf-8 -*-
"""
知识库精炼脚本（v2，兼容5种资料格式）
======================================
读取《数据》文件夹的舰船原始资料，整理精炼为 AI 更易读的结构化数据：
- 重点字段：名称、类型、服役数、指挥值/人口、基础属性（血量/防御/速度/评级）、武器概要
- 去除策略介绍（系统策略/专属策略/强化策略/策略名称/策略【】等）
- 数据文件夹原始内容一律不动，产物写入 数据/精炼/

支持格式：
A. 护卫舰格式  XX完整参数明细/阐述 + 舰船基础信息块 + N. 系统(搭载X门)
B. 驱逐舰格式  XX整体基础参数 + 单行基础信息 + A:"XX"系统 + 伤害数值/动作时序参数
C. 巡洋舰格式  XX完整参数整理 + 舰船基础总览/基础面板 + 一、XX系统 + 核心基础参数
D. 战巡格式    XX（精简调整版）+ 舰船基础面板 + M1 XX系统 + - N×武器行
E. 战机格式    舰船名称：XX + 基础整体属性 + 一、XX系统 + 武器核心参数

产物：舰船基础信息.json / 舰船基础信息.md / 精炼说明.md
用法: python refine_kb.py
"""

import json
import re
import time
from collections import Counter, OrderedDict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "数据"
SHIP_DIR = DATA_DIR / "舰船资料向量拆解"
POP_FILE = DATA_DIR / "舰船人口 载机基础信息 服役数.txt"
SLANG_FILE = DATA_DIR / "黑话.txt"
OUT_DIR = DATA_DIR / "精炼"

TYPE_MAP = [
    ("护卫舰", ["护卫舰"]),
    ("驱逐舰", ["驱逐舰"]),
    ("巡洋舰", ["巡洋舰"]),
    ("战列巡洋舰", ["战列巡洋舰"]),
    ("战列舰", ["战列舰"]),
    ("战机", ["战机"]),
    ("护航艇", ["护航艇"]),
    ("航空母舰", ["航空母舰"]),
    ("支援舰", ["支援舰"]),
]

TITLE_SUFFIXES = ["完整参数明细", "完整参数阐述", "完整参数整理", "整体基础参数",
                  "整机基础参数", "整机基础完整参数", "基础属性+全模块完整参数", "精简调整版",
                  "属性与全模块明细", "完整属性+模块数据+机制说明",
                  "完整基础属性+全模块详细数据", "完整基础属性+全模块详细参数",
                  "完整基础属性+全模块参数"]

# ==================== 记录切分 ====================

def is_record_title(line):
    s = line.strip().lstrip("\ufeff")
    if not s:
        return False
    if s.startswith("舰船名称：") or s.startswith("舰船全称："):
        return True
    # 标题可能带括号结尾，如 （精简调整版）→ 把括号内容并入检查
    core = re.sub(r"[（(]([^）)]*)[）)]$", r"\1", s)
    return any(core.endswith(suf) or s.endswith(suf) for suf in TITLE_SUFFIXES)


# 主标题后缀（排除"整机基础参数"等段标题）
MASTER_SUFFIXES = [s for s in TITLE_SUFFIXES if "整机" not in s]


def split_records(text):
    """
    按记录标题切分。
    - 主标题（完整参数整理等）始终是记录标题
    - 舰船全称/舰船名称 前缀行：仅当其主词与上一条记录不同时才是新记录
      （主标题与"舰船全称"成对出现时主词相同 → 视为正文行；不同变体主词不同 → 新记录）
    """
    lines = text.split("\n")

    def is_master(s):
        core = re.sub(r"[（(]([^）)]*)[）)]$", r"\1", s)
        return any(core.endswith(suf) or s.endswith(suf) for suf in MASTER_SUFFIXES)

    def main_word(title):
        t = title
        t = re.sub(r"^\d+[\.、]?\s*", "", t)
        if "：" in t:
            t = t.split("：", 1)[1]
        return parse_title(t)[0]

    records = []
    cur = None
    last_main = ""
    for line in lines:
        s = line.strip().lstrip("\ufeff")
        if not s:
            if cur is not None:
                cur["lines"].append(line)
            continue
        is_title = False
        if is_master(s):
            is_title = True
        elif s.startswith("舰船全称：") or s.startswith("舰船名称：") or re.match(r"^\d+[\.、]?\s*(舰船全称|舰船名称)[：:]", s):
            mw = main_word(s)
            # 紧跟在上一条主标题后（<8行）且主词相同的全称行 → 正文行（成对出现）
            near = cur is not None and len(cur["lines"]) < 8 and mw == last_main
            if not cur or not near:
                is_title = True
        if is_title:
            if cur is not None:
                records.append(cur)
            cur = {"title": s, "lines": []}
            last_main = main_word(s)
        elif cur is not None:
            cur["lines"].append(line)
    if cur is not None:
        records.append(cur)
    return records


def parse_title(title):
    """解析标题 → (name, variant, sub)"""
    t = title
    t = re.sub(r"^\d+[\.、]?\s*", "", t)
    if t.startswith("舰船名称：") or t.startswith("舰船全称："):
        t = t.split("：", 1)[1]
    # 去掉结尾后缀
    for suf in TITLE_SUFFIXES:
        if t.endswith(suf):
            t = t[: -len(suf)]
            break
    t = t.strip()
    # 去掉"（黄色选中XX）"等噪声
    t = re.sub(r"[（(]黄色选中[^）)]*[）)]", "", t)
    name, variant, sub = t.strip(), "", ""
    parts = t.split("-")
    if len(parts) >= 2:
        name = parts[0].strip()
        variant = "-".join(parts[1:]).strip()
    m = re.search(r"[（(]([^）)]*)[）)]", variant)
    if m:
        sub = m.group(1).strip()
        variant = variant.replace(m.group(0), "").strip()
    name = name.strip()
    return name, variant, sub


# ==================== 策略去除 ====================

FIELD_LINE_RE = re.compile(
    r"^(伤害类型|弹道类型|单发伤害|总分钟火力|分钟火力|分钟总伤害|每分钟伤害|弹药×攻击次数|弹药数×攻击次数|"
    r"锁定时间|冷却时间|攻击持续时间|持续时间|专属机制|系统强化|武器定位机制|锁定效率|基础优先目标|优先目标|"
    r"攻击类型|攻击模式|特性|伤害数值|动作时序参数|武器正式名称|武器核心参数|攻击序列|各类舰船命中率|"
    r"系统策略|强化策略|专属策略|核心机制|机制说明|工作目标序列)[：:&]")

STRATEGY_PATTERNS = [
    re.compile(r"^\s*策略名称"),
    re.compile(r"^\s*(专属策略|系统策略|强化策略)"),
    re.compile(r"^\s*策略【"),
    re.compile(r"^\s*\d+\.\s*策略"),
    re.compile(r"^\s*策略[：:]"),
]

SYSTEM_TITLE_PATTERNS = [
    re.compile(r"^\d+[\.、]\s*.*系统"),
    re.compile(r"^[A-H][：:].*系统"),
    re.compile(r"^[一二三四五六七八九十]+、.*系统"),
    re.compile(r"^M\d+.*系统"),
    re.compile(r"^A\d+.*系统"),
]


def clean_strategy(lines):
    """去除策略介绍行及其后续说明块"""
    out = []
    skip = False
    for line in lines:
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if skip:
            # 策略块延续：遇到字段行/系统标题/数字序号则结束跳过
            if FIELD_LINE_RE.match(s) or any(p.match(s) for p in SYSTEM_TITLE_PATTERNS) \
               or re.match(r"^\d+[\.、]", s):
                skip = False
            else:
                continue
        if any(p.match(s) for p in STRATEGY_PATTERNS):
            skip = True
            continue
        out.append(line)
    return out


# ==================== 基础信息提取（多格式） ====================

def extract_basic(record):
    info = {"hp": None, "armor_desc": "", "cruise_speed": "", "warp_speed": None,
            "service_limit": None, "ratings": {}, "command_value": None}
    for line in record["lines"]:
        s = line.strip()
        # A格式：舰船基础信息块字段
        m = re.match(r"^(名称|血量（结构值）|防御能力|巡航速度|战机/护航艇服役数量上限|航行去程、返程时间|舰船定位评级|指挥值|服役上限|服役数|结构值（总血量）|结构值（血量）|护甲属性|物理护甲|能量护甲减伤)[：:]\s*(.*)$", s)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k in ("血量（结构值）", "结构值（总血量）", "结构值（血量）"):
                info["hp"] = _to_num(v)
            elif k == "防御能力":
                info["armor_desc"] = v
            elif k == "护甲属性":
                info["armor_desc"] = v
            elif k == "物理护甲":
                info["armor_desc"] = info["armor_desc"] or f"物理护甲{v}"
            elif k == "能量护甲减伤":
                info["armor_desc"] = (info["armor_desc"] + "；" if info["armor_desc"] else "") + f"能量护甲{v}"
            elif k == "巡航速度":
                parts = v.split("；")
                info["cruise_speed"] = parts[0].strip() if parts else v
                for p in parts[1:]:
                    mm = re.search(r"曲率速度[：:]?\s*([\d~]+)", p)
                    if mm:
                        info["warp_speed"] = _to_num(mm.group(1))
            elif k in ("战机/护航艇服役数量上限", "服役上限", "服役数"):
                if v and "图片" not in v and "无" not in v:
                    info["service_limit"] = _to_num(v)
            elif k == "舰船定位评级":
                info["ratings"] = _parse_ratings(v)
            elif k == "指挥值":
                info["command_value"] = _to_num(v)
            continue
        # B格式：单行基础信息
        if "舰船血量（结构值）" in s and "；" in s:
            mm = re.search(r"舰船血量（结构值）[：:]?\s*([\d.]+)", s)
            if mm:
                info["hp"] = float(mm.group(1))
            mm = re.search(r"防御能力数值\s*([\d.]+)", s)
            if mm:
                info["armor_desc"] = f"防御能力{mm.group(1)}"
            mm = re.search(r"巡航速度\s*([\d~]+)", s)
            if mm:
                info["cruise_speed"] = mm.group(1)
            mm = re.search(r"曲率速度\s*([\d.]+)", s)
            if mm:
                info["warp_speed"] = float(mm.group(1))
            mm = re.search(r"舰船定位评级[：:]([^；;]+)", s)
            if mm:
                info["ratings"] = _parse_ratings(mm.group(1))
            continue
        # G格式：整体基础数据 编号行（结构血量/舰船体量/防御属性/航行属性/战机服役上限）
        m = re.match(r"^\d+\.\s*(结构血量|舰船体量|防御属性|航行属性|战机服役上限|舰船全称)[：:]?\s*(.*)$", s)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "结构血量":
                info["hp"] = _to_num(v)
            elif k == "防御属性":
                info["armor_desc"] = v
            elif k == "航行属性":
                pass  # 子行单独处理
            elif k == "战机服役上限":
                if v and "无" not in v and "图片" not in v:
                    info["service_limit"] = _to_num(v)
            continue
        # C格式：基础面板编号行
        m = re.match(r"^\d+\.\s*(结构值（血量）|护甲属性|速度属性|服役限制|舰船定位评级|指挥值|服役上限)[：:]?\s*(.*)$", s)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "结构值（血量）":
                info["hp"] = _to_num(v)
            elif k == "护甲属性":
                info["armor_desc"] = v
            elif k == "舰船定位评级":
                info["ratings"] = _parse_ratings(v)
            elif k == "指挥值":
                info["command_value"] = _to_num(v)
            elif k == "服役上限":
                if v and "图片" not in v and "无" not in v:
                    info["service_limit"] = _to_num(v)
            continue
        # C格式：速度子行
        m = re.match(r"^-?\s*巡航速度[：:]?\s*([\d~]+)", s)
        if m:
            info["cruise_speed"] = m.group(1)
            continue
        m = re.match(r"^-?\s*曲率速度[：:]?\s*([\d.]+)", s)
        if m:
            info["warp_speed"] = float(m.group(1))
            continue
        # D格式：基础面板编号行（指挥值/服役上限/结构值）
        m = re.match(r"^\d+\.\s*(指挥值|服役上限|结构值（总血量）|物理护甲|能量护甲减伤)[：:]?\s*(.*)$", s)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "指挥值":
                info["command_value"] = _to_num(v)
            elif k == "服役上限":
                if v and "图片" not in v and "无" not in v:
                    info["service_limit"] = _to_num(v)
            elif k == "结构值（总血量）":
                info["hp"] = _to_num(v)
            elif k == "物理护甲":
                info["armor_desc"] = (info["armor_desc"] + "；" if info["armor_desc"] else "") + f"物理护甲{v}"
            elif k == "能量护甲减伤":
                info["armor_desc"] = (info["armor_desc"] + "；" if info["armor_desc"] else "") + f"能量护甲{v}"
            continue
        # E/F格式：基础整体属性/整体基础属性 编号行
        m = re.match(r"^\d+\.\s*(血量（结构值）|尺寸等级|能量护甲|物理护甲|防御属性|航行参数|服役限制|火力总览)[：:]?\s*(.*)$", s)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "血量（结构值）":
                info["hp"] = _to_num(v)
            elif k == "防御属性":
                info["armor_desc"] = v
            elif k in ("能量护甲", "物理护甲"):
                if v and "无" not in v and "未标注" not in v:
                    info["armor_desc"] = (info["armor_desc"] + "；" if info["armor_desc"] else "") + f"{k}{v}"
            elif k == "航行参数":
                mm = re.search(r"巡航速度\s*([\d~]+)", v)
                if mm:
                    info["cruise_speed"] = mm.group(1)
                mm = re.search(r"曲率速度\s*([\d.]+)", v)
                if mm:
                    info["warp_speed"] = float(mm.group(1))
            elif k == "服役限制":
                mm = re.search(r"--/(\d+)", v)
                if mm:
                    info["service_limit"] = int(mm.group(1))
            continue
        # B/H格式：单行综合属性（编队规格/结构值（血量）/火力总览/定位评级）
        if ("编队规格" in s or "结构值（血量）" in s or "火力总览" in s) and ("；" in s or "；" in s):
            mm = re.search(r"结构值（血量）\s*([\d.]+)", s)
            if mm and info["hp"] is None:
                info["hp"] = float(mm.group(1))
            mm = re.search(r"防御数值\s*([\d.]+)", s)
            if mm and not info["armor_desc"]:
                info["armor_desc"] = f"防御数值{mm.group(1)}"
            mm = re.search(r"定位评级[：:]\s*([^；;]+)", s)
            if mm and not info["ratings"]:
                info["ratings"] = _parse_ratings(mm.group(1))
            continue
        # E格式：编队服役数量
        m = re.search(r"单编队服役数量为\s*(\d+)", s)
        if m and info["service_limit"] is None:
            info["service_limit"] = int(m.group(1))
    return info


def _parse_ratings(v):
    ratings = {}
    for m in re.finditer(r"(对舰|防空|攻城|支援|生存|战略)([A-Za-z]?)", v):
        key = {"对舰": "antiShip", "防空": "antiAir", "攻城": "siege",
               "支援": "support", "生存": "survival", "战略": "strategy"}[m.group(1)]
        ratings[key] = m.group(2) or ""
    return ratings


def _to_num(v):
    m = re.search(r"-?\d+(\.\d+)?", str(v))
    return float(m.group(0)) if m else None


# ==================== 武器提取（多格式） ====================

def extract_weapons(record):
    """提取武器系统。兼容 A/B/C/D/E 五种格式，统一输出结构"""
    weapons = []
    cur = None
    lines = clean_strategy(record["lines"])

    def new_weapon(system_title, mount=""):
        return {"system": system_title, "mount": mount, "dmg_type": "", "ballistic": "",
                "single_dmg": None, "dpm": {}, "ammo_x_attacks": "", "lock_time": None,
                "cooldown": None, "atk_duration": None, "priority": "", "special": [], "attack_seq": []}

    def is_weapon_system(title):
        return any(k in title for k in ["武器", "炮", "导弹", "鱼雷", "无人机", "机库", "舰载", "载机", "防空", "火力", "投射", "拦截", "轰炸", "舰炮", "鱼雷发射", "脉冲"])

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if not s:
            continue
        # 系统标题（A: N. XX系统；B: A："XX"系统；C: 一、XX系统；D: M1/A1 XX系统；F: A模块："XX"系统）
        sys_match = None
        m = re.match(r"^([A-H])模块[：:]\s*“?([^”]+)”?(?:系统|模块)?", s)
        if m:
            sys_match = m
        if not sys_match:
            m = re.match(r"^(\d+)[\.、]\s*(.+?)(?:系统|模块|矩阵).*$", s)
            if m and ("武器" in m.group(2) or "系统" in s):
                sys_match = m
        if not sys_match:
            m = re.match(r"^([A-H])[：:]\s*“?([^”]+)”?系统", s)
            if m:
                sys_match = m
        if not sys_match:
            m = re.match(r"^[一二三四五六七八九十]+、\s*(.+?)(?:系统|模块).*$", s)
            if m:
                sys_match = m
        if not sys_match:
            m = re.match(r"^(M\d+|A\d+)\s*(.+?)(?:系统|模块).*$", s)
            if m:
                sys_match = m
        if not sys_match:
            m = re.match(r"^模块\d+[：:]\s*(.+?)$", s)
            if m:
                sys_match = m
        if sys_match:
            title = s
            # 提取搭载信息
            mount = ""
            mm = re.search(r"[（(]搭载\s*([^）)]*)[）)]", s)
            if mm:
                mount = mm.group(1).strip()
            if is_weapon_system(title):
                cur = new_weapon(title, mount)
                weapons.append(cur)
            else:
                cur = None
            continue
        if cur is None:
            continue
        # D格式：- N×武器名行 → 新武器条目
        m = re.match(r"^-?\s*\d+[×xX]\s*(.+?)$", s)
        if m:
            wname = m.group(1).strip()
            wname = re.sub(r"[（(]原装[）)]|（原装）", "", wname).strip()
            cur = new_weapon(wname, mount="")
            weapons.append(cur)
            continue
        # B格式：1. 伤害数值 / 2. 动作时序参数
        m = re.match(r"^\d+\.\s*伤害数值[：:]\s*(.*)$", s)
        if m:
            v = m.group(1)
            mm = re.search(r"单发伤害\s*([\d.]+)", v)
            if mm:
                cur["single_dmg"] = float(mm.group(1))
            cur["dpm"] = _parse_dpm(v)
            continue
        m = re.match(r"^\d+\.\s*动作时序参数[：:]\s*(.*)$", s)
        if m:
            v = m.group(1)
            mm = re.search(r"持续时间\s*([\d.]+)", v)
            if mm:
                cur["atk_duration"] = float(mm.group(1))
            mm = re.search(r"弹药数×攻击次数\s*=\s*(\d+[×xX]\d+)", v) or re.search(r"弹药数[×xX]攻击次数\s*=\s*(\d+[×xX]\d+)", v)
            if mm:
                cur["ammo_x_attacks"] = mm.group(1)
            mm = re.search(r"冷却时间\s*([\d.]+)", v)
            if mm:
                cur["cooldown"] = float(mm.group(1))
            mm = re.search(r"锁定时间\s*([\d.]+)", v)
            if mm:
                cur["lock_time"] = float(mm.group(1))
            continue
        # F/G格式：编号字段行（值含分号/顿号/逗号分隔 → 多字段拆分）
        m = re.match(r"^\d+\.\s*(伤害类型|攻击类型|单发伤害|攻击次数配置|攻击持续时间|战斗序列|分钟伤害|优先攻击目标|弹药数×攻击次数)[：:]\s*(.*)$", s)
        if m and ("；" in m.group(2) or "、" in m.group(2) or "，" in m.group(2)):
            k, v = m.group(1), m.group(2).strip()
            if k == "战斗序列":
                continue
            # 分隔符拆分成 字段名：值 对 + 裸值归类
            for seg in re.split(r"[；;、，,]", v):
                seg = seg.strip()
                if not seg:
                    continue
                fm = re.match(r"^(伤害类型|弹道类型|单发伤害|分钟伤害|弹药数×攻击次数|攻击持续时间|锁定时间|冷却时间|优先攻击目标|攻击类型|附带机制)[：:]\s*(.*)$", seg)
                if fm:
                    fk, fv = fm.group(1), fm.group(2).strip()
                    if fk in ("伤害类型", "攻击类型"):
                        cur["dmg_type"] = fv
                    elif fk == "弹道类型":
                        cur["ballistic"] = fv
                    elif fk == "单发伤害":
                        cur["single_dmg"] = _to_num(fv)
                    elif fk == "分钟伤害":
                        cur["dpm"] = _parse_dpm(fv)
                    elif fk == "弹药数×攻击次数":
                        mm = re.search(r"(\d+[×xX]\d+)", fv)
                        if mm:
                            cur["ammo_x_attacks"] = mm.group(1)
                    elif fk == "攻击持续时间":
                        if fv and "图片" not in fv:
                            cur["atk_duration"] = _to_num(fv)
                    elif fk == "锁定时间":
                        cur["lock_time"] = _to_num(fv)
                    elif fk == "冷却时间":
                        cur["cooldown"] = _to_num(fv)
                    elif fk == "优先攻击目标":
                        cur["priority"] = fv
                    elif fk == "附带机制":
                        cur["special"].append(fv)
                else:
                    # 无字段名的裸值：按内容归类
                    if not cur["dmg_type"] and ("实弹" in seg or "能量" in seg):
                        cur["dmg_type"] = seg
                    elif not cur["ballistic"] and ("直射" in seg or "投射" in seg):
                        cur["ballistic"] = seg
                    elif "机制" in seg:
                        cur["special"].append(seg)
            if not cur["dpm"] and "分钟伤害" in v:
                cur["dpm"] = _parse_dpm(v)
            continue
        # C格式：核心基础参数编号行
        m = re.match(r"^\d+\.\s*(伤害类型|分钟总伤害|单发伤害|弹药×攻击次数|攻击次数配置|攻击持续时间|锁定时间|冷却时间|武器正式名称|优先攻击目标)[：:]\s*(.*)$", s)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "伤害类型":
                cur["dmg_type"] = v
            elif k == "分钟总伤害":
                cur["dpm"] = _parse_dpm(v)
            elif k == "单发伤害":
                cur["single_dmg"] = _to_num(v)
            elif k == "弹药×攻击次数":
                cur["ammo_x_attacks"] = v
            elif k == "攻击次数配置":
                mm = re.search(r"(\d+[×xX]\d+)", v)
                if mm:
                    cur["ammo_x_attacks"] = mm.group(1)
            elif k == "攻击持续时间":
                if v and "图片" not in v:
                    cur["atk_duration"] = _to_num(v)
            elif k == "锁定时间":
                cur["lock_time"] = _to_num(v)
            elif k == "冷却时间":
                cur["cooldown"] = _to_num(v)
            elif k == "优先攻击目标":
                cur["priority"] = v
            continue
        # E格式：武器核心参数行
        m = re.match(r"^-?\s*(攻击类型|伤害类型)[：:]\s*(.*)$", s)
        if m:
            cur["dmg_type"] = m.group(2).strip()
            continue
        m = re.match(r"^-?\s*武器数量[：:]\s*(.*)$", s)
        if m:
            cur["mount"] = m.group(1).strip()
            continue
        m = re.match(r"^-?\s*单发伤害[：:]\s*([\d.]+)", s)
        if m:
            cur["single_dmg"] = float(m.group(1))
            continue
        m = re.match(r"^-?\s*(单门火炮分钟伤害|每分钟伤害)[：:]\s*(.*)$", s)
        if m:
            cur["dpm"] = _parse_dpm(m.group(2))
            continue
        m = re.match(r"^-?\s*(攻击模式|弹药×攻击次数)[：:]\s*(\d+[×xX]\d+)", s)
        if m:
            cur["ammo_x_attacks"] = m.group(2)
            continue
        m = re.match(r"^-?\s*(攻击持续时间|冷却时间|锁定时间)[：:]\s*([\d.]+)", s)
        if m:
            k, v = m.group(1), float(m.group(2))
            if k == "攻击持续时间":
                cur["atk_duration"] = v
            elif k == "冷却时间":
                cur["cooldown"] = v
            elif k == "锁定时间":
                cur["lock_time"] = v
            continue
        m = re.match(r"^-?\s*基础优先目标[：:]\s*(.*)$", s)
        if m:
            cur["priority"] = m.group(1).strip()
            continue
        # D格式：武器属性行（逗号分隔：每分钟伤害/伤害类型/优先目标/单发伤害/特性）
        if "每分钟伤害" in s and "，" in s:
            mm = re.search(r"每分钟伤害[：:]?\s*([\d.]+)", s)
            if mm and not cur["dpm"]:
                cur["dpm"] = _parse_dpm(s)
            mm = re.search(r"伤害类型[：:]?\s*([^，,]+)", s)
            if mm and not cur["dmg_type"]:
                cur["dmg_type"] = mm.group(1).strip()
            mm = re.search(r"优先目标[：:]?\s*([^，,]+)", s)
            if mm and not cur["priority"]:
                cur["priority"] = mm.group(1).strip()
            mm = re.search(r"单发伤害[：:]?\s*([\d.]+)", s)
            if mm and cur["single_dmg"] is None:
                cur["single_dmg"] = float(mm.group(1))
            mm = re.search(r"特性[：:]?\s*(.+)$", s)
            if mm:
                cur["special"].append(mm.group(1).strip())
            continue
        # 通用字段行（A格式）
        fm = re.match(r"^(伤害类型|弹道类型|单发伤害|总分钟火力|分钟火力|弹药×攻击次数|锁定时间|冷却时间|攻击持续时间|专属机制|系统强化|武器定位机制|锁定效率)[：:]\s*(.*)$", s)
        if fm:
            k, v = fm.group(1), fm.group(2).strip()
            if k == "伤害类型":
                cur["dmg_type"] = v
            elif k == "弹道类型":
                cur["ballistic"] = v
            elif k == "单发伤害":
                cur["single_dmg"] = _to_num(v)
            elif k in ("总分钟火力", "分钟火力"):
                cur["dpm"] = _parse_dpm(v)
            elif k == "弹药×攻击次数":
                cur["ammo_x_attacks"] = v
            elif k == "锁定时间":
                cur["lock_time"] = _to_num(v)
            elif k == "冷却时间":
                cur["cooldown"] = _to_num(v)
            elif k == "攻击持续时间":
                if v and "图片" not in v and "未标注" not in v:
                    cur["atk_duration"] = _to_num(v)
            elif k in ("专属机制", "系统强化"):
                cur["special"].append(v)
            continue
        # 攻击序列（A/C: N阶；B: ①一阶；G: 序列01）
        m = re.match(r"^序列\d+[：:]\s*(.+?)，命中(.+)$", s)
        if m:
            cur["attack_seq"].append({"prio": len(cur["attack_seq"]) + 1, "targets": m.group(1).strip(), "hit": m.group(2).strip()})
            continue
        m = re.match(r"^(\d+)阶[（(]?([^）)]*)[)）]?[：:]\s*(.*)$", s)
        if m:
            cur["attack_seq"].append({"prio": int(m.group(1)), "targets": m.group(3).strip(), "hit": (m.group(2) or "").strip()})
            continue
        m = re.match(r"^[①②③④⑤]+.*[：:]", s)
        if m and ("命中" in s or "优先" in s):
            txt = re.sub(r"^[①②③④⑤]+", "", s)
            cur["attack_seq"].append({"prio": len(cur["attack_seq"]) + 1, "targets": txt[:40], "hit": ""})
            continue
        m = re.match(r"^优先级(\d+)[：:]\s*(.*)$", s)
        if m:
            cur["attack_seq"].append({"prio": int(m.group(1)), "targets": m.group(2).strip(), "hit": ""})
            continue
        # 命中率行（E格式：1.战列舰...：70%~100%）
        m = re.match(r"^\d+\.\s*(.+?)[：:]\s*([\d%~<]+)", s)
        if m and ("%" in m.group(2)):
            cur["attack_seq"].append({"prio": len(cur["attack_seq"]) + 1, "targets": m.group(1).strip(), "hit": m.group(2)})
            continue
    return weapons


def _parse_dpm(v):
    dpm = {}
    for m in re.finditer(r"(对舰|防空|攻城)([\d.]+)/", v):
        key = {"对舰": "antiShip", "防空": "antiAir", "攻城": "siege"}[m.group(1)]
        dpm[key] = float(m.group(2))
    return dpm


# ==================== 人口/指挥值 & 黑话 关联 ====================

def load_command_values():
    if not POP_FILE.exists():
        return []
    items = []
    for line in POP_FILE.read_text(encoding="utf-8").split("\n"):
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        # 格式1：名称（全部都为）—8 / 名称（全部都为8）/ 名称(全部都为18）
        m = re.match(r"^(.*?)[（(]全部都为\s*(\d+)[）)]$", line) or \
            re.match(r"^(.*?)（全部都为）[—\-]?\s*(\d+)$", line)
        if m:
            items.append({"name": m.group(1).strip(), "variant": "", "value": int(m.group(2))})
            continue
        # 格式2：名称—变体—N（从右往左最后一个破折号前是名称）——先于通用正则处理
        parts = [p.strip() for p in re.split(r"[—\-]", line) if p.strip()]
        if len(parts) >= 2 and re.match(r"^\d+$", parts[-1]) and (len(parts) > 2 or not re.match(r"^\d+$", parts[0])):
            items.append({"name": parts[0], "variant": "-".join(parts[1:-1]), "value": int(parts[-1])})
            continue
        # 格式3：名称—N
        m = re.match(r"^(.*?)[—\-]\s*(\d+)$", line)
        if m:
            items.append({"name": m.group(1).strip(), "variant": "", "value": int(m.group(2))})
    return items


def match_command_value(items, name, variant, sub):
    best = None
    for it in items:
        if name in it["name"] or it["name"] in name:
            score = 0
            if it["variant"]:
                if variant and (it["variant"] in variant or variant in it["variant"]):
                    score += 2
                elif sub and (it["variant"] in sub or sub in it["variant"]):
                    score += 1
            else:
                score += 1
            if best is None or score > best[0]:
                best = (score, it["value"])
    return best[1] if best else None


def load_slang():
    if not SLANG_FILE.exists():
        return {}
    slang = {}
    for line in SLANG_FILE.read_text(encoding="utf-8").split("\n"):
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("["):
            continue
        parts = re.split(r"[\t\s]+", line)
        if len(parts) >= 2:
            slang[parts[0]] = parts[1]
    return slang


# ==================== 主流程 ====================

def main():
    print(f"📂 舰船资料目录: {SHIP_DIR}")
    files = sorted(SHIP_DIR.glob("*.txt"))
    pop_items = load_command_values()
    slang = load_slang()
    print(f"📄 读取 {len(files)} 个舰船资料文件, 人口记录 {len(pop_items)} 条, 黑话 {len(slang)} 条")

    all_ships = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        records = split_records(text)
        stype = ship_type_of(f.name)
        for rec in records:
            name, variant, sub = parse_title(rec["title"])
            basic = extract_basic(rec)
            weapons = extract_weapons(rec)
            cv = match_command_value(pop_items, name, variant, sub) or basic.get("command_value")
            ship = {
                "name": name,
                "full_name": rec["title"],
                "type": stype,
                "variant": variant,
                "sub_type": sub,
                "service_limit": basic["service_limit"],
                "command_value": cv,
                "hp": basic["hp"],
                "armor_desc": basic["armor_desc"],
                "cruise_speed": basic["cruise_speed"],
                "warp_speed": basic["warp_speed"],
                "ratings": basic["ratings"],
                "weapons": weapons,
                "alias": slang.get(rec["title"], "") or slang.get(name, ""),
                "source_file": f.name,
            }
            all_ships.append(ship)

    print(f"🚢 精炼完成：共 {len(all_ships)} 条舰船记录（去重前）")

    # 去重：同 (name, sub) 保留信息更全的一条（优先有血量+武器）
    def info_score(s):
        return (1 if s["hp"] else 0) + (1 if s["weapons"] else 0) + (1 if s["command_value"] else 0) + (0.5 if s["armor_desc"] else 0)

    dedup = {}
    for s in all_ships:
        key = (s["name"], s["sub_type"] or s["variant"])
        if key not in dedup or info_score(s) > info_score(dedup[key]):
            dedup[key] = s
    all_ships = list(dedup.values())
    all_ships.sort(key=lambda s: (s["type"], s["name"]))

    print(f"🚢 去重后：共 {len(all_ships)} 条舰船记录")
    type_cnt = Counter(s["type"] for s in all_ships)
    print("类型分布:", dict(type_cnt))
    print("有指挥值:", sum(1 for s in all_ships if s["command_value"]))
    print("有血量:", sum(1 for s in all_ships if s["hp"]))
    print("有武器:", sum(1 for s in all_ships if s["weapons"]))

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "舰船基础信息.json").write_text(
        json.dumps(all_ships, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "舰船基础信息.md").write_text(build_md(all_ships), encoding="utf-8")
    (OUT_DIR / "精炼说明.md").write_text(build_readme(all_ships), encoding="utf-8")
    print(f"✅ 产物已输出到 {OUT_DIR}")


def build_md(ships):
    lines = ["# 舰船基础信息（精炼版）",
             "",
             "> 已去除策略介绍，保留基础信息与武器参数。来源：《数据/舰船资料向量拆解/》+《舰船人口 载机基础信息 服役数.txt》+《黑话.txt》",
             ""]
    groups = OrderedDict()
    for s in ships:
        groups.setdefault(s["type"], []).append(s)
    for stype, arr in groups.items():
        lines.append(f"## {stype}（{len(arr)}）")
        lines.append("")
        for s in arr:
            lines.append(f"### {s['full_name']}")
            cv = f"{s['command_value']}" if s["command_value"] else "?"
            sl = f"{s['service_limit']}" if s["service_limit"] else "?"
            lines.append(f"- 人口/指挥值：{cv} | 服役数：{sl} | 血量：{s['hp'] or '?'}")
            if s["armor_desc"]:
                lines.append(f"- 防御：{s['armor_desc']}")
            if s["cruise_speed"]:
                lines.append(f"- 速度：{s['cruise_speed']}" + (f"，曲率 {s['warp_speed']}" if s["warp_speed"] else ""))
            if s["ratings"]:
                lines.append("- 评级：" + "、".join(f"{k}{v}" for k, v in s["ratings"].items() if v))
            for w in s["weapons"]:
                parts = [w["system"]]
                if w["dmg_type"]:
                    parts.append(w["dmg_type"].replace("伤害", ""))
                if w["ballistic"]:
                    parts.append(w["ballistic"].replace("武器", ""))
                lines.append(f"- 武器：{w['system']}（{'、'.join(p for p in parts[1:] if p) or '武器'}）")
                detail = []
                if w["single_dmg"]:
                    detail.append(f"单发{int(w['single_dmg'])}" if w["single_dmg"] == int(w["single_dmg"]) else f"单发{w['single_dmg']}")
                if w["dpm"]:
                    detail.append("DPM:" + "/".join(f"{k}{int(v)}" for k, v in w["dpm"].items()))
                if w["ammo_x_attacks"]:
                    detail.append(f"弹药{w['ammo_x_attacks']}")
                if w["lock_time"]:
                    detail.append(f"锁定{w['lock_time']}s")
                if w["cooldown"]:
                    detail.append(f"冷却{w['cooldown']}s")
                if detail:
                    lines.append(f"  - {' | '.join(detail)}")
                if w["attack_seq"]:
                    seq = "；".join(f"{a['prio']}阶{a['targets']}({a['hit']})" for a in w["attack_seq"][:4])
                    lines.append(f"  - 攻击序列: {seq}")
                if w["special"]:
                    lines.append(f"  - 机制: {'、'.join(w['special'])}")
            lines.append("")
    return "\n".join(lines)


def build_readme(ships):
    lines = [
        "# 精炼说明",
        "",
        f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 处理规则",
        "- 原始资料位于《数据/舰船资料向量拆解/》，本文件夹为精炼产物，**原始数据未做任何修改**",
        "- 重点字段：名称、类型、服役数、指挥值/人口、血量、防御、速度、定位评级、武器概要（单发伤害/DPM/弹药/锁定/冷却/攻击序列）",
        "- **已去除策略介绍**：策略名称、专属策略、系统策略、强化策略、策略【】等段落全部剔除",
        "- 能源/装甲/动力/指挥系统仅保留系统名称（原资料多数仅标注名称）",
        "- 人口/指挥值来自《舰船人口 载机基础信息 服役数.txt》，按名称+变体自动关联；关联失败为 null",
        "- 服役数来自各舰船资料『服役上限/战机服役数量上限』字段；资料标注'图片无相关数据'的为 null",
        "- 黑话简称来自《黑话.txt》，自动关联到 alias 字段",
        "- 兼容5种资料格式（完整参数明细/阐述/整理、整体基础参数、精简调整版、舰船名称）",
        "",
        "## 产物",
        "- `舰船基础信息.json`：AI 可读结构化数据（每舰一条，含全部基础字段与武器参数）",
        "- `舰船基础信息.md`：人可读精炼文档（按舰船类型分组）",
        "",
        "## 统计",
        f"- 舰船记录总数：{len(ships)}",
        f"- 类型分布：{dict(Counter(s['type'] for s in ships))}",
        f"- 关联到指挥值：{sum(1 for s in ships if s['command_value'])}",
        f"- 关联到血量：{sum(1 for s in ships if s['hp'])}",
        f"- 含武器数据：{sum(1 for s in ships if s['weapons'])}",
        "",
        "## 同步位置",
        "精炼产物同时复制到两个项目的知识库，供 AI 直接检索：",
        "- `拉格朗日智能体/lagrange_docs/舰船基础信息（精炼）.json`",
        "- `拉格朗日智能体3/data/knowledge/舰船基础信息（精炼）.json`",
    ]
    return "\n".join(lines)


def ship_type_of(filename: str) -> str:
    # 长关键词优先（战列巡洋舰 先于 巡洋舰 匹配）
    for t, kws in sorted(TYPE_MAP, key=lambda x: -max(len(k) for k in x[1])):
        if any(k in filename for k in kws):
            return t
    return "未知"


if __name__ == "__main__":
    main()
