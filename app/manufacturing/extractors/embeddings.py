"""
Visual Embedding Extractor for Manufacturing Drawings.

Uses deep learning models (DINOv2, CLIP) to create semantic embeddings
for similarity search and retrieval.
"""

from typing import Optional, Literal
import numpy as np
import cv2
from pathlib import Path

# Try to import PyTorch dependencies (optional feature)
EMBEDDINGS_AVAILABLE = True
IMPORT_ERROR_MSG = None

try:
    import torch
    import timm
    from PIL import Image
except ImportError as e:
    EMBEDDINGS_AVAILABLE = False
    IMPORT_ERROR_MSG = str(e)


class VisualEmbedder:
    """
    Extract visual embeddings from engineering drawings.
    
    Supports:
    - DINOv2 (recommended for technical drawings - better at line/shape features)
    - CLIP (optional - good for multimodal text+image)
    
    Note: This feature requires PyTorch and timm. If unavailable, methods will
    gracefully return None or raise informative errors.
    """
    
    def __init__(
        self,
        model_type: Literal["dinov2", "clip"] = "dinov2",
        model_name: str = "vit_base_patch14_dinov2.lvd142m",
        device: Optional[str] = None
    ):
        """
        Initialize embedding model.
        
        Args:
            model_type: "dinov2" or "clip".
            model_name: Model variant name (for timm or CLIP).
            device: "cuda", "cpu", or None (auto-detect).
        """
        # Check if embeddings are available
        if not EMBEDDINGS_AVAILABLE:
            print(f"Warning: Visual embeddings disabled - PyTorch unavailable ({IMPORT_ERROR_MSG})")
            print("   System will use OCR + Geometry + Symbols only (recommended combination)")
            self.model = None
            self.model_type = model_type
            self.model_name = model_name
            self.device = "cpu"
            return
        
        self.model_type = model_type
        self.model_name = model_name
        
        # Auto-detect device
        if device is None:
            self.device = "cuda" if (EMBEDDINGS_AVAILABLE and torch.cuda.is_available()) else "cpu"
        else:
            self.device = device
        
        # Load model
        if model_type == "dinov2":
            self.model = self._load_dinov2()
        elif model_type == "clip":
            self.model = self._load_clip()
        else:
            raise ValueError(f"Unknown model_type: {model_type}")
        
        if self.model is not None:
            self.model.eval()
    
    def _load_dinov2(self):
        """Load DINOv2 model from timm."""
        if not EMBEDDINGS_AVAILABLE:
            return None
        
        # DINOv2 ViT-Base (recommended for technical drawings)
        # Outputs 768-dim embeddings
        model = timm.create_model(
            self.model_name,
            pretrained=True,
            num_classes=0  # Remove classification head
        )
        model.to(self.device)
        
        # Get data config for preprocessing
        self.data_config = timm.data.resolve_data_config(model.pretrained_cfg)
        self.transform = timm.data.create_transform(**self.data_config, is_training=False)
        
        return model
    
    def _load_clip(self):
        """Load CLIP model (optional)."""
        if not EMBEDDINGS_AVAILABLE:
            return None
        
        try:
            import clip
        except ImportError:
            raise ImportError("CLIP not installed. Run: pip install git+https://github.com/openai/CLIP.git")
        
        model, preprocess = clip.load("ViT-B/32", device=self.device)
        self.transform = preprocess
        return model
    
    def extract(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract embedding vector from image.
        
        Args:
            image: Input image (BGR format from OpenCV).
        
        Returns:
            Embedding vector (numpy array, shape [embedding_dim]) or None if unavailable.
            - DINOv2 ViT-Base: 768-dim
            - CLIP ViT-B/32: 512-dim
        """
        # Return None if embeddings unavailable
        if self.model is None or not EMBEDDINGS_AVAILABLE:
            return None
        
        # Convert BGR to RGB
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            # Grayscale to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Convert to PIL Image
        pil_image = Image.fromarray(image_rgb)
        
        # Preprocess
        input_tensor = self.transform(pil_image).unsqueeze(0).to(self.device)
        
        # Extract features
        with torch.no_grad():
            if self.model_type == "dinov2":
                # DINOv2: forward returns embedding directly
                embedding = self.model(input_tensor)
            elif self.model_type == "clip":
                # CLIP: encode_image returns embedding
                embedding = self.model.encode_image(input_tensor)
            else:
                raise ValueError(f"Unknown model_type: {self.model_type}")
        
        # Convert to numpy
        embedding_np = embedding.cpu().numpy().squeeze()
        
        # Normalize (L2 norm)
        embedding_np = embedding_np / np.linalg.norm(embedding_np)
        
        return embedding_np
    
    def extract_from_file(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract embedding from image file.
        
        Args:
            image_path: Path to image file.
        
        Returns:
            Embedding vector (numpy array) or None if unavailable.
        """
        if self.model is None or not EMBEDDINGS_AVAILABLE:
            return None
        
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        return self.extract(image)
    
    def batch_extract(self, images: list[np.ndarray]) -> Optional[np.ndarray]:
        """
        Extract embeddings for multiple images (batch processing).
        
        Args:
            images: List of images (BGR format).
        
        Returns:
            Embeddings matrix (shape [num_images, embedding_dim]) or None if unavailable.
        """
        if self.model is None or not EMBEDDINGS_AVAILABLE:
            return None
        
        # Preprocess all images
        input_tensors = []
        for image in images:
            # Convert BGR to RGB
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            
            pil_image = Image.fromarray(image_rgb)
            input_tensor = self.transform(pil_image)
            input_tensors.append(input_tensor)
        
        # Stack into batch
        batch = torch.stack(input_tensors).to(self.device)
        
        # Extract features
        with torch.no_grad():
            if self.model_type == "dinov2":
                embeddings = self.model(batch)
            elif self.model_type == "clip":
                embeddings = self.model.encode_image(batch)
            else:
                raise ValueError(f"Unknown model_type: {self.model_type}")
        
        # Convert to numpy
        embeddings_np = embeddings.cpu().numpy()
        
        # Normalize each embedding
        norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
        embeddings_np = embeddings_np / norms
        
        return embeddings_np
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimensionality."""
        if not EMBEDDINGS_AVAILABLE or self.model is None:
            return 0
        
        if self.model_type == "dinov2":
            # DINOv2 ViT-Base: 768
            # DINOv2 ViT-Small: 384
            # DINOv2 ViT-Large: 1024
            if "small" in self.model_name:
                return 384
            elif "large" in self.model_name:
                return 1024
            else:
                return 768
        elif self.model_type == "clip":
            return 512
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")


# Convenience function
def extract_embedding(image: np.ndarray, model_type: str = "dinov2") -> Optional[np.ndarray]:
    """
    Quick embedding extraction without creating embedder object.
    
    Args:
        image: Input image (BGR format).
        model_type: "dinov2" or "clip".
    
    Returns:
        Embedding vector (numpy array) or None if unavailable.
    """
    embedder = VisualEmbedder(model_type=model_type)
    return embedder.extract(image)
