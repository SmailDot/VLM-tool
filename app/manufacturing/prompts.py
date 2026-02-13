"""
Engineering Drawing Analysis Prompts for VLM.

Provides structured prompts for vision-language models to analyze 
manufacturing drawings and identify required processes.

製程辨識系統 - VLM 提示詞模組
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class PromptTemplate:
    """
    Prompt template with metadata.
    
    Attributes:
        name: Template name
        system_prompt: System-level instructions
        user_prompt: User query template
        expected_output: Expected JSON schema
        examples: Few-shot examples (optional)
    """
    name: str
    system_prompt: str
    user_prompt: str
    expected_output: Dict[str, Any]
    examples: Optional[List[Dict[str, Any]]] = None


class EngineeringPrompts:
    """
    Collection of prompts for engineering drawing analysis.
    
    Designed for sheet metal manufacturing process recognition with 
    78 process types across 8 categories.
    
    Process Categories:
    - C: 切割 (Cutting) - 7 processes
    - D: 折彎 (Bending) - 5 processes  
    - F: 焊接 (Welding) - 14 processes
    - E: 去毛邊 (Deburring) - 3 processes
    - H: 表面處理 (Surface Treatment) - 18 processes
    - I: 檢驗 (Inspection) - 12 processes
    - O: 其他 (Other) - 17 processes
    - Q: 組裝 (Assembly) - 20 processes
    - K: 切削 (Machining) - 1 process
    """
    
    # System prompt for manufacturing expert role
    MANUFACTURING_EXPERT_SYSTEM_PROMPT = (
        "你是一位資深的鈑金加工工程師，擁有 20 年以上的工程圖紙分析經驗。"
        "你精通各類製造製程，能夠從工程圖的視覺特徵準確判斷所需的加工步驟。\n\n"
        "你的專長包括：\n"
        "- 識別折彎線、焊接符號、表面處理標記等技術符號\n"
        "- 分析零件形狀與結構特徵\n"
        "- 根據材質、厚度、公差要求推斷製程\n"
        "- 理解製程間的依賴關係與順序\n\n"
        "**重要：請務必使用繁體中文（Traditional Chinese）回答所有問題。**\n"
        "所有分析結果、形狀描述、推理依據都必須用繁體中文輸出。\n"
        "**專業術語格式**：若涉及專業術語，請使用「中文(英文)」格式，例如：\n"
        "  - 折彎線(bend line)\n"
        "  - 焊接符號(welding symbol)\n"
        "  - 表面處理(surface treatment)\n"
        "  - 去毛邊(deburring)\n"
        "請以專業、準確、結構化的方式回答問題，**只輸出 JSON 格式**。"
    )
    
    @staticmethod
    def get_process_recognition_prompt(
        include_examples: bool = True,
        language: str = "zh-TW",
        detail_level: str = "standard"
    ) -> PromptTemplate:
        """
        Get prompt for manufacturing process recognition from engineering drawings.
        
        This prompt guides the VLM to:
        1. Observe overall shape (flat, L-shape, U-shape, box, etc.)
        2. Detect key features (bend lines, welding symbols, holes, etc.)
        3. Infer required processes based on detected features
        4. Output structured JSON with process IDs and reasoning
        
        Args:
            include_examples: Include few-shot examples in prompt
            language: Output language ("zh-TW", "zh-CN", "en")
            detail_level: Level of detail ("brief", "standard", "detailed")
        
        Returns:
            PromptTemplate with complete prompt structure
        """
        
        # Define expected output schema
        expected_output = {
            "shape_description": "string - 零件整體形狀描述",
            "overall_complexity": "string - 複雜度評估 (簡單/中等/複雜)",
            "detected_features": {
                "geometry": [
                    "string - 幾何特徵列表，如 'bend_lines', 'holes', 'complex_curves'"
                ],
                "symbols": [
                    "string - 符號列表，如 'welding_symbol', 'surface_finish_mark'"
                ],
                "text_annotations": [
                    "string - 文字標註，如 '折彎', '烤漆', 'M3 抽牙'"
                ],
                "material_info": "string - 材質資訊 (如有)"
            },
            "suggested_process_ids": [
                "string - 製程編號列表，如 ['C01', 'D01', 'E01', 'F01']"
            ],
            "confidence_scores": {
                "process_id": "float - 該製程的信心度 (0-1)"
            },
            "reasoning": "string - 詳細的判斷依據說明",
            "process_sequence": [
                "string - 建議的製程順序 (optional)"
            ]
        }
        
        # Build user prompt based on detail level
        if detail_level == "brief":
            user_prompt = _build_brief_prompt(language)
        elif detail_level == "detailed":
            user_prompt = _build_detailed_prompt(language)
        else:  # standard
            user_prompt = _build_standard_prompt(language)
        
        # Add examples if requested
        examples = None
        if include_examples:
            examples = _get_few_shot_examples(language)
        
        return PromptTemplate(
            name="process_recognition_standard",
            system_prompt=EngineeringPrompts.MANUFACTURING_EXPERT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            expected_output=expected_output,
            examples=examples
        )
    
    @staticmethod
    def get_feature_detection_prompt() -> PromptTemplate:
        """
        Get prompt focused on detecting specific features only.
        
        Useful for pre-processing or validation.
        
        Returns:
            PromptTemplate for feature detection
        """
        system_prompt = (
            "你是一位工程圖紙特徵識別專家。"
            "請仔細觀察圖紙，識別所有可見的幾何特徵、符號和文字標註，圖紙中會有輔助標線，請不要把輔助標線納入特徵識別。"
            "**重要：請務必使用繁體中文（Traditional Chinese）描述所有特徵。**\n"
            "**專業術語格式**：若涉及專業術語，請使用「中文(英文)」格式，例如：\n"
            "  - 折彎線(bend line)\n"
            "  - 孔洞(hole)\n"
            "  - 焊接符號(welding symbol)\n"
            "  - 點焊(spot welding)\n"
            "**只輸出 JSON 格式**。"
        )
        
        user_prompt = """
