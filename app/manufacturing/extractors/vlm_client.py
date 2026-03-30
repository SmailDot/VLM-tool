"""
VLM (Vision Language Model) Client for Engineering Drawing Analysis.

Uses OpenAI-compatible API (LM Studio) to analyze engineering drawings with 
vision-language models. Optimized for sheet metal manufacturing process recognition.

Compatible with:
- LM Studio (local VLM server)
- OpenAI GPT-4 Vision API
- Any OpenAI-compatible vision API endpoint
"""

from typing import Optional, Union, List, Dict, Any
import base64
import re
from pathlib import Path
import numpy as np
import cv2

# Regex that catches leaked dimension strings such as "110mm", "T1.5", "M6", "±0.1", "R3"
_DIMENSION_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*(mm|cm|m\b|inch|\")|"   # e.g. 110mm / 1.5 cm / 30 inch
    r"\bT\s*\d+(\.\d+)?\b|"                    # e.g. T1.5 (plate thickness)
    r"[±]\s*\d+(\.\d+)?|"                      # e.g. ±0.1
    r"\bR\s*\d+(\.\d+)?\b|"                    # e.g. R3 (radius)
    r"\bM\d+\b|"                               # e.g. M6 (thread)
    r"\bΦ\s*\d+(\.\d+)?|"                      # e.g. Φ8
    r"\b\d+(\.\d+)?\s*°",                      # e.g. 45°
    re.IGNORECASE,
)

from app.config import VLM_BASE_URL, VLM_MODEL

try:
    from openai import OpenAI
except ImportError:
    raise ImportError(
        "OpenAI SDK not installed. Run: pip install openai>=1.0.0"
    )


