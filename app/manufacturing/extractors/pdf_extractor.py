"""
PDF Image Extractor - PDF 高解析度圖片提取器

從 PDF 工程圖紙提取高解析度圖片，解決手動截圖模糊問題。

功能：
- 從 PDF 直接渲染高 DPI 圖片（300-600 DPI）
- 精確裁切指定區域（子圖提取）
- 避免螢幕顯示造成的二次取樣損失

作者：NKUST 視覺實驗室
日期：2026-02-03
"""

from typing import Tuple, Optional, Dict, Any
from pathlib import Path
import numpy as np
import cv2

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class PDFImageExtractor:
    """
    從 PDF 提取高解析度圖片（替代手動截圖）
    
    解決問題：
    - 手動截圖（螢幕 96 DPI）→ 模糊 → OCR 失敗
    - PDF 直接渲染（300+ DPI）→ 清晰 → OCR 成功
    
    Usage:
        extractor = PDFImageExtractor(target_dpi=300)
        
        # 提取完整頁面（父圖）
        parent_img = extractor.extract_full_page("drawing.pdf", page_num=0)
        
        # 提取指定區域（子圖）
        child_img = extractor.extract_region(
            "drawing.pdf", 
            page_num=0,
            bbox=(0.1, 0.2, 0.5, 0.6)  # 歸一化座標
        )
    """
    
    def __init__(self, target_dpi: int = 300):
        """
        初始化 PDF 圖片提取器
        
        Args:
            target_dpi: 目標解析度（DPI）
                - 150 DPI: 快速預覽
                - 300 DPI: 標準品質（推薦）
                - 600 DPI: 高品質（檔案較大）
        
        Raises:
            ImportError: 如果 PyMuPDF 未安裝
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError(
                "PyMuPDF 未安裝。請執行: pip install pymupdf"
            )
        
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow 未安裝。請執行: pip install pillow"
            )
        
        self.target_dpi = target_dpi
        self.zoom_factor = target_dpi / 72.0  # PDF 預設 72 DPI
    
    def extract_full_page(
        self,
        pdf_path: str,
        page_num: int = 0,
        alpha: bool = False
    ) -> np.ndarray:
        """
        提取 PDF 完整頁面（父圖）
        
        Args:
            pdf_path: PDF 檔案路徑
            page_num: 頁碼（從 0 開始）
            alpha: 是否包含透明通道（通常不需要）
        
        Returns:
            BGR 格式的 numpy array (H, W, 3)
        
        Raises:
            FileNotFoundError: PDF 檔案不存在
            ValueError: 頁碼超出範圍
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 檔案不存在: {pdf_path}")
        
        # 開啟 PDF
        doc = fitz.open(str(pdf_path))
        
        # 檢查頁碼
        if page_num >= len(doc):
            doc.close()
            raise ValueError(
                f"頁碼 {page_num} 超出範圍（PDF 共 {len(doc)} 頁）"
            )
        
        page = doc[page_num]
        
        # 高解析度渲染
        mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
        pix = page.get_pixmap(matrix=mat, alpha=alpha)
        
        # 轉換為 numpy array
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_array = np.array(img)
        
        # 轉換為 BGR（OpenCV 格式）
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        doc.close()
        
        return img_bgr
    
    def extract_region(
        self,
        pdf_path: str,
        page_num: int,
        bbox: Tuple[float, float, float, float],
        alpha: bool = False
    ) -> np.ndarray:
        """
        從 PDF 提取指定區域（子圖）- 高解析度
        
        **重點功能**：這個方法取代手動截圖！
        
        Args:
            pdf_path: PDF 檔案路徑
            page_num: 頁碼（從 0 開始）
            bbox: 邊界框（歸一化座標 0-1）
                  格式: (x0, y0, x1, y1)
                  - x0, y0: 左上角（比例）
                  - x1, y1: 右下角（比例）
                  
                  範例：
                  (0.0, 0.0, 1.0, 1.0) = 完整頁面
                  (0.1, 0.2, 0.5, 0.6) = 左上角 10%,20% 到 50%,60%
            
            alpha: 是否包含透明通道
        
        Returns:
            裁切後的高解析度圖片（BGR）
        
        Raises:
            FileNotFoundError: PDF 檔案不存在
            ValueError: 頁碼或座標無效
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 檔案不存在: {pdf_path}")
        
        # 驗證 bbox
        x0, y0, x1, y1 = bbox
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError(
                f"無效的 bbox 座標: {bbox}。座標必須在 [0, 1] 範圍內且 x0<x1, y0<y1"
            )
        
        # 開啟 PDF
        doc = fitz.open(str(pdf_path))
        
        # 檢查頁碼
        if page_num >= len(doc):
            doc.close()
            raise ValueError(
                f"頁碼 {page_num} 超出範圍（PDF 共 {len(doc)} 頁）"
            )
        
        page = doc[page_num]
        
        # 轉換為實際座標（PDF points）
        page_rect = page.rect
        actual_x0 = page_rect.x0 + x0 * page_rect.width
        actual_y0 = page_rect.y0 + y0 * page_rect.height
        actual_x1 = page_rect.x0 + x1 * page_rect.width
        actual_y1 = page_rect.y0 + y1 * page_rect.height
        
        clip_rect = fitz.Rect(actual_x0, actual_y0, actual_x1, actual_y1)
        
        # 高解析度渲染指定區域
        mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
        pix = page.get_pixmap(matrix=mat, clip=clip_rect, alpha=alpha)
        
        # 轉換為 numpy array
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_array = np.array(img)
        
        # 轉換為 BGR（OpenCV 格式）
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        doc.close()
        
        return img_bgr
    
    def extract_with_pixel_coords(
        self,
        pdf_path: str,
        page_num: int,
        pixel_bbox: Tuple[int, int, int, int],
        reference_dpi: int = 72
    ) -> np.ndarray:
        """
        使用像素座標提取區域（方便從預覽圖上選取）
        
        工作流程：
        1. 以低解析度（72 DPI）顯示 PDF 預覽
        2. 使用者在預覽上框選區域（像素座標）
        3. 用此方法以高解析度提取該區域
        
        Args:
            pdf_path: PDF 檔案路徑
            page_num: 頁碼
            pixel_bbox: 像素座標 (x0, y0, x1, y1)
            reference_dpi: 預覽圖的 DPI（預設 72）
        
        Returns:
            高解析度圖片（BGR）
        """
        # 開啟 PDF 取得頁面尺寸
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]
        page_rect = page.rect
        doc.close()
        
        # 計算縮放比例
        zoom = reference_dpi / 72.0
        preview_width = page_rect.width * zoom
        preview_height = page_rect.height * zoom
        
        # 轉換像素座標為歸一化座標
        px0, py0, px1, py1 = pixel_bbox
        norm_x0 = px0 / preview_width
        norm_y0 = py0 / preview_height
        norm_x1 = px1 / preview_width
        norm_y1 = py1 / preview_height
        
        # 限制在 [0, 1] 範圍
        norm_bbox = (
            max(0.0, min(1.0, norm_x0)),
            max(0.0, min(1.0, norm_y0)),
            max(0.0, min(1.0, norm_x1)),
            max(0.0, min(1.0, norm_y1))
        )
        
        # 使用歸一化座標提取
        return self.extract_region(pdf_path, page_num, norm_bbox)
    
    def get_page_info(self, pdf_path: str, page_num: int = 0) -> Dict[str, Any]:
        """
        取得 PDF 頁面資訊
        
        Args:
            pdf_path: PDF 檔案路徑
            page_num: 頁碼
        
        Returns:
            頁面資訊字典:
            {
                'width': 頁面寬度（points）,
                'height': 頁面高度（points）,
                'width_inches': 寬度（英吋）,
                'height_inches': 高度（英吋）,
                'output_width': 輸出圖片寬度（pixels）,
                'output_height': 輸出圖片高度（pixels）,
                'dpi': 目標 DPI
            }
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 檔案不存在: {pdf_path}")
        
        doc = fitz.open(str(pdf_path))
        
        if page_num >= len(doc):
            doc.close()
            raise ValueError(
                f"頁碼 {page_num} 超出範圍（PDF 共 {len(doc)} 頁）"
            )
        
        page = doc[page_num]
        rect = page.rect
        
        info = {
            'width': rect.width,
            'height': rect.height,
            'width_inches': rect.width / 72.0,
            'height_inches': rect.height / 72.0,
            'output_width': int(rect.width * self.zoom_factor),
            'output_height': int(rect.height * self.zoom_factor),
            'dpi': self.target_dpi
        }
        
        doc.close()
        
        return info
    
    def get_preview_image(
        self,
        pdf_path: str,
        page_num: int = 0,
        preview_dpi: int = 72
    ) -> np.ndarray:
        """
        取得低解析度預覽圖（用於 UI 顯示和區域選擇）
        
        Args:
            pdf_path: PDF 檔案路徑
            page_num: 頁碼
            preview_dpi: 預覽解析度（預設 72 DPI，速度快）
        
        Returns:
            預覽圖片（BGR）
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 檔案不存在: {pdf_path}")
        
        doc = fitz.open(str(pdf_path))
        
        if page_num >= len(doc):
            doc.close()
            raise ValueError(
                f"頁碼 {page_num} 超出範圍（PDF 共 {len(doc)} 頁）"
            )
        
        page = doc[page_num]
        
        # 低解析度渲染
        zoom = preview_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # 轉換
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_array = np.array(img)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        doc.close()
        
        return img_bgr


def is_pdf_available() -> bool:
    """
    檢查 PyMuPDF 是否可用
    
    Returns:
        True if PyMuPDF is installed, False otherwise
    """
    return PYMUPDF_AVAILABLE


# Convenience function
def extract_from_pdf(
    pdf_path: str,
    page_num: int = 0,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    target_dpi: int = 300
) -> np.ndarray:
    """
    快速從 PDF 提取圖片（無需建立 extractor 物件）
    
    Args:
        pdf_path: PDF 檔案路徑
        page_num: 頁碼
        bbox: 歸一化邊界框（None = 完整頁面）
        target_dpi: 目標解析度
    
    Returns:
        圖片（BGR）
    """
    extractor = PDFImageExtractor(target_dpi=target_dpi)
    
    if bbox is None:
        return extractor.extract_full_page(pdf_path, page_num)
    else:
        return extractor.extract_region(pdf_path, page_num, bbox)