請分析這張工程圖紙，識別以下特徵：

**1. 幾何特徵**：
- 折彎線 (bend_lines)：虛線或標註為折彎的線條
- 孔洞 (holes)：圓形孔、螺絲孔、通風孔
- 角度 (angles)：標註的角度值
- 複雜曲線 (complex_curves)：非直線的輪廓

**2. 符號**：
- 焊接符號 (welding_symbol)
- 點焊符號 (spot_welding)
- 表面處理符號 (surface_finish_mark)

**3. 文字標註**：
- 製程相關：折彎、焊接、烤漆、電鍍等
- 材質標註：SPCC, SUS304, AL 等
- 特殊要求：抽牙、壓鉚、去毛邊等

請以 JSON 格式輸出：
```json
{
  "geometry_features": ["feature1", "feature2"],
  "symbols": ["symbol1", "symbol2"],
  "text_annotations": ["text1", "text2"],
  "material": "材質名稱或null",
  "special_notes": ["特殊要求1", "特殊要求2"]
}
```
"""
        
        expected_output = {
            "geometry_features": ["list of strings"],
            "symbols": ["list of strings"],
            "text_annotations": ["list of strings"],
            "material": "string or null",
            "special_notes": ["list of strings"]
        }
        
        return PromptTemplate(
            name="feature_detection",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expected_output=expected_output
        )
    
    @staticmethod
    def get_shape_classification_prompt() -> PromptTemplate:
        """
        Get prompt for overall shape classification.
        
        Useful for initial categorization.
        
        Returns:
            PromptTemplate for shape classification
        """
        system_prompt = (
            "你是一位零件形狀分類專家。"
            "請觀察零件的整體輪廓，判斷其基本形狀類型。"
            "**只輸出 JSON 格式**。"
        )
        
        user_prompt = """
請判斷這個零件的整體形狀類型：

