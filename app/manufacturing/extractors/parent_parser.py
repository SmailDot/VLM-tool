"""
Parent Image Parser - 父圖全域資訊提取器

負責從父圖中提取全域資訊:
- 標題欄 (Title Block)
- 技術要求 (Technical Notes)
- 材質資訊 (Material)
- 客戶資訊 (Customer)
- 特殊要求 (Special Requirements)
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any

import cv2
import numpy as np

from ..schema import OCRResult
from .vlm_client import VLMClient


@dataclass
class ParentImageContext:
    """父圖全域資訊"""
    
    # 基本資訊
    material: Optional[str] = None  # 材質 (白鐵、鋁板等)
    thickness: Optional[float] = None  # 厚度 (T)
    customer: Optional[str] = None  # 客戶 (ASML、日本客戶等)
    
    # 特殊要求
    cleanroom_level: Optional[str] = None  # 無塵室等級
    surface_treatment: List[str] = field(default_factory=list)  # 表面處理 (烤漆、鍍鋅等)
    special_requirements: List[str] = field(default_factory=list)  # 特殊要求
    
    # 檢測到的關鍵字
    detected_keywords: Set[str] = field(default_factory=set)  # 所有檢測到的關鍵字
    
    # 原始 OCR 結果
    ocr_results: List[OCRResult] = field(default_factory=list)
    
    # 預設製程 (由父圖觸發)
    triggered_processes: List[str] = field(default_factory=list)  # 製程 ID 列表
    
    # NEW: 注意事項 (從標題欄/技術要求區域提取)
    important_notes: List[str] = field(default_factory=list)  # 重要注意事項
    title_block_text: List[str] = field(default_factory=list)  # 標題欄所有文字
    detected_languages: Set[str] = field(default_factory=set)  # 檢測到的語言

    # NEW: VLM 全域分析（3D 結構與加工特徵）
    vlm_context: Dict[str, Any] = field(default_factory=dict)


class ParentImageParser:
    """
    父圖解析器
    
    依據 ChatGPT.txt 的邏輯:
    1. 掃描標題欄、技術要求、全視圖
    2. 提取材質、客戶、特殊要求
    3. 根據關鍵字觸發預設製程
    """
    
    def __init__(self, ocr_extractor=None):
        """
        初始化父圖解析器
        
        Args:
            ocr_extractor: OCR 提取器實例
        """
        self.ocr_extractor = ocr_extractor
        self.vlm_client = VLMClient()
        
        # 定義關鍵字規則 (來自 ChatGPT.txt)
        self.keyword_rules = {
            # 材質相關
            "material": {
                "白鐵": ["白鐵", "stainless", "SUS", "304", "316"],
                "鋁板": ["鋁", "aluminum", "AL"],
                "鐵板": ["鐵板", "iron", "steel"]
            },
            # 客戶相關
            "customer": {
                "ASML": ["ASML", "asml"],
                "日本客戶": ["日本", "japan", "JP"]
            },
            # 無塵室
            "cleanroom": ["無塵室", "cleanroom", "clean room", "class", "等級"],
            # 表面處理
            "surface_treatment": {
                "烤漆": ["烤漆", "powder coating", "塗裝"],
                "鍍鋅": ["鍍鋅", "galvanize", "zinc"],
                "陽極": ["陽極", "anodize"],
                "鈍化": ["鈍化", "passivation"]
            },
            # 特殊要求
            "special": {
                "三價鉻": ["三價鉻", "trivalent chromium", "CR3", "Cr(III)"],
                "鉻酸鹽": ["鉻酸鹽", "chromate", "CR6"],
                "不烤漆": ["不烤漆", "防烤", "遮蔽", "mask"],
                "測漏": ["測漏", "leak test", "不可漏水", "防水"],
                "保壓": ["保壓", "pressure test"],
                "無塵": ["無塵", "clean"]
            }
        }
        
        # 預設製程 (來自 ChatGPT.txt)
        self.default_processes = ["B01", "B02", "E01", "I01", "H02", "J01"]
    
    def parse(
        self,
        parent_image: np.ndarray,
        ocr_threshold: float = 0.5,
        scan_title_block: bool = True
    ) -> ParentImageContext:
        """
        解析父圖，提取全域資訊
        
        Args:
            parent_image: 父圖 numpy array (BGR)
            ocr_threshold: OCR 信心度門檻
            scan_title_block: 是否掃描標題欄區域 (右下角)
        
        Returns:
            ParentImageContext 包含全域資訊
        """
        context = ParentImageContext()
        
        # 1. 執行 OCR (如果有) - 使用多語言支持
        if self.ocr_extractor:
            # 全圖 OCR (多語言)
            context.ocr_results = self.ocr_extractor.extract_multilang(
                parent_image,
                languages=['chinese_cht', 'ch', 'en', 'japan', 'korean'],
                confidence_threshold=ocr_threshold,
                translate_to_chinese=False
            )
            
            # 記錄檢測到的語言
            for result in context.ocr_results:
                if hasattr(result, 'metadata') and 'language' in result.metadata:
                    context.detected_languages.add(result.metadata['language'])
            
            # 掃描標題欄區域 (右下角) 提取注意事項
            if scan_title_block:
                title_block_data = self.ocr_extractor.detect_title_block_notes(
                    parent_image,
                    scan_bottom_right=True,
                    region_ratio=0.25,
                    confidence_threshold=ocr_threshold
                )
                
                context.title_block_text = title_block_data['raw_texts']
                context.important_notes = title_block_data['important_notes']
        
        # 2. 提取文字內容 (全圖 + 標題欄)
        all_text = " ".join([ocr.text for ocr in context.ocr_results])
        title_block_text = " ".join(context.title_block_text)
        detected_text = (all_text + " " + title_block_text).lower()
        
        # 3. 解析材質
        context.material = self._detect_material(detected_text)
        
        # 4. 解析客戶
        context.customer = self._detect_customer(detected_text)
        
        # 5. 解析無塵室等級
        context.cleanroom_level = self._detect_cleanroom(detected_text)
        
        # 6. 解析表面處理
        context.surface_treatment = self._detect_surface_treatment(detected_text)
        
        # 7. 解析特殊要求
        context.special_requirements = self._detect_special_requirements(detected_text)
        
        # 8. 收集所有檢測到的關鍵字
        context.detected_keywords = self._collect_keywords(detected_text)
        
        # 9. 根據父圖資訊觸發預設製程
        context.triggered_processes = self._trigger_processes(context)
        
        return context

    def analyze_parent_context(self, image: np.ndarray) -> str:
        """
        Analyze parent drawing/BOM with VLM to extract global constraints.

        Args:
            image: Parent image as numpy array (BGR).

        Returns:
            str: Context text extracted from parent drawing.
        """
        if not self.vlm_client or not self.vlm_client.is_available():
            return ""

        prompt = """
