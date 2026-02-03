# NKUST AoV Tool - System Architecture & Rules

## 🛑 CRITICAL INSTRUCTIONS (MUST READ)
You are the Lead Architect for the NKUST AoV Tool. The current state of the project is "Unacceptable/Toy-Level".
Your goal is to transform this into a "Industrial-Grade" FPGA deployment tool.

## 🧠 Project Memory (Do NOT Forget)
1. **The "999 CLK" Ban:** NEVER return "999" or "Unknown". If a CLK value is missing in `tech_lib.json`, you MUST calculate it using the heuristic: `(Image_Width * Image_Height * Kernel_Size^2) / Parallelism_Factor`.
2. **The "Green Mess" Ban:** The current HoughCircles output is garbage. It detects keyboard keys as coins.
   - **Constraint:** `param2` (Accumulator Threshold) MUST default to **50 or higher**.
   - **Constraint:** `minDist` MUST be at least **1/8 of image height**.
   - **Mandatory Preprocessing:** NEVER apply HoughCircles directly on a raw image. The pipeline MUST be: `GaussianBlur` -> `Canny` -> `HoughCircles`.
3. **UI Rules:**
   - Remove "National Kaohsiung University..." subtitles.
   - Edges in Graphviz MUST show hardware logic (e.g., "LineBuffer", "Window 3x3").

## 📂 File Structure Context
- `tech_lib.json`: The Single Source of Truth for hardware specs.
- `logic_engine.py`: The brain. It maps strings to functions.
- `processor.py`: The muscle. It executes OpenCV code.

## ⚡ MCP / Tool Use Protocol
When the user asks for a feature, FIRST check `tech_lib.json`.
- If an algorithm is missing, DO NOT Hallucinate.
- Action: Generate a Python script to APPEND the new algorithm to `tech_lib.json` with calculated hardware costs immediately.