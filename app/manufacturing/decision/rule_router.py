"""
Rule-based Vision Skill Router (無 LLM 依賴版).

根據 BOM 表的自由文字，以正規表達式與關鍵字規則決定需要執行哪些 CV 掃描技能，
完全不依賴任何外部大語言模型。

使用範例：
    from app.manufacturing.decision.rule_router import plan_vision_skills

    skills = plan_vision_skills("需要點焊與 M6 攻牙，材料 SUS304")
    # ['scan_weld_symbols', 'scan_thread_marks', 'scan_holes']
"""

from __future__ import annotations

import re
from typing import List


# ---------------------------------------------------------------------------
# 規則定義表
# key  : CV 技能名稱 (skill key)
# value: 正規表達式 pattern 清單（任一命中即觸發）
# ---------------------------------------------------------------------------
_SKILL_RULES: dict[str, list[str]] = {
    # ── 焊接 ──────────────────────────────────────────────────────────────
    "scan_weld_symbols": [
        r"溶接|焊接|weld|銲接|点焊|點焊|氬焊|電焊|co2焊|tig|mig|spot\s*weld",
    ],
    # ── 螺紋 / 攻牙 ────────────────────────────────────────────────────────
    "scan_thread_marks": [
        r"タップ|攻牙|tap|抽牙|螺紋|tapping|thread|m\d+[\s×x]",
    ],
    # ── 孔洞（圓孔、長孔、沖孔）──────────────────────────────────────────────
    "scan_holes": [
        r"孔|hole|drilling|鑽孔|打孔|沖孔|burr|thru[\s-]?hole|slotted[\s-]?hole",
    ],
    # ── 折彎線 ────────────────────────────────────────────────────────────
    "scan_bend_lines": [
        r"折彎|bending|bend|彎折|折板|展開|l[\s-]?型|u[\s-]?型|z[\s-]?型",
    ],
    # ── 表面處理符號（噴砂、電鍍、烤漆…）──────────────────────────────────
    "scan_surface_marks": [
        r"噴砂|烤漆|電鍍|陽極|鍍鋅|paint|plating|coating|anodiz|powder\s*coat"
        r"|sandblast|surface\s*finish",
    ],
    # ── 公差 / 精度標記 ────────────────────────────────────────────────────
    "scan_tolerance_marks": [
        r"公差|tolerance|±\s*\d|h\d|h7|h8|js\d|精度|grade\s*\d",
    ],
    # ── 壓鉚 / 植件 ───────────────────────────────────────────────────────
    "scan_insert_marks": [
        r"壓鉚|植件|rivet|insert|nut\s*insert|pem|螺母",
    ],
}


def plan_vision_skills(bom_context: str) -> List[str]:
    """
    根據 BOM 文字以規則路由器決定需要執行的 CV 掃描技能清單。

    不呼叫任何外部 LLM；純 Python 正規表達式比對。

    Args:
        bom_context: 使用者輸入的 BOM 表或全域標注文字（多行自由文字皆可）。

    Returns:
        List[str]: 需要執行的 CV 技能名稱清單（去重、保持規則順序）。
                   若無任何規則命中則回傳空清單。

    Examples:
        >>> plan_vision_skills("需要點焊，材料 SUS304，M6 攻牙")
        ['scan_weld_symbols', 'scan_thread_marks']

        >>> plan_vision_skills("平板烤漆黑色，無折彎")
        ['scan_surface_marks']

        >>> plan_vision_skills("")
        []
    """
    if not bom_context or not bom_context.strip():
        return []

    text = bom_context.lower()
    triggered: List[str] = []

    for skill_key, patterns in _SKILL_RULES.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                triggered.append(skill_key)
                break  # 同一 skill 只加一次

    return triggered


def describe_skills(skills: List[str]) -> str:
    """
    將技能清單轉為人類可讀的描述字串（方便 Debug / UI 顯示）。

    Args:
        skills: plan_vision_skills() 的回傳值。

    Returns:
        str: 逗號分隔的中文說明，例如 '焊接符號掃描, 螺紋標記掃描'
    """
    _DESCRIPTIONS: dict[str, str] = {
        "scan_weld_symbols":   "焊接符號掃描",
        "scan_thread_marks":   "螺紋/攻牙標記掃描",
        "scan_holes":          "孔洞掃描",
        "scan_bend_lines":     "折彎線掃描",
        "scan_surface_marks":  "表面處理符號掃描",
        "scan_tolerance_marks":"公差標記掃描",
        "scan_insert_marks":   "壓鉚/植件掃描",
    }
    return ", ".join(_DESCRIPTIONS.get(s, s) for s in skills)
