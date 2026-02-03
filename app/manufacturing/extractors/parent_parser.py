"""
Parent Image Parser - 父圖全域資訊提取器

負責從父圖中提取全域資訊:
- 標題欄 (Title Block)
- 技術要求 (Technical Notes)
- 材質資訊 (Material)
- 客戶資訊 (Customer)
- 特殊要求 (Special Requirements)
"""

from typing import Dict, List, Optional, Set
import numpy as np
import cv2
from dataclasses import dataclass

from ..schema import OCRResult


@dataclass
class ParentImageContext:
    """父圖全域資訊"""
    
    # 基本資訊
    material: Optional[str] = None  # 材質 (白鐵、鋁板等)
    thickness: Optional[float] = None  # 厚度 (T)
    customer: Optional[str] = None  # 客戶 (ASML、日本客戶等)
    
    # 特殊要求
    cleanroom_level: Optional[str] = None  # 無塵室等級
    surface_treatment: List[str] = None  # 表面處理 (烤漆、鍍鋅等)
    special_requirements: List[str] = None  # 特殊要求
    
    # 檢測到的關鍵字
    detected_keywords: Set[str] = None  # 所有檢測到的關鍵字
    
    # 原始 OCR 結果
    ocr_results: List[OCRResult] = None
    
    # 預設製程 (由父圖觸發)
    triggered_processes: List[str] = None  # 製程 ID 列表
    
    # NEW: 注意事項 (從標題欄/技術要求區域提取)
    important_notes: List[str] = None  # 重要注意事項
    title_block_text: List[str] = None  # 標題欄所有文字
    detected_languages: Set[str] = None  # 檢測到的語言
    
    def __post_init__(self):
        if self.surface_treatment is None:
            self.surface_treatment = []
        if self.special_requirements is None:
            self.special_requirements = []
        if self.detected_keywords is None:
            self.detected_keywords = set()
        if self.ocr_results is None:
            self.ocr_results = []
        if self.triggered_processes is None:
            self.triggered_processes = []
        if self.important_notes is None:
            self.important_notes = []
        if self.title_block_text is None:
            self.title_block_text = []
        if self.detected_languages is None:
            self.detected_languages = set()


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
