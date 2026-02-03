"""
Manufacturing Process Recognition Pipeline.

End-to-end workflow:
1. Load image (from file or numpy array)
2. Extract multimodal features (OCR, Geometry, Symbols, Visual embeddings)
3. Run decision engine to predict processes
4. Return results with confidence and evidence
"""

from typing import Optional, Union, List
from pathlib import Path
import numpy as np
import cv2
import time

from .schema import (
    ExtractedFeatures,
    RecognitionResult,
    ProcessPrediction
)
from .extractors import (
    OCRExtractor,
    GeometryExtractor,
    SymbolDetector,
    VisualEmbedder,
    PDFImageExtractor,
    is_pdf_available
)
from .extractors.parent_parser import ParentImageParser, ParentImageContext
from .extractors.tolerance_parser import ToleranceParser
from .decision import DecisionEngine
from .decision.engine_v2 import DecisionEngineV2


class ManufacturingPipeline:
    """
    Complete pipeline for engineering drawing process recognition.
    
    Usage:
        pipeline = ManufacturingPipeline()
        result = pipeline.recognize("path/to/drawing.jpg")
        
        # Access predictions
        for pred in result.predictions:
            print(f"{pred.process_name}: {pred.confidence:.2f}")
            print(f"  Evidence: {pred.evidence}")
    """
    
    def __init__(
        self,
        use_ocr: bool = True,
        use_geometry: bool = True,
        use_symbols: bool = True,
        use_visual: bool = False,  # Visual embeddings optional (expensive)
        template_dir: Optional[str] = None,
        process_lib_path: Optional[str] = None,
        use_v2_engine: bool = True  # Use DecisionEngineV2 by default
    ):
        """
        Initialize pipeline.
        
        Args:
            use_ocr: Enable OCR text extraction.
            use_geometry: Enable geometry analysis.
            use_symbols: Enable symbol detection.
            use_visual: Enable visual embedding (DINOv2).
            template_dir: Directory for symbol templates.
            process_lib_path: Path to process_lib.json or process_lib_v2.json.
            use_v2_engine: Use DecisionEngineV2 (supports logic rules).
        """
        self.use_ocr = use_ocr
        self.use_geometry = use_geometry
        self.use_symbols = use_symbols
        self.use_visual = use_visual
        
        # Initialize extractors
        self.ocr_extractor = OCRExtractor() if use_ocr else None
        self.geometry_extractor = GeometryExtractor() if use_geometry else None
        self.symbol_detector = SymbolDetector(template_dir) if use_symbols else None
        self.visual_embedder = VisualEmbedder() if use_visual else None
        
        # Initialize parent image parser
        self.parent_parser = ParentImageParser(self.ocr_extractor)
        
        # Initialize PDF extractor (if available)
        self.pdf_extractor = None
        if is_pdf_available():
            try:
                self.pdf_extractor = PDFImageExtractor(target_dpi=300)
            except ImportError:
                pass  # PDF功能不可用
        
        # Initialize decision engine (v2 by default)
        if use_v2_engine:
            self.decision_engine = DecisionEngineV2(process_lib_path)
        else:
            self.decision_engine = DecisionEngine(process_lib_path)
    
    def recognize(
        self,
        image: Union[str, np.ndarray],
        parent_image: Optional[Union[str, np.ndarray]] = None,
        top_n: int = 5,
        min_confidence: float = 0.3,
        ocr_threshold: float = 0.5,
        symbol_threshold: float = 0.6,
        frequency_filter: Optional[List[str]] = None
    ) -> RecognitionResult:
        """
        Recognize manufacturing processes from engineering drawing.
        
        Args:
            image: Child image file path or numpy array (BGR). REQUIRED.
            parent_image: Parent image file path or numpy array (BGR). OPTIONAL.
                         Contains global information (title block, technical notes, etc.)
            top_n: Return top N process predictions.
            min_confidence: Minimum confidence threshold for predictions.
            ocr_threshold: Minimum confidence for OCR detections.
            symbol_threshold: Minimum confidence for symbol detections.
            frequency_filter: List of frequencies to include (e.g., ["高", "中"]).
                            If None, all frequencies are included.
        
        Returns:
            RecognitionResult with predictions and diagnostics.
        """
        start_time = time.time()
        
        # Parse parent image (optional)
        parent_context = None
        if parent_image is not None:
            # Load parent image (支援 PDF)
            if isinstance(parent_image, str):
                if parent_image.lower().endswith('.pdf') and self.pdf_extractor:
                    # PDF → 高解析度圖片
                    try:
                        parent_img_array = self.pdf_extractor.extract_full_page(parent_image, page_num=0)
                    except Exception as e:
                        raise ValueError(f"Failed to extract parent image from PDF: {e}")
                else:
                    # 一般圖片檔案
                    parent_img_array = cv2.imread(parent_image)
                    if parent_img_array is None:
                        raise ValueError(f"Failed to load parent image: {parent_image}")
            else:
                parent_img_array = parent_image
            
            # Parse parent image for global context
            parent_context = self.parent_parser.parse(
                parent_img_array,
                ocr_threshold
            )
        
        # Load child image (required)
        # 支援 PDF 檔案自動轉換
        if isinstance(image, str):
            image_path = image
            if image.lower().endswith('.pdf') and self.pdf_extractor:
                # PDF → 高解析度圖片
                try:
                    img_array = self.pdf_extractor.extract_full_page(image, page_num=0)
                except Exception as e:
                    raise ValueError(f"Failed to extract image from PDF: {e}")
            else:
                # 一般圖片檔案
                img_array = cv2.imread(image)
                if img_array is None:
                    raise ValueError(f"Failed to load image: {image}")
        else:
            img_array = image
            image_path = None
        
        # Extract features from child image
        features = self._extract_features(
            img_array,
            ocr_threshold,
            symbol_threshold
        )
        
        # Run decision engine (pass parent_context if available)
        predictions = self.decision_engine.predict(
            features,
            parent_context=parent_context,
            top_n=top_n,
            min_confidence=min_confidence,
            frequency_filter=frequency_filter
        )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Create result (include parent_context if available)
        result = RecognitionResult(
            predictions=predictions,
            features=features,
            parent_context=parent_context,
            total_time=processing_time
        )
        
        return result
    
    def _extract_features(
        self,
        image: np.ndarray,
        ocr_threshold: float,
        symbol_threshold: float
    ) -> ExtractedFeatures:
        """
        Extract all features from image.
        
        Args:
            image: Input image (BGR).
            ocr_threshold: OCR confidence threshold.
            symbol_threshold: Symbol confidence threshold.
        
        Returns:
            ExtractedFeatures object.
        """
        # OCR extraction
        ocr_results = []
        if self.use_ocr and self.ocr_extractor:
            ocr_results = self.ocr_extractor.extract(image, ocr_threshold)
        
        # Tolerance extraction from OCR results (NEW!)
        tolerances = []
        if ocr_results:
            tolerance_parser = ToleranceParser()
            tolerances = tolerance_parser.extract_tolerances(ocr_results)
        
        # Geometry extraction (pass OCR results for dimension line filtering)
        geometry = None
        if self.use_geometry and self.geometry_extractor:
            geometry = self.geometry_extractor.extract(image, ocr_results=ocr_results)
        
        # Symbol detection
        symbols = []
        if self.use_symbols and self.symbol_detector:
            symbols = self.symbol_detector.detect(image, symbol_threshold)
        
        # Visual embedding
        visual_embedding = None
        if self.use_visual and self.visual_embedder:
            visual_embedding = self.visual_embedder.extract(image)
        
        return ExtractedFeatures(
            ocr_results=ocr_results,
            geometry=geometry,
            symbols=symbols,
            visual_embedding=visual_embedding,
            tolerances=tolerances  # NEW!
        )
    
    def batch_recognize(
        self,
        images: List[Union[str, np.ndarray]],
        **kwargs
    ) -> List[RecognitionResult]:
        """
        Batch process multiple images.
        
        Args:
            images: List of image paths or numpy arrays.
            **kwargs: Additional arguments for recognize().
        
        Returns:
            List of RecognitionResult objects.
        """
        results = []
        for image in images:
            try:
                result = self.recognize(image, **kwargs)
                results.append(result)
            except Exception as e:
                # Create error result
                results.append(RecognitionResult(
                    predictions=[],
                    extracted_features=ExtractedFeatures(
                        ocr_results=[],
                        geometry=None,
                        symbols=[],
                        visual_embedding=None
                    ),
                    image_path=str(image) if isinstance(image, str) else None,
                    processing_time=0.0,
                    diagnostics={"error": str(e)}
                ))
        
        return results
    
    def visualize_features(
        self,
        image: Union[str, np.ndarray],
        show_ocr: bool = True,
        show_geometry: bool = True,
        show_symbols: bool = True
    ) -> np.ndarray:
        """
        Visualize extracted features on image (for debugging).
        
        Args:
            image: Input image path or numpy array.
            show_ocr: Draw OCR bounding boxes.
            show_geometry: Draw geometry features.
            show_symbols: Draw symbol detections.
        
        Returns:
            Image with drawn features.
        """
        # Load image
        if isinstance(image, str):
            img_array = cv2.imread(image)
            if img_array is None:
                raise ValueError(f"Failed to load image: {image}")
        else:
            img_array = image.copy()
        
        # Extract features
        features = self._extract_features(img_array, 0.5, 0.6)
        
        # Draw features
        vis_image = img_array.copy()
        
        if show_geometry and features.geometry and self.geometry_extractor:
            vis_image = self.geometry_extractor.visualize(vis_image, features.geometry)
        
        if show_symbols and features.symbols and self.symbol_detector:
            vis_image = self.symbol_detector.visualize(vis_image, features.symbols)
        
        if show_ocr and features.ocr_results and self.ocr_extractor:
            vis_image = self.ocr_extractor.visualize(vis_image, features.ocr_results)
        
        return vis_image


# Convenience function
def recognize(
    image: Union[str, np.ndarray],
    top_n: int = 5
) -> RecognitionResult:
    """
    Quick recognition without creating pipeline object.
    
    Args:
        image: Image file path or numpy array.
        top_n: Return top N predictions.
    
    Returns:
        RecognitionResult object.
    """
    pipeline = ManufacturingPipeline()
    return pipeline.recognize(image, top_n=top_n)
