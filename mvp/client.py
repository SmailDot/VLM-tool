"""
MVP VLM Client — lightweight OpenAI-compatible wrapper.

Unlike the main VLMClient, this one accepts a *custom* system prompt per call,
making it suitable for the multi-agent MVP where each agent has its own role.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np

from app.config import VLM_BASE_URL, VLM_MODEL

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI SDK not installed. Run: pip install openai>=1.0.0")


def _encode_image(image_source: Union[str, Path, np.ndarray]) -> Optional[str]:
    """Encode image to base64 PNG string. Supports Unicode/Chinese paths on Windows."""
    try:
        if isinstance(image_source, (str, Path)):
            path = Path(image_source)
            if not path.exists():
                print(f"[MVP-CLIENT] Image not found: {path}")
                return None
            buf = np.fromfile(str(path), dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                print(f"[MVP-CLIENT] Failed to decode: {path}")
                return None
        elif isinstance(image_source, np.ndarray):
            img = image_source
        else:
            print(f"[MVP-CLIENT] Unsupported type: {type(image_source)}")
            return None

        ok, buf = cv2.imencode(".png", img)
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("utf-8")
    except Exception as exc:
        print(f"[MVP-CLIENT] Encode error: {exc}")
        return None


class MVPClient:
    """
    Minimal VLM client for the MVP multi-agent pipeline.

    Key difference from VLMClient: system_prompt is passed per-call,
    enabling each of the 8 Step-2 agents to use its own system prompt.
    """

    def __init__(
        self,
        base_url: str = VLM_BASE_URL,
        model: str = VLM_MODEL,
        timeout: int = 1200,
    ):
        self.model = model
        self.client = OpenAI(
            base_url=base_url,
            api_key="not-needed",
            timeout=timeout,
            max_retries=0,   # no auto-retry — let the caller decide
        )

    # ------------------------------------------------------------------
    def call(
        self,
        system_prompt: str,
        user_text: str,
        images: Optional[List[Union[str, Path, np.ndarray]]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> Optional[str]:
        """
        Make a single VLM call.

        Args:
            system_prompt: Role/instruction for the model.
            user_text:      User-turn message text.
            images:         Optional list of image paths or arrays to attach.
            max_tokens:     Max response tokens.
            temperature:    Sampling temperature (keep low for determinism).

        Returns:
            Response string, or None on failure.
        """
        # Build user content
        user_content: list = [{"type": "text", "text": user_text}]

        if images:
            for img in images:
                b64 = _encode_image(img)
                if b64 is None:
                    print(f"[MVP-CLIENT] Skipping unreadable image: {img}")
                    continue
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                print("[MVP-CLIENT] Empty response from model")
            return content
        except Exception as exc:
            print(f"[MVP-CLIENT] API error: {exc}")
            return None

    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """Quick health check — try to list models."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
