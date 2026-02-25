"""
VLM (Vision Language Model) Client for Engineering Drawing Analysis.

Uses OpenAI-compatible API (LM Studio) to analyze engineering drawings with 
vision-language models. Optimized for sheet metal manufacturing process recognition.

Compatible with:
- LM Studio (local VLM server)
- OpenAI GPT-4 Vision API
- Any OpenAI-compatible vision API endpoint
"""

from typing import Optional, Dict, Any, Union, List
import base64
import json
import re
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
        "你是一個資深的鈑金加工工程師，請根據工程圖視覺特徵回答問題，"
        "只輸出 JSON 格式。"
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
        response_format: str = "json",
        temperature: float = 0.0,
        max_tokens: int = 2000
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze engineering drawing using vision-language model.
        
        Args:
            image_path: Path to image file or OpenCV image array (np.ndarray).
            prompt: User prompt describing what to analyze.
                   Example: "識別此工程圖中所有可能的製程類型"
            response_format: Expected response format ("json" or "text").
                           "json" will attempt to parse the response as JSON.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
                        Use 0.0 for factual engineering analysis.
            max_tokens: Maximum tokens in response.
        
        Returns:
            Dictionary containing analysis results, or None if request fails.
            
            Example successful response:
            {
                "processes": ["折彎", "雷射切割", "焊接"],
                "confidence": 0.85,
                "reasoning": "圖中可見折彎線、切割路徑標記和焊接符號"
            }
            
            Example error response (connection failed):
            None
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
        
        try:
            # Construct message with image
            user_content = [
                {
                    "type": "text",
                    "text": prompt
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
                max_tokens=max_tokens
            )
            
            # Extract response content
            content = response.choices[0].message.content
            
            # Handle None response
            if content is None:
                print("Warning: Model returned empty response")
                return None
            
            # Parse JSON response if requested
            if response_format == "json":
                try:
                    # content is guaranteed to be str here (None check above)
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        return json.loads(json_str)

                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse response as JSON: {e}")
                    print(f"Raw response: {content}")
                    # Return raw text wrapped in dict
                    return {"raw_response": content, "parse_error": str(e)}
            else:
                # Return raw text response (content is str here)
                return {"response": content}
        
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
            prompt="請分析這張工程圖，識別可能需要的製程類型。以 JSON 格式輸出，包含: processes (製程列表), confidence (信心度), reasoning (判斷依據)",
            response_format="json",
            temperature=0.0
        )
        
        if result:
            print("\n✅ Analysis successful!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("\n❌ Analysis failed.")
    else:
        print(f"⚠️  Test image not found: {test_image}")
        print("Please provide a valid engineering drawing image to test.")
