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
from pathlib import Path
import numpy as np
import cv2

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
        "Habit 3 — I write exactly 3 sections and then stop. "
        "Section 1 is my view-by-view observation. Section 2 is my symbol and text scan. Section 3 is my 3D inference. "
        "After I finish Section 3, I write '[END OF REPORT]' on its own line and stop immediately. "
        "I never add Section 4, Section 5, '(continued)', or any extra text after '[END OF REPORT]'.\n"
        "Habit 4 — When multiple images are provided, I always read them in order. "
        "Top View and Front View are my PRIMARY evidence — I base my shape description on these two. "
        "Side View and Iso View are SUPPORTING only — I use them only to confirm details I already see in Top/Front. "
        "If only one image is provided, I treat it as the best available view.\n\n"
        # ── MY REPORT FORMAT (fixed — I always produce exactly this) ───────────
        "My report always looks like this — three sections, this exact heading style, nothing else:\n\n"
        "--- MY REPORT STYLE (do NOT copy this text — analyze the actual drawing) ---\n"
        "### 1. VIEW-BY-VIEW OBSERVATION\n"
        "- Top View: A <green>Rectangular Base</green> with two <green>Thru-holes</green> near the edges.\n"
        "- Front View: A <green>Flange</green> bent upward along the long edge. An <orange>Chamfer</orange> on the top-right corner.\n"
        "- Side/Detail View: Not shown in this drawing.\n\n"
        "### 2. SYMBOL & TEXT SEARCH\n"
        "- One <green>Weld symbol</green> near the left joint.\n"
        "- No material callout visible in any view.\n\n"
        "### 3. 3D RECONSTRUCTION INFERENCE\n"
        "Based on my observations: this is a <green>L-shaped Bracket</green>. "
        "It has a <green>Rectangular Base</green> with a <green>Flange</green> welded along the long edge, forming a right-angle support structure. "
        "The <green>Thru-holes</green> are for bolt-down mounting. "
        "The <green>Weld symbol</green> confirms a welding step is needed. "
        "The <orange>Chamfer</orange> suggests a deburring step after forming.\n"
        "[END OF REPORT]\n"
        "--- END OF STYLE REFERENCE ---"
    )
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "not-needed",
        model: str = "local-model",
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
        bom_context: str = "",
        response_format: str = "text",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        stop: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Analyze engineering drawing using vision-language model.
        Always returns a plain-text string (no JSON parsing).

        Args:
            image_path: Path, OpenCV array, or list thereof.
            prompt: User prompt. Use get_vlm_descriptive_prompt() for geometry analysis.
            bom_context: Optional plain-text BOM facts (material, thickness, part name).
                         Prepended as KNOWN FACTS block when non-empty.
            response_format: Kept for call-site compatibility; ignored internally.
            temperature: Sampling temperature. Keep low (0.1) to reduce hallucination.
            max_tokens: Maximum tokens in response.

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
        # Inject bom_context as KNOWN FACTS preamble if provided
        effective_prompt = prompt
        if bom_context.strip():
            effective_prompt = (
                "=== KNOWN FACTS FROM BOM / GLOBAL NOTES (MANDATORY — DO NOT IGNORE) ===\n"
                "The following information was confirmed by the engineer and carries the HIGHEST PRIORITY.\n"
                "You MUST treat every item below as authoritative ground truth.\n"
                "Violating or contradicting any item below is a CRITICAL ERROR.\n\n"
                f"{bom_context.strip()}\n\n"
                "COMPLIANCE CHECKLIST (apply before writing each section):\n"
                "  [1] Material / surface treatment stated above → mention it in Sections 2 and 4.\n"
                "  [2] Part name / assembly context stated above → reference it in Section 1.\n"
                "  [3] Any dimension or thickness stated above → use it verbatim in Section 3.\n"
                "  [4] Any finish or coating stated above → call it out explicitly in Section 4.\n"
                "If a KNOWN FACT cannot be reconciled with what you see, state the conflict explicitly.\n"
                "=== END OF KNOWN FACTS ===\n\n"
            ) + prompt

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


# Example usage
if __name__ == "__main__":
    """
    Test script to verify VLM client functionality.
    
    Prerequisites:
    1. Install LM Studio: https://lmstudio.ai/
    2. Download a vision-language model (e.g., LLaVA, Qwen-VL)
    3. Start local server in LM Studio (default: http://localhost:1234)
    4. Load the model in LM Studio UI
    """
    
    # Initialize client
    client = VLMClient(
        base_url="http://localhost:1234/v1",
        model="local-model"
    )
    
    # Check if service is available
    print("Checking VLM service availability...")
    if not client.is_available():
        print("❌ VLM service is not available.")
        print("\nSetup instructions:")
        print("1. Download and install LM Studio from https://lmstudio.ai/")
        print("2. Load a vision-language model (e.g., LLaVA)")
        print("3. Start the local server (Server tab)")
        print("4. Ensure it's running on http://localhost:1234")
        exit(1)
    
    print("✅ VLM service is available!\n")
    
    # Test with sample image (you need to provide a real image path)
    test_image = "test_drawing.jpg"
    
    if Path(test_image).exists():
        print(f"Analyzing image: {test_image}")
        result = client.analyze_image(
            image_path=test_image,
            prompt="請分析這張工程圖，描述其形狀、特徵與可能需要的製程類型。請用純文字描述，不要輸出 JSON。",
            response_format="text",
            temperature=0.1
        )
        if result:
            print("\n✅ Analysis successful!")
            print(result)
        else:
            print("\n❌ Analysis failed.")
    else:
        print(f"⚠️  Test image not found: {test_image}")
        print("Please provide a valid engineering drawing image to test.")
