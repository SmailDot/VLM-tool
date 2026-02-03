# AGENTS.md - Context & Rules for AI Agents

> **Auto-generated Context for AI Agents**  
> This file provides project-specific context, commands, and standards for AI agents (Sisyphus, Cursor, Copilot, etc.) working on the NKUST AoV Tool.

## 1. Project Context
**Name**: NKUST AoV Tool (FPGA-aware Computer Vision Pipeline Generator)
**Goal**: Allow users to generate OpenCV algorithm pipelines via natural language, with real-time FPGA resource estimation.
**Tech Stack**:
- **Frontend**: Streamlit (`aov_app.py`)
- **Backend**: Python 3.8+
- **CV Engine**: OpenCV (`cv2`), NumPy, Pillow
- **Visualization**: Graphviz, PyVis
- **Data**: JSON for project storage (`tech_lib.json`, project exports)

## 2. Environment & Commands

### Setup
The project uses a standard Python virtual environment.
```bash
# Windows
.venv\Scripts\activate
pip install -r requirements.txt

# Linux/Mac
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Application
Primary entry point is Streamlit:
```bash
streamlit run aov_app.py
# Or via python module
python -m streamlit run aov_app.py
```

### Testing & Linting
Currently, the project relies on manual verification via the UI.
However, agents adding new features **MUST** ensure basic code quality:

**Linting (Recommended)**:
```bash
# Check for syntax errors and undefined names
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

**Testing**:
No formal test suite exists yet. 
- When adding logic: Create a small reproduction script if complex.
- When fixing bugs: Verify with `test1.jpg` or `test2.jpg`.

## 3. Code Style & Standards

### Python General
- **Version**: Python 3.8+ compatible.
- **Formatting**: Follow PEP 8.
  - Indentation: 4 spaces.
  - Line length: Soft limit 100, hard limit 120.
- **Typing**: **MANDATORY** for all new function signatures.
  ```python
  # Good
  def process_image(img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
      ...
  
  # Bad
  def process_image(img, params):
      ...
  ```

### Docstrings
Use **Google Style** docstrings for all modules, classes, and complex functions.
```python
def example_function(param1: int, param2: str) -> bool:
    """
    Brief description of what the function does.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        bool: True if successful, False otherwise.
    """
    pass
```

### Imports
Group imports in the following order:
1. Standard Library (`import os`, `import json`)
2. Third-Party (`import cv2`, `import streamlit as st`)
3. Local Modules (`from processor import ImageProcessor`)

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `LogicEngine`)
- **Functions/Variables**: `snake_case` (e.g., `execute_pipeline`)
- **Constants**: `UPPER_CASE` (e.g., `DEFAULT_IMAGE_SIZE`)
- **Private**: `_leading_underscore` (e.g., `_op_canny`)

### Error Handling
- Use `try-except` blocks for operations that might fail (I/O, OpenCV ops).
- Print informative error messages (or use `st.error` in UI code).
- Do NOT swallow errors silently.

## 4. Architecture & Key Modules

| Module | Responsibility |
|--------|----------------|
| `aov_app.py` | **Entry Point**. Streamlit UI layout, state management (`st.session_state`), and event handling. |
| `logic_engine.py` | **Brain**. Handles LLM query processing, JSON parsing, and pipeline generation logic. |
| `processor.py` | **Execution**. `ImageProcessor` class. Maps string operation names (e.g., "Canny") to OpenCV calls. |
| `library_manager.py` | **Database**. Manages `tech_lib.json` (algorithms, FPGA constraints). |
| `project_manager.py` | **I/O**. Handles Import/Export of `.json` project files. |
| `tech_lib.json` | **Data**. Defines available algorithms, their parameters, and FPGA resource costs. |

### Adding a New Algorithm
1. **Definition**: Add entry to `tech_lib.json` (name, params, FPGA stats).
2. **Implementation**: Add method `_op_new_algo` to `ImageProcessor` in `processor.py`.
3. **Registration**: Ensure `ImageProcessor.operation_map` points to the new method.

## 5. Agent Behavior Guidelines

### "Sisyphus" Mode
- **Proactive**: If you see a missing dependency or error, fix it.
- **Atomic**: Keep changes focused. Don't rewrite the whole app for a typo fix.
- **Verification**: Since there's no CI, you **MUST** mentally verify your logic or create a small check script.
- **Context**: Read `README.md` and `tech_lib.json` before proposing architectural changes.

### UI Changes (Streamlit)
- Use `st.session_state` for data persistence across reruns.
- Use `st.cache_resource` for heavy objects (Engine, Processor).
- Keep the UI responsive; use `st.spinner` for long operations.

### File Operations
- Always use **Absolute Paths** or `os.path.join` relative to the script location.
- Respect the `05_AoV_Tool` root directory.

## 6. Common Issues & Fixes
- **Graphviz Error**: Ensure `graphviz` binary is in system PATH.
- **OpenCV Errors**: Check input image depth/channels before processing.
- **Streamlit Rerun**: Call `st.rerun()` carefully to avoid infinite loops.

---
*Generated by Sisyphus Agent - 2026-01-20*
