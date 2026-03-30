"""
Engineering Drawing Analysis Prompts for VLM.

Provides structured prompts for vision-language models to analyze
manufacturing drawings and identify required processes.

製程辨識系統 - VLM 提示詞模組
"""

from typing import List, Optional


def get_vlm_descriptive_prompt(bom_context: str = "", rag_context: str = "", system_anchors: Optional[List[str]] = None) -> str:
    """
    Generate a structured descriptive prompt for VLM geometry analysis.

    Includes:
    - ALLOWED VOCABULARY (Controlled Vocabulary): 6 categories of standard sheet-metal terms
    - CONFIDENCE TAGGING rules: VLM must wrap entities with <green>, <orange>, or <red>
    - 4-section output format for structured geometry description
    - SYSTEM ANCHORS: CV scanner + RAG prior hints for spatial relationship description

    Args:
        bom_context: Plain-text BOM / material facts confirmed by the user.
                     If non-empty, injected as a KNOWN FACTS preamble.
        rag_context: Past similar case description for few-shot reference.
        system_anchors: List of feature labels from CV scanner + RAG priors.
                        If non-empty, injected as a SYSTEM ANCHORS block.

    Returns:
        Complete prompt string ready to pass to VLMClient.analyze_image().
    """
    known_facts = ""
    bom_instruction = ""
    if bom_context.strip():
        known_facts = (
            "=== KNOWN BOM FACTS (FOR REFERENCE — DO NOT TREAT AS ABSOLUTE TRUTH) ===\n"
            "The following items are listed in the BOM / engineer notes.\n"
            "Use this as a REFERENCE CHECKLIST to cross-check against the drawing views.\n"
            "Do NOT blindly accept BOM items as ground truth — verify each one visually.\n\n"
            f"{bom_context.strip()}\n\n"
            "BOM CROSS-VERIFICATION RULES (apply in every section as you write):\n"
            "  Rule A: If you see a feature/symbol/process in the drawing views that is NOT mentioned in the BOM above,\n"
            "          you MUST flag it inline: 'BOM 沒有提到 [XXX]，但我在視角圖上有看到，請注意確認'\n"
            "  Rule B: If the BOM mentions an item that you CANNOT find evidence of in the drawing views,\n"
            "          you MUST flag it inline: 'BOM 有提到 [XXX]，但我在視角圖上沒有看到，請注意確認'\n"
            "  Rule C: If a BOM item IS confirmed in the drawing, state it normally with its location.\n"
            "  Rule D: Do NOT silently skip any BOM item — every item must be either confirmed or flagged.\n"
            "=== END OF KNOWN BOM FACTS ===\n\n"
        )
        bom_instruction = "Verify the 2D drawing views against the KNOWN BOM FACTS (for reference)."
    else:
        bom_instruction = "Analyze the 2D drawing views carefully (No BOM provided this time)."
    known_facts_block = known_facts

    # ── RAG few-shot reference block ─────────────────────────────────────
    rag_block = ""
    if rag_context.strip():
        rag_block = (
            "=== VERIFIED REFERENCE CASE (similar part from past analysis) ===\n"
            "A similar engineering drawing was analysed before and its verified description is shown below.\n"
            "USE THIS AS A STYLE AND REASONING GUIDE ONLY.\n"
            "DO NOT copy it word-for-word. Adapt the structure and reasoning style to what you actually see in the CURRENT drawing.\n"
            "IMPORTANT: If the reference case contains any numeric measurements (e.g. 110mm, T1.5, M6), IGNORE those numbers entirely — the ZERO NUMBERS RULE above applies here too.\n\n"
            f"{rag_context.strip()}\n\n"
            "=== END OF REFERENCE CASE ===\n\n"
            "Now analyse the CURRENT drawing provided above, using the reference case as a guide.\n\n"
        )

    # ── System Anchors block (Task1-Step3+4) ─────────────────────────────
    anchors_block = ""
    if system_anchors:
        _anchor_lines = "\n".join(f"  - {a}" for a in system_anchors)
        anchors_block = (
            "=== CV-CONFIRMED SYMBOLS (AUTHORITATIVE — DO NOT CONTRADICT) ===\n"
            "The following symbols were PHYSICALLY DETECTED in the engineering drawing images\n"
            "by the computer-vision template-matching system BEFORE you were called.\n"
            "These are GROUND TRUTH. You MUST acknowledge each one in your analysis.\n"
            "Denying or omitting a CV-CONFIRMED symbol is a CRITICAL ERROR.\n\n"
            f"{_anchor_lines}\n\n"
            "For each CV-CONFIRMED symbol: state it as confirmed in Section 2,\n"
            "describe its location using ALLOWED VOCABULARY location words.\n"
            "=== END OF CV-CONFIRMED SYMBOLS ===\n\n"
        )
    # ── Anti-Hallucination rules ─────────────────────────────────────────
    confidence_rules = (
        "FORBIDDEN \u2014 do NOT write any of the following:\n"
        "  \u2022 Numeric measurements of any kind (e.g., 110mm, 30mm, 4mm, 55mm)\n"
        "  \u2022 Width / Length / Height / Thickness values in any unit\n"
        "  \u2022 Thread specifications or tolerances (e.g., M6, R3, \u00b10.1)\n"
        "  \u2022 Dimension chains (e.g., '55mm x 10mm x 62mm', 'dimensions X x Y x Z')\n"
        "Writing a measurement number is a CRITICAL ERROR that invalidates your response.\n"
        "NO EXCEPTIONS \u2014 numeric measurements are forbidden even if they appear in the KNOWN FACTS block above. "
        "Use qualitative descriptions instead (e.g., 'thin sheet', 'narrow flange', 'large cutout').\n"
        "OUTPUT STRUCTURE: Output EXACTLY 3 sections in STRICT ORDER (### 1, ### 2, ### 3). "
        "STOP after Section 3. Do NOT add Section 4 or any continuation.\n\n"
    )

    # ── Vocabulary block ─────────────────────────────────────────────────
    vocab_block = (
        "SHAPE VOCABULARY — use in this priority order:\n"
        "\n"
        "  Tier 1 — PREFERRED TERMS (use these whenever they fit):\n"
        "    2D Outlines : Rectangular outline | Circular outline | L-shaped profile | C-shaped profile | U-shaped profile | Z-shaped profile | S-shaped profile | T-shaped profile | Hat-shaped profile | Trapezoidal profile\n"
        "    3D Shapes   : Flat Plate | Rectangular Base | L-shaped Bracket | C-Channel | U-shaped Channel | Hat Channel | Z-shaped Bracket | Box | Cylinder\n"
        "    Features    : Flange | Rib | Chamfer | Fillet | Gusset | Louver | Emboss\n"
        "    Holes       : Thru-hole | Threaded hole | Extruded hole (Burring) | Countersink (CSK) | Slotted hole | Notch | Cutout\n"
        "    Symbols     : Weld symbol | Surface finish mark\n"
        "    Confidence  : <green>word</green> = clearly visible | <orange>word</orange> = partially visible | <red>word</red> = inferred\n"
        "\n"
        "  Tier 2 — FALLBACK (only when NO Tier 1 term fits the shape):\n"
        "    Describe the geometry in plain English.\n"
        "    Rules:\n"
        "      • Describe shape and geometry ONLY — no process names, no material names\n"
        "      • No numbers, no dimensions, no units\n"
        "      • Be concise but complete (as many words as needed to be accurate)\n"
        "    Examples:\n"
        "      \u2713 'Omega-shaped profile' (closed top, two downward legs)\n"
        "      \u2713 'stepped rectangular outline with a central slot'\n"
        "      \u2713 'partial U-shaped cutout along one edge'\n"
        "      \u2717 'welded bracket' (contains process name)\n"
        "      \u2717 'small hole' (no size qualifiers)\n"
        "\n"
        "  NEVER invent brand names, process names, material names, or dimension values.\n\n"
    )

    return (
        # FORBIDDEN rules come FIRST — before any BOM/RAG content that may contain numbers,
        # so the model internalises the constraint before it ever reads dimension-bearing text.
        f"{confidence_rules}"
        f"{known_facts_block}"
        f"{rag_block}"
        f"{anchors_block}"
        f"{vocab_block}"
        f"You are an experienced mechanical Quality Assurance (QA) inspector. Your job is to {bom_instruction}\n"
        "Pay close attention to the Top View and Front View, as these two perspectives summarize 70% of the part's geometry. "
        "The remaining 30% is supplemented by the Side View. "
        "If an Isometric (ISO) or 3D view is provided, use it as additional reference to clarify spatial relationships.\n\n"
        "Tag EVERY shape/feature/hole/symbol noun with <green>, <orange>, or <red>.\n"
        "NO DIMENSIONS. Write exactly 3 sections in the format shown.\n\n"
        "FINAL REMINDER \u2014 ZERO NUMBERS RULE:\n"
        "Before you write anything: I will NOT write any digit followed by mm, cm, m, \u00b0, \u00b1, R, or M.\n"
        "Section 3 must sound like an experienced engineer explaining to a colleague \u2014 "
        "full sentences, cause-and-effect reasoning. "
        "Reference the BOM part name / material / context (if provided) to explain WHY features exist. "
        "Example style: 'Given this is a [BOM part name], the thru-holes visible in the Top View are likely mounting points for screws.' "
        "or: 'The weld symbol near the flange, combined with the U-shaped channel, suggests a welded bracket assembly.'\n"
        "Section 2 — SYMBOL & TEXT SEARCH format (output EXACTLY this structure):\n"
        "### 2. SYMBOL & TEXT SEARCH\n"
        "- Weld symbol detected: True/False (if True, state location briefly)\n"
        "- Surface finish mark detected: True/False (if True, state location briefly)\n"
        "- Other text annotation found: True/False (if True, describe briefly — no numbers)\n\n"
        "Answer ONLY True or False for each item above — no substitutions, no repetitive descriptions.\n\n"
        "Begin your report now with ### 1. VIEW-BY-VIEW OBSERVATION:\n"
    )


__all__ = [
    "get_vlm_descriptive_prompt",
]