**形狀類別**：
- 平板 (flat_plate)：平面板材，無折彎
- L型 (l_shape)：單次 90° 折彎
- U型 (u_shape)：雙折彎，形成 U 字形
- Z型 (z_shape)：兩次反向折彎
- 箱體 (box_shape)：多次折彎形成封閉或半封閉結構
- 圓筒 (cylinder)：捲曲成圓筒狀
- 複雜形狀 (complex_shape)：不規則或多重特徵組合

請以 JSON 格式輸出：
```json
{
  "shape_type": "形狀類別代碼",
  "shape_name": "形狀中文名稱",
  "confidence": 0.95,
  "description": "詳細描述零件形狀特徵",
  "key_dimensions": {
    "length": "長度估計或null",
    "width": "寬度估計或null",
    "height": "高度估計或null"
  }
}
```
"""
        
        expected_output = {
            "shape_type": "string - one of [flat_plate, l_shape, u_shape, z_shape, box_shape, cylinder, complex_shape]",
            "shape_name": "string - Chinese name",
            "confidence": "float - 0 to 1",
            "description": "string - detailed description",
            "key_dimensions": {
                "length": "string or null",
                "width": "string or null", 
                "height": "string or null"
            }
        }
        
        return PromptTemplate(
            name="shape_classification",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expected_output=expected_output
        )


def _build_standard_prompt(language: str = "zh-TW") -> str:
    """Build standard-level detail prompt."""
    return """
請分析這張鈑金工程圖，識別所需的製造製程。

**重要：語言與術語格式要求**
- 所有輸出必須使用繁體中文(Traditional Chinese)
- 專業術語請使用「中文(英文)」格式，例如：
  * 折彎線(bend line)
  * 焊接符號(welding symbol)  
  * 孔洞(hole)
  * 表面處理(surface treatment)
- 在 reasoning 欄位中詳細說明推理依據時，也請使用此格式

**分析步驟**：

**步驟 1：觀察整體形狀**
- 零件的基本輪廓是什麼？(平板/L型/U型/箱體/其他)
- 整體複雜度如何？(簡單/中等/複雜)

**步驟 2：檢測關鍵特徵**

幾何特徵：
- ✓ 折彎線 (bend_lines)：虛線或標註的折彎位置
- ✓ 孔洞 (holes)：圓孔、長孔、螺絲孔
- ✓ 角度 (angles)：折彎角度標註 (如 90°, 45°)
- ✓ 複雜曲線 (complex_curves)：非直線輪廓

符號：
- ✓ 焊接符號 (welding_symbol)：三角形、箭頭等焊接標記
- ✓ 點焊符號 (spot_welding)：圓圈或點狀標記
- ✓ 表面處理符號 (surface_finish_mark)：粗糙度、鍍層標記

文字標註：
- ✓ 製程關鍵字：折彎、焊接、烤漆、電鍍、噴砂等
- ✓ 材質標註：SPCC, SUS304, AL6061 等
- ✓ 特殊要求：抽牙 (M3/M4/M5)、壓鉚螺母、色號等

**步驟 3：推論製程**

根據檢測到的特徵，從以下 78 種製程中選擇適用的：

**切割類 (C)**：
- C01: 單機切割 (預設)
- C05: M3048 (有抽牙/中心沖標註)

**折彎類 (D)**：
- D01: 折彎 (檢測到折彎線)
- D04: 折彎/植零件 (折彎線 + 植件名稱)
- D06: 植零件 (壓鉚螺母、接地螺絲)

**焊接類 (F)**：
- F01: 焊接 (焊接符號或"焊接"字眼)
- F03: SPOT點焊 (點焊符號)

**去毛邊類 (E)**：
- E01: 去毛邊 (幾乎所有金屬件都需要)

**表面處理類 (H)**：
- H01: 除焦洗淨 (白鐵+焊接+無烤漆)
- H02: 廠內噴砂 (標註"噴砂")
- H03: 包裝網蓋貼 (網印、蓋印、貼紙)

**檢驗類 (I)**：
- I01: 成品全檢 (高精度要求)

**組裝類 (Q)**：
- Q01: 治具 (複雜組裝)

**其他 (O, K, J)**：
- 按需選擇

**輸出格式**：

請嚴格按照以下 JSON 格式輸出，**不要包含任何其他文字**：