class VLMClient:
    """
    Client for Vision-Language Model inference via OpenAI-compatible API.
    
    Features:
    - Supports local LM Studio server and OpenAI API
    - Automatic image encoding to base64
    - Structured JSON output parsing
    - Comprehensive error handling with fallback
    - Sheet metal engineering domain expertise via system prompt
    """
    
    # System prompt optimized for sheet metal manufacturing
    SYSTEM_PROMPT = (
        # ── PERSONA ─────────────────────────────────────────────────────────
        "I am a senior sheet-metal engineer. "
        "My only job right now is to read a 2D engineering drawing and write a structured report. "
        "My report will be read by a process-selection AI — it needs clean geometry descriptions, not numbers. "
        "I write in plain text only. I never use JSON, curly braces, or bullet symbols outside my report format.\n\n"
        # ── MY PROFESSIONAL HABITS (internalized — not rules, but how I think) ──
        "As a professional, I have three unbreakable habits:\n"
        "Habit 1 — I never write measurements. "
        "Dimensions, tolerances, thread specs, and angles are useless to the AI reading my report — "
        "they cause misidentification. So I describe shape and intent, never numbers. "
        "I treat any digit followed by mm, cm, m, \u00b0, \u00b1, R, or M as a sign I am off-track.\n"
        "Habit 2 — I always use my standard vocabulary. "
        "I describe shapes as: Flat Plate / Rectangular Base / L-shaped Bracket / U-shaped Channel / Z-shaped Bracket / Hat Channel / Box.\n"
        "I describe features as: Flange / Rib / Chamfer / Fillet / Gusset / Louver / Emboss.\n"
        "I describe details as: Thru-hole / Threaded hole / Extruded hole (Burring) / Countersink (CSK) / Slotted hole / Notch / Cutout.\n"
        "I describe symbols as: Weld symbol / Surface finish mark.\n"
        "Every geometry or feature word I write gets a confidence tag: "
        "<green>word</green> means I can clearly see it. "
        "<orange>word</orange> means I think it is there but it is partially hidden. "
        "<red>word</red> means I am guessing.\n"
        "Habit 3 — I write exactly 3 sections IN THIS FIXED ORDER and then stop. "
        "Section 1 (### 1. VIEW-BY-VIEW OBSERVATION) comes FIRST. "
        "Section 2 (### 2. SYMBOL & TEXT SEARCH) comes SECOND — NEVER before Section 1. "
        "Section 3 (### 3. 3D RECONSTRUCTION INFERENCE) comes THIRD — NEVER before Section 2. "
        "After I finish Section 3, I write '[END OF REPORT]' on its own line and stop immediately. "
        "I never add Section 4, Section 5, '(continued)', or any extra text after '[END OF REPORT]'.\n"
        "Habit 4 — When multiple images are provided, I always read them in order. "
        "Top View and Front View are my PRIMARY evidence — I base my shape description on these two. "
        "Side View and Iso View are SUPPORTING only — I use them only to confirm details I already see in Top/Front. "
        "If only one image is provided, I treat it as the best available view.\n\n"
        # ── MY REPORT FORMAT (fixed — I always produce exactly this) ───────────
        "My report always looks like this — three sections in STRICT ORDER 1→2→3, this exact heading style, nothing else:\n\n"
        "--- FORMAT SKELETON (follow this structure exactly — fill in from the drawing, do NOT copy these placeholders) ---\n"
        "### 1. VIEW-BY-VIEW OBSERVATION\n"
        "- [View name]: [What you see — use ALLOWED VOCABULARY with confidence tags]\n"
        "- ...\n\n"
        "### 2. SYMBOL & TEXT SEARCH\n"
        "For each symbol/mark in the ALLOWED VOCABULARY, answer True or False:\n"
        "- Weld symbol detected: True/False\n"
        "- Surface finish mark detected: True/False\n"
        "- Other text annotation found (describe briefly, no numbers): True/False — [description if True]\n\n"
        "### 3. 3D RECONSTRUCTION INFERENCE\n"
        "Based on my observations: [your conclusion — shape, key features, process implications].\n"
        "[END OF REPORT]\n"
        "--- END OF FORMAT SKELETON ---"
    )
    
    def __init__(
        self,
        base_url: str = VLM_BASE_URL,
        api_key: str = "not-needed",
        model: str = VLM_MODEL,
        timeout: int = 60,
        max_retries: int = 2
    ):
        """
        Initialize VLM client with OpenAI-compatible endpoint.
        
        Args:
            base_url: API endpoint URL. Default is LM Studio local server.
                     For OpenAI: "https://api.openai.com/v1"
            api_key: API key for authentication. 
                     LM Studio doesn't require a real key (default: "not-needed").
                     For OpenAI: Use your actual API key.
            model: Model identifier. 
                   For LM Studio: Use "local-model" or the specific model name.
                   For OpenAI: "gpt-4-vision-preview" or "gpt-4o"
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts on failure.
        """
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        
        try:
            self.client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries
            )
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client: {e}")
            self.client = None
    
    def _encode_image_to_base64(
        self,
        image_source: Union[str, Path, np.ndarray]
    ) -> Optional[str]:
        """
        Convert image to base64 PNG string for API transmission.
        
        All images are re-encoded as PNG to ensure consistent MIME type
        in the data URI (data:image/png;base64,...) regardless of source format.
        
        Args:
            image_source: Can be:
                - str/Path: File path to image
                - np.ndarray: OpenCV image array (BGR or grayscale)
        
        Returns:
            Base64-encoded PNG image string, or None if encoding fails.
        """
        try:
            # Case 1: File path - load and re-encode as PNG
            if isinstance(image_source, (str, Path)):
                image_path = Path(image_source)
                if not image_path.exists():
                    print(f"Error: Image file not found: {image_path}")
                    return None
                
                # Load image with OpenCV to re-encode as PNG
                image = cv2.imread(str(image_path))
                if image is None:
                    print(f"Error: Failed to load image: {image_path}")
                    return None
                
                # Encode as PNG to ensure MIME type consistency
                success, buffer = cv2.imencode('.png', image)
                if not success:
                    print(f"Error: Failed to encode image to PNG: {image_path}")
                    return None
                
                image_bytes = buffer.tobytes()
                return base64.b64encode(image_bytes).decode('utf-8')
            
            # Case 2: NumPy array (OpenCV image)
            elif isinstance(image_source, np.ndarray):
                # Encode as PNG to preserve quality
                success, buffer = cv2.imencode('.png', image_source)
                if not success:
                    print("Error: Failed to encode image array to PNG")
                    return None
                
                image_bytes = buffer.tobytes()
                return base64.b64encode(image_bytes).decode('utf-8')
            
            else:
                print(f"Error: Unsupported image source type: {type(image_source)}")
                return None
                
        except Exception as e:
            print(f"Error encoding image to base64: {e}")
            return None
    
    def analyze_image(
        self,
        image_path: Union[str, Path, np.ndarray, List[Union[str, Path, np.ndarray]]],
        prompt: str,
        response_format: str = "text",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        stop: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Analyze engineering drawing using vision-language model.
        Always returns a plain-text string (no JSON parsing).

        BOM context should be injected via the prompt itself (use
        ``get_vlm_descriptive_prompt(bom_context=...)``), NOT through
        this method.

        Args:
            image_path: Path, OpenCV array, or list thereof.
            prompt: User prompt. Use get_vlm_descriptive_prompt() for geometry analysis.
            response_format: Kept for call-site compatibility; ignored internally.
            temperature: Sampling temperature. Keep low (0.1) to reduce hallucination.
            max_tokens: Maximum tokens in response.
            stop: Optional stop sequences.

        Returns:
            Plain-text description string, or None if request fails.
        """
        # Check if client is initialized
        if self.client is None:
            print("Error: OpenAI client not initialized")
            return None

        # Encode image(s) to base64
        images = image_path if isinstance(image_path, list) else [image_path]
        base64_images: List[str] = []
        for image in images:
            base64_image = self._encode_image_to_base64(image)
            if base64_image is None:
                return None
            base64_images.append(base64_image)

        effective_prompt = prompt

        try:
            # Construct message with image
            user_content = [
                {
                    "type": "text",
                    "text": effective_prompt
                }
            ]
            for base64_image in base64_images:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                )

            messages = [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            
            # Make API request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
            )
            
            # Extract response content
            content = response.choices[0].message.content
            
            # Handle None response
            if content is None:
                print("Warning: Model returned empty response")
                return None
            
            # Output-level dimension leak detector — log a warning so the caller
            # knows the model violated the ZERO NUMBERS RULE without crashing.
            leaked = _DIMENSION_PATTERN.findall(content)
            if leaked:
                print(
                    f"[VLM-WARN] Dimension leak detected in output "
                    f"({len(leaked)} match(es)). "
                    "Model violated ZERO NUMBERS RULE — review output before use."
                )

            # Return plain text directly — no JSON parsing
            return content
        
        except Exception as e:
            print(f"Error during VLM API request: {e}")
            print(f"Endpoint: {self.base_url}")
            print(f"Model: {self.model}")
            
            # Check for common errors
            if "Connection" in str(e) or "timeout" in str(e).lower():
                print("\nTroubleshooting:")
                print("1. Check if LM Studio is running on http://localhost:1234")
                print("2. Verify model is loaded in LM Studio")
                print("3. Test with: curl http://localhost:1234/v1/models")
            
            return None
    
    def batch_analyze(
        self,
        images: list,
        prompt: str,
        **kwargs
    ) -> list:
        """
        Analyze multiple images with the same prompt.
        
        Args:
            images: List of image paths or numpy arrays.
            prompt: Common prompt for all images.
            **kwargs: Additional arguments passed to analyze_image().
        
        Returns:
            List of analysis results (same order as input images).
            Failed analyses return None in the corresponding position.
        """
        results = []
        for i, image in enumerate(images):
            print(f"Processing image {i+1}/{len(images)}...")
            result = self.analyze_image(image, prompt, **kwargs)
            results.append(result)
        return results
    
    def is_available(self) -> bool:
        """
        Check if VLM service is available and responding.
        
        Returns:
            True if service is reachable, False otherwise.
        """
        if self.client is None:
            return False
        
        try:
            # Try to list models as health check
            models = self.client.models.list()
            return True
        except Exception as e:
            print(f"VLM service unavailable: {e}")
            return False


# Convenience function for quick usage
def analyze_engineering_drawing(
    image_path: Union[str, Path, np.ndarray],
    question: str,
    base_url: str = "http://localhost:1234/v1"
) -> Optional[Dict[str, Any]]:
    """
    Quick analysis of engineering drawing without creating client object.
    
    Args:
        image_path: Path to image file or OpenCV image array.
        question: Question to ask about the drawing.
                 Example: "這張工程圖需要哪些製程?"
        base_url: LM Studio server URL (default: local).
    
    Returns:
        Dictionary with analysis results, or None if failed.
        
    Example:
        >>> result = analyze_engineering_drawing("drawing.jpg", "識別所有製程")
        >>> if result:
        >>>     print(result.get("processes", []))
    """
    client = VLMClient(base_url=base_url)
    
    # Check availability first
    if not client.is_available():
        print("Warning: VLM service is not available. Skipping analysis.")
        return None
    
    return client.analyze_image(image_path, question)

