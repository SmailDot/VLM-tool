"""Contracts for pluggable VLM core service."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union

import numpy as np


ImageLike = Union[str, Path, np.ndarray]


@dataclass
class AnalysisRequest:
    """Unified request model for drawing analysis."""

    image: Optional[ImageLike]
    parent_image: Optional[ImageLike] = None
    child_images: Optional[Sequence[ImageLike]] = None
    view_labels: Optional[List[str]] = None
    bom_context: str = ""
    use_rag: bool = False
    use_vlm: bool = True
    min_confidence: float = 0.25