```json
{
  "shape_description": "零件形狀的簡要描述",
  "overall_complexity": "簡單/中等/複雜",
  "detected_features": {
    "geometry": ["特徵1", "特徵2"],
    "symbols": ["符號1", "符號2"],
    "text_annotations": ["標註1", "標註2"],
    "material_info": "材質資訊或null"
  },
  "suggested_process_ids": ["C01", "D01", "E01"],
  "confidence_scores": {
    "C01": 0.95,
    "D01": 0.85,
    "E01": 0.90
  },
  "reasoning": "根據檢測到折彎線(bend line, 2條)和角度標註(90°)，判斷需要切割(cutting, C01)和折彎(bending, D01)製程。所有金屬件預設需要去毛邊(deburring, E01)。",
  "process_sequence": ["C01", "D01", "E01"]
}
```

**重要提醒**：
- 必須輸出有效的 JSON 格式
- process_ids 必須是資料庫中存在的編號
- confidence_scores 範圍為 0-1
- reasoning 要具體說明判斷依據
"""


def _build_brief_prompt(language: str = "zh-TW") -> str:
    """Build brief-level prompt."""
    return """
請分析這張工程圖，識別所需的製程。

觀察：
1. 整體形狀 (平板/L型/U型/箱體等)
2. 關鍵特徵 (折彎線/焊接符號/孔洞/文字標註)
3. 推論製程編號

以 JSON 格式輸出：
```json
{
  "shape_description": "形狀描述",
  "detected_features": ["特徵1", "特徵2"],
  "suggested_process_ids": ["C01", "D01"],
  "reasoning": "判斷依據"
}
```
"""


def _build_detailed_prompt(language: str = "zh-TW") -> str:
    """Build detailed-level prompt with comprehensive guidance."""
    standard = _build_standard_prompt(language)
    
    # Add detailed process library reference
    detailed_addition = """

**完整製程參考 (78種)**：

**切割類 (C) - 7種**：
C01(單機切割), C03(複合機), C04(M2048), C05(M3048), C06(手動切割), C07(水刀切割), C08(線切割)

**折彎類 (D) - 5種**：
D01(折彎), D04(折彎/植零件), D06(植零件), D07(植零件/折彎), D09(植零件/沖壓)

**焊接類 (F) - 14種**：
F01(焊接), F03(SPOT點焊), F05(廠內點焊機), F11(廠內鋁焊), F14(焊接修補), F16(自動焊接) 等

**去毛邊 (E) - 3種**：
E01(去毛邊), E02(去毛邊2), E04/E08/E11(特殊去毛邊)

**表面處理 (H) - 18種**：
H01(除焦洗淨), H02(廠內噴砂), H03(包裝網蓋貼), H04(外包研磨), H05(外包噴砂), 
H08(前處烤漆), H14(廠內鈍化), H15(外包陽極), H16(外包電鍍鋅), H17(外包電鍍鉻) 等

**檢驗類 (I) - 12種**：
I01(成品全檢), I02(成品抽檢2), I04(氣密測試), I14(可程式檢測), I19(無塵室客戶成檢) 等

**組裝類 (Q) - 20種**：
Q01(治具), Q04(材料/螺絲/標籤碼), Q05(廠內沖壓), Q07(廠內攻牙/後處理), Q11(無塵室組立) 等

**其他 (O) - 17種**：
O02(包材平貼文件), O04(除膠), O12(板材製程), O14(成模線) 等

