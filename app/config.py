"""
Application configuration.

Values can be overridden by environment variables.
"""

from __future__ import annotations

import os

# VLM (LM Studio)
VLM_BASE_URL = os.getenv("VLM_BASE_URL", "http://localhost:1234/v1")
VLM_MODEL = os.getenv("VLM_MODEL", "LFT2.5-1.6b")
