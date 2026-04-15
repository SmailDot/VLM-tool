"""
MVPPipeline — 3-step multi-agent manufacturing process classifier.

Step 1 : 1 VLM call  — visual observer, outputs Chinese description
Step 2 : 8 VLM calls (parallel via ThreadPoolExecutor) — category classifiers
Step 3 : 1 VLM call  — consolidator, outputs final process table
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np

from mvp.client import MVPClient
from mvp.prompts import (
    AGENTS,
    STEP1_SYSTEM,
    STEP1_USER,
    STEP2_USER_TMPL,
    STEP3_SYSTEM,
    STEP3_USER_TMPL,
)


class MVPPipeline:
    """
    Three-step multi-agent pipeline for manufacturing process classification.

    Usage:
        pipeline = MVPPipeline()
        result = pipeline.run(
            parent_image="path/to/parent.jpg",   # or None
            child_images=["view1.jpg", "view2.jpg", ...],
        )
        print(result["step3"])   # final process table
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_workers: int = 4,
        step1_max_tokens: int = 1024,
        step2_max_tokens: int = 1024,
        step3_max_tokens: int = 2048,
    ):
        """
        Args:
            base_url:          VLM endpoint. Defaults to app.config.VLM_BASE_URL.
            model:             Model name. Defaults to app.config.VLM_MODEL.
            max_workers:       ThreadPoolExecutor workers for Step 2 parallel calls.
            step1_max_tokens:  Max tokens for Step 1 observer output.
            step2_max_tokens:  Max tokens per Step 2 agent output.
            step3_max_tokens:  Max tokens for Step 3 consolidator output.
        """
        kwargs: dict = {}
        if base_url:
            kwargs["base_url"] = base_url
        if model:
            kwargs["model"] = model

        self.client = MVPClient(**kwargs)
        self.max_workers = max_workers
        self.step1_max_tokens = step1_max_tokens
        self.step2_max_tokens = step2_max_tokens
        self.step3_max_tokens = step3_max_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        child_images: List[Union[str, Path, np.ndarray]],
        parent_image: Optional[Union[str, Path, np.ndarray]] = None,
        view_labels: Optional[List[str]] = None,
    ) -> Dict:
        """
        Run the full 3-step pipeline.

        Args:
            child_images:  List of child view images (front/top/side/iso).
            parent_image:  Optional parent drawing image (adds context).
            view_labels:   Optional human-readable labels for each child image.

        Returns:
            dict with keys:
              "step1"         : str  — observation description
              "step2"         : dict — {agent_name: str} raw outputs
              "step3"         : str  — final consolidated process table
              "elapsed_step1" : float
              "elapsed_step2" : float
              "elapsed_step3" : float
              "error"         : str | None  — set if any step failed
        """
        result: Dict = {
            "step1": None,
            "step2": {},
            "step3": None,
            "elapsed_step1": 0.0,
            "elapsed_step2": 0.0,
            "elapsed_step3": 0.0,
            "error": None,
        }

        # Build ordered image list: parent first (if provided), then children
        all_images: List = []
        if parent_image is not None:
            all_images.append(parent_image)
        all_images.extend(child_images)

        if not all_images:
            result["error"] = "No images provided"
            return result

        # ── Step 1 ──────────────────────────────────────────────────
        t0 = time.time()
        print(f"[MVP] Step 1 — Visual Observer ({len(all_images)} images)...")
        step1_output = self._step1_observe(all_images)
        result["elapsed_step1"] = round(time.time() - t0, 1)

        if not step1_output:
            result["error"] = "Step 1 failed: VLM returned no output"
            return result
        result["step1"] = step1_output
        print(f"[MVP] Step 1 done ({result['elapsed_step1']}s)")

        # ── Step 2 ──────────────────────────────────────────────────
        t0 = time.time()
        print(f"[MVP] Step 2 — {len(AGENTS)} Classifier Agents (parallel, workers={self.max_workers})...")
        step2_outputs = self._step2_classify_parallel(step1_output, all_images)
        result["elapsed_step2"] = round(time.time() - t0, 1)
        result["step2"] = step2_outputs
        print(f"[MVP] Step 2 done ({result['elapsed_step2']}s, {len(step2_outputs)} agents replied)")

        # ── Step 3 ──────────────────────────────────────────────────
        t0 = time.time()
        print("[MVP] Step 3 — Consolidator...")
        step3_output = self._step3_consolidate(step1_output, step2_outputs)
        result["elapsed_step3"] = round(time.time() - t0, 1)

        if not step3_output:
            result["error"] = "Step 3 failed: VLM returned no output"
            return result
        result["step3"] = step3_output
        print(f"[MVP] Step 3 done ({result['elapsed_step3']}s)")

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _step1_observe(self, all_images: list) -> Optional[str]:
        """Single VLM call: visual observer with all images."""
        return self.client.call(
            system_prompt=STEP1_SYSTEM,
            user_text=STEP1_USER,
            images=all_images,
            max_tokens=self.step1_max_tokens,
            temperature=0.1,
        )

    def _step2_classify_parallel(
        self, step1_output: str, all_images: list
    ) -> Dict[str, str]:
        """
        Run all 8 classifier agents in parallel.
        Each agent receives: Step1 description (text) + all images.
        """
        user_text = STEP2_USER_TMPL.format(step1_output=step1_output)

        outputs: Dict[str, str] = {}

        def _call_agent(agent_name: str, system_prompt: str) -> tuple[str, Optional[str]]:
            print(f"  [MVP] {agent_name} starting...")
            t0 = time.time()
            out = self.client.call(
                system_prompt=system_prompt,
                user_text=user_text,
                images=all_images,
                max_tokens=self.step2_max_tokens,
                temperature=0.1,
            )
            elapsed = round(time.time() - t0, 1)
            status = "OK" if out else "FAILED"
            print(f"  [MVP] {agent_name} {status} ({elapsed}s)")
            return agent_name, out

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(_call_agent, name, sys_prompt): name
                for name, sys_prompt in AGENTS
            }
            for future in as_completed(futures):
                agent_name, out = future.result()
                outputs[agent_name] = out or "（Agent 無輸出）"

        return outputs

    def _step3_consolidate(
        self, step1_output: str, step2_outputs: Dict[str, str]
    ) -> Optional[str]:
        """Single VLM text-only call: consolidate all agent outputs into final table."""
        # Build the combined agent outputs block
        agent_section_lines = []
        for agent_name, agent_out in step2_outputs.items():
            agent_section_lines.append(f"【{agent_name}】")
            agent_section_lines.append(agent_out)
            agent_section_lines.append("")

        agent_outputs_text = "\n".join(agent_section_lines)

        user_text = STEP3_USER_TMPL.format(
            step1_output=step1_output,
            agent_outputs=agent_outputs_text,
        )

        # Step 3 is text-only — no images needed
        return self.client.call(
            system_prompt=STEP3_SYSTEM,
            user_text=user_text,
            images=None,
            max_tokens=self.step3_max_tokens,
            temperature=0.1,
        )