請根據圖面特徵從上述製程中選擇合適的，並給出詳細的判斷理由。
"""
    
    return standard + detailed_addition


def _get_few_shot_examples(language: str = "zh-TW") -> List[Dict[str, Any]]:
    """Get few-shot examples for in-context learning."""
    return [
        {
            "description": "簡單 L 型折彎件範例",
            "input": "一個帶有單次 90° 折彎的平板零件，標註有折彎線和去毛邊要求",
            "output": {
                "shape_description": "L型折彎件，單次90°折彎",
                "overall_complexity": "簡單",
                "detected_features": {
                    "geometry": ["bend_lines"],
                    "symbols": [],
                    "text_annotations": ["折彎", "去毛邊"],
                    "material_info": "SPCC"
                },
                "suggested_process_ids": ["C01", "D01", "E01"],
                "confidence_scores": {
                    "C01": 0.95,
                    "D01": 0.90,
                    "E01": 0.95
                },
                "reasoning": "圖面標註清楚的折彎線，材質為 SPCC 需要切割。所有金屬件預設去毛邊。",
                "process_sequence": ["C01", "D01", "E01"]
            }
        },
        {
            "description": "焊接件範例",
            "input": "兩片板材組合，標註焊接符號和烤漆要求",
            "output": {
                "shape_description": "組合件，由兩片平板焊接而成",
                "overall_complexity": "中等",
                "detected_features": {
                    "geometry": ["multiple_parts"],
                    "symbols": ["welding_symbol"],
                    "text_annotations": ["焊接", "烤漆", "黑色"],
                    "material_info": "SPCC"
                },
                "suggested_process_ids": ["C01", "F01", "E01", "H01", "H08"],
                "confidence_scores": {
                    "C01": 0.95,
                    "F01": 0.95,
                    "E01": 0.90,
                    "H01": 0.85,
                    "H08": 0.90
                },
                "reasoning": "檢測到焊接符號，需要焊接製程(F01)。焊接後需除焦洗淨(H01)。標註烤漆黑色，需前處烤漆(H08)。",
                "process_sequence": ["C01", "F01", "H01", "E01", "H08"]
            }
        },
        {
            "description": "複雜組裝件範例",
            "input": "多次折彎 + 壓鉚螺母 + 焊接的複雜零件",
            "output": {
                "shape_description": "箱體結構，多次折彎形成半封閉空間",
                "overall_complexity": "複雜",
                "detected_features": {
                    "geometry": ["bend_lines", "holes"],
                    "symbols": ["welding_symbol"],
                    "text_annotations": ["折彎", "壓鉚螺母", "M4", "焊接"],
                    "material_info": "SUS304"
                },
                "suggested_process_ids": ["C05", "D04", "F01", "E01", "H01", "I01"],
                "confidence_scores": {
                    "C05": 0.85,
                    "D04": 0.90,
                    "F01": 0.88,
                    "E01": 0.95,
                    "H01": 0.80,
                    "I01": 0.75
                },
                "reasoning": "標註 M4 抽牙需要 M3048(C05)。折彎線+壓鉚螺母需要折彎/植零件(D04)。焊接符號需焊接(F01)。不鏽鋼焊接需除焦(H01)。複雜結構建議全檢(I01)。",
                "process_sequence": ["C05", "D04", "F01", "H01", "E01", "I01"]
            }
        }
    ]


# Convenience function for quick access
def get_default_prompt(parent_context: str = "") -> str:
    """
    Generate the main prompt for VLM analysis.
    Now includes specific Symbol knowledge and Process ID mapping.
    
    Returns:
        請分析這張鈑金工程圖，並以 JSON 格式輸出你的發現。

        重要：你必須嚴格遵守以下的製程代號對照表，不可發明代號：
        - F01: 焊接 (特徵：三角形符號 △、箭頭指向接合處、Weld字樣)
        - D01: 折彎 (特徵：L型、U型、折彎線、展開圖)
        - D04: 折彎/植零件 (特徵：同時有折彎和壓鉚螺母/螺柱)
        - C05: M3048/沖孔 (特徵：大量孔洞、百葉窗、特殊成形)
        - D06: 植零件 (特徵：壓鉚螺母、螺柱)

        特殊符號教學：
        1. 如果看到 "4|4△" 且有箭頭指向線條，代表線條上的這個地方是「焊接 (F01)」。
        2. 如果看到 "R5" 或 "90°" 標註，這是「折彎 (D01)」。
        3. 請忽略尺寸標註線與輔助線，不要把它們當成折彎線。

        請輸出如下 JSON 格式：
        {
        "shape_description": "描述零件形狀 (如 L型支架)",
        "detected_features": {
        "geometry": ["特徵1", "特徵2"],
        "symbols": ["看到的符號文字"]
        },
        "suggested_process_ids": ["F01", "D01"],
        "reasoning": "你的判斷理由 (請引用看到的具體符號)"
        }
    """
    parent_section = ""
    if parent_context:
        parent_section = (
            "【全域規範 (來自父圖/BOM)】\n"
            f"{parent_context}\n"
            "(請注意：子圖的材質與後處理必須遵循上述規範)\n"
            "(重要：分析子圖時，若看到圓形或圓柱外觀，請參考『全域幾何背景』判斷是孔洞還是圓柱，"
            "不要只看單張子圖猜測。)\n\n"
        )

    return f"""
 {parent_section}你是由 AIIA 訓練的專用 AI，只能根據以下代碼表判斷製程，**不可使用外部知識**。