你是一位製造工程助理。這是一張組立圖或 BOM 表。
請不要分析製程，而是提取全域規範與幾何結構資訊：
1. 材質資訊
2. 表面處理要求（如酸洗、烤漆）
3. 特殊註記或注意事項
4. 幾何結構分析：請分析父圖中的三視圖 (Top/Front/Side Views)。
   請描述此零件的 3D 立體形狀是什麼？(例如：L型板金、U型槽、圓柱體、封閉盒體)。
5. 請找出圖面上的特殊加工特徵（如：沉頭孔、攻牙、焊接肋條）。

請輸出 JSON 格式（僅輸出 JSON，不要包含其他文字）：
{
  "material_spec": "...",
  "3d_structure": "描述零件的立體形狀...",
  "global_features": ["特徵A", "特徵B"],
  "bom_notes": "..."
}
""".strip()

        try:
            result = self.vlm_client.analyze_image(
                image_path=image,
                prompt=prompt,
                response_format="json",
                temperature=0.0,
                max_tokens=800
            )
            if isinstance(result, dict):
                global_features = result.get("global_features")
                if isinstance(global_features, str):
                    global_features = [global_features]
                elif not isinstance(global_features, list):
                    global_features = []

                structured_result = {
                    "material_spec": result.get("material_spec") or result.get("material") or "",
                    "3d_structure": result.get("3d_structure") or "",
                    "global_features": global_features,
                    "bom_notes": result.get("bom_notes") or ""
                }
                return json.dumps(structured_result, ensure_ascii=False)
            return ""
        except Exception as e:
            print(f"Warning: Parent VLM analysis failed: {e}")
            return ""
    
    def _detect_material(self, text: str) -> Optional[str]:
        """檢測材質"""
        for material, keywords in self.keyword_rules["material"].items():
            if any(kw in text for kw in [k.lower() for k in keywords]):
                return material
        return None
    
    def _detect_customer(self, text: str) -> Optional[str]:
        """檢測客戶"""
        for customer, keywords in self.keyword_rules["customer"].items():
            if any(kw in text for kw in [k.lower() for k in keywords]):
                return customer
        return None
    
    def _detect_cleanroom(self, text: str) -> Optional[str]:
        """檢測無塵室等級"""
        keywords = self.keyword_rules["cleanroom"]
        if any(kw in text for kw in [k.lower() for k in keywords]):
            return "detected"  # 簡化: 只檢測是否有提到無塵室
        return None
    
    def _detect_surface_treatment(self, text: str) -> List[str]:
        """檢測表面處理"""
        treatments = []
        for treatment, keywords in self.keyword_rules["surface_treatment"].items():
            if any(kw in text for kw in [k.lower() for k in keywords]):
                treatments.append(treatment)
        return treatments
    
    def _detect_special_requirements(self, text: str) -> List[str]:
        """檢測特殊要求"""
        requirements = []
        for req, keywords in self.keyword_rules["special"].items():
            if any(kw in text for kw in [k.lower() for k in keywords]):
                requirements.append(req)
        return requirements
    
    def _collect_keywords(self, text: str) -> Set[str]:
        """收集所有檢測到的關鍵字"""
        keywords = set()
        
        # 檢查所有規則中的關鍵字
        for category, rules in self.keyword_rules.items():
            if isinstance(rules, dict):
                for subcategory, kw_list in rules.items():
                    for kw in kw_list:
                        if kw.lower() in text:
                            keywords.add(kw)
            elif isinstance(rules, list):
                for kw in rules:
                    if kw.lower() in text:
                        keywords.add(kw)
        
        return keywords
    
    def _trigger_processes(self, context: ParentImageContext) -> List[str]:
        """
        根據父圖資訊觸發預設製程
        
        邏輯來自 ChatGPT.txt:
        - 預設: B01, B02, E01, I01, H02, J01
        - 無塵室 → H26, H27, I19 (或 H31)
        - ASML → H32
        - 日本客戶 → O12
        - 三價鉻 → H33 + H34
        - 鉻酸鹽 → Q04
        - 不烤漆/遮蔽 → Q07
        - 白鐵+焊接+無烤漆 → H01
        """
        processes = self.default_processes.copy()
        
        # 無塵室邏輯
        if context.cleanroom_level:
            if "清潔" in context.special_requirements and "包裝" in " ".join(context.surface_treatment + context.special_requirements):
                processes.append("H31")  # 無塵室清潔/包裝
            else:
                processes.extend(["H26", "H27", "I19"])
        
        # 客戶特定
        if context.customer == "ASML":
            processes.append("H32")  # 整理清潔
        if context.customer == "日本客戶":
            processes.append("O12")  # 疊板裝箱
        
        # 化學要求
        if "三價鉻" in context.special_requirements:
            processes.extend(["H33", "H34"])
        if "鉻酸鹽" in context.special_requirements:
            processes.append("Q04")
        
        # 表處遮蔽
        if "不烤漆" in context.special_requirements:
            processes.append("Q07")
        
        # 除焦洗淨邏輯 (材質=白鐵 AND 有焊接 AND 無烤漆)
        # 注意: 焊接資訊來自子圖，這裡先預留
        if context.material == "白鐵" and "烤漆" not in context.surface_treatment:
            # 標記為潛在需要 H01 (需等子圖確認有焊接)
            pass
        
        return list(set(processes))  # 去重