請嚴格遵守代碼表，禁止自行新增或改寫代碼含義。

**重要：語言與術語格式要求**
- 所有輸出必須使用繁體中文(Traditional Chinese)
- 專業術語請使用「中文(英文)」格式，例如：
  * 折彎線(bend line)
  * 焊接符號(welding symbol)
  * 孔洞(hole)
  * 沖孔(punching)
- 在 reasoning 和 shape_description 欄位中也請使用此格式

代碼表 (Knowledge Base)：
- C05: 必須是「沖孔(punching)/M3048」。特徵：圖面上有密集的圓孔、方孔。**絕對不是焊接**。
- F01: 焊接(welding)。特徵：必須看到「△」、「4|4△」符號，或是有箭頭指向兩零件接合處。
- D01: 折彎(bending)。特徵：實線標示的 L 型/U 型結構。

輔助線規則：
- 細線、虛線、帶有數字的引線（如「110」、「30」）是尺寸標註(dimension line)，不是折彎線。**請忽略**。
- 若看到圓形或圓柱外觀，請先查看【全域幾何背景】判斷是孔洞(hole)或圓柱(cylinder)，禁止單張圖猜測。

思維鏈 (CoT) 要求：輸出 JSON 之前，請在 reasoning 欄位中進行「視覺過濾」，並使用中英對照格式描述特徵。
Step 1: 掃描所有線條，區分實線（輪廓, contour）與細線（尺寸標註, dimension line）。
Step 2: 尋找特殊符號（三角形, triangle / R角, radius）。
Step 3: 根據代碼表匹配製程。

請輸出如下 JSON 格式：
{{
  "shape_description": "描述零件形狀 (如 L型支架(L-shaped bracket))",
  "detected_features": {{
    "geometry": ["使用中英對照格式，如：折彎線(bend line)"],
    "symbols": ["看到的符號文字，如：焊接符號(welding symbol)"],
    "text_annotations": ["看到的文字標註"],
    "material_info": "材質資訊或null"
  }},
  "suggested_process_ids": ["F01", "D01"],
  "confidence_scores": {{
    "F01": 0.95
  }},
  "reasoning": "你的判斷理由 (Step 1... Step 2...)，請使用中英對照格式描述特徵",
  "process_sequence": ["F01", "D01"]
}}

輸出格式：保持原本的 JSON 結構，**不要包含任何其他文字**。

```json
{{
  "shape_description": "零件形狀的簡要描述",
  "overall_complexity": "簡單/中等/複雜",
  "detected_features": {{
    "geometry": ["特徵1", "特徵2"],
    "symbols": ["符號1", "符號2"],
    "text_annotations": ["標註1", "標註2"],
    "material_info": "材質資訊或null"
  }},
  "suggested_process_ids": ["C05", "D01", "F01"],
  "confidence_scores": {{
    "C05": 0.95,
    "D01": 0.85,
    "F01": 0.10
  }},
   "reasoning": "請依照 Step 1~3 描述視覺過濾與判斷依據",
  "process_sequence": ["C05", "D01", "F01"]
}}
```
""".strip()



# Export main classes and functions
__all__ = [
    "EngineeringPrompts",
    "PromptTemplate",
    "get_default_prompt"
]
