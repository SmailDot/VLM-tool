# AoV Tool V2 — VLM-based Engineering Drawing Analyzer

> **NKUST Vision Lab**
> Manufacturing Process Recognition from Engineering Drawings
> VLM-only + Multi-Model RAG Architecture

---

## Overview

AoV Tool V2 is an AI-powered engineering drawing analysis system. It uses a local Vision Language Model (VLM) to describe the geometry, features, and symbols of sheet-metal parts from 2D engineering drawings, then leverages RAG (Retrieval-Augmented Generation) with human-corrected references to progressively improve description quality.

**Key design decisions:**
- VLM outputs **English-only** structured descriptions (avoids Chinese vocabulary issues in small models)
- VLM describes geometry — it does **not** predict manufacturing processes (that's downstream LLM's job)
- RAG uses **dual-channel semantic search** (image + text embeddings) for accurate case retrieval
- Human-in-the-loop (HITL) corrections accumulate into a knowledge base that makes the system smarter over time

---

## Architecture

```
Engineering Drawing (JPG/PNG/PDF)
    |
    v
[SymbolMatcher] --- CV template matching (pre-VLM)
    |                 -> [CV-CONFIRMED] anchors
    v
[VLM] --- Gemma 3 4B via LM Studio (1st call)
    |       -> Structured 3-section geometry description
    v
[RAG Retrieval] --- FAISS dual index
    |   Image channel: DINOv2 ViT-Base (768-dim, weight 0.4)
    |   Text channel:  multilingual-MiniLM-L12-v2 (384-dim, weight 0.6)
    |   Fallback: SHA-256 exact match > Jaccard keyword
    v
[VLM] --- (2nd call, with reference case injected)
    |       -> Self-corrected description
    v
[Output] --- raw_vlm_description (English structured text)
    |
    v
[HITL] --- User corrects description -> saves to knowledge base
             -> embeddings indexed in FAISS for future retrieval
```

### VLM Output Format (3-section report)

```
### 1. VIEW-BY-VIEW OBSERVATION
  Geometry description with <green>/<orange>/<red> confidence tags

### 2. SYMBOL & TEXT SEARCH
  - Weld symbol detected: True/False
  - Surface finish mark detected: True/False
  - Other text annotation found: True/False

### 3. 3D RECONSTRUCTION INFERENCE
  Engineer-style reasoning about part structure
```

---

## Quick Start

### Requirements
- Python 3.10+
- [LM Studio](https://lmstudio.ai/) with a vision model loaded (e.g. `google/gemma-3-4b-it`)

### Installation

```bash
cd AoV_Tool_V2
pip install -r requirements.txt
```

First run will auto-download the sentence-transformers model (~500MB, cached afterwards).

PaddleOCR is optional (used only for parent image / BOM OCR scanning):
```bash
# Windows
pip install paddlepaddle==2.6.1 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
```

### Launch

```bash
streamlit run aov_app.py
```

Open http://localhost:8501 in your browser.

### LM Studio Setup

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load a vision model (e.g. `google/gemma-3-4b-it`)
3. Start the local server (default: `http://localhost:1234`)
4. The system auto-connects via OpenAI-compatible API

---

## Usage

### Basic Flow

1. **Upload** child drawing (required) + optional parent drawing + BOM images
2. **Multi-view** upload supported: Top / Front / Side / Isometric views
3. **Configure** VLM and RAG settings in sidebar
4. **Run** analysis
5. **Review** VLM description on the right panel
6. **Correct** the description via HITL text editor
7. **Save** corrected description to RAG knowledge base

### Python API

```python
from app.core import AOVCoreService, AnalysisRequest

service = AOVCoreService()
request = AnalysisRequest(
    image="path/to/child_drawing.jpg",
    parent_image="path/to/parent_drawing.jpg",  # optional
    use_vlm=True,
    use_rag=True,
    bom_context="SUS304, T1.5, Bracket",
)
result = service.analyze(request)
print(result.features.raw_vlm_description)
```

---

## Project Structure

```
AoV_Tool_V2/
|-- aov_app.py                              # Streamlit UI entry point
|-- main.py                                 # Launcher script
|-- requirements.txt
|
|-- app/
|   |-- config.py                           # Global configuration
|   |
|   |-- core/                               # Portable API facade
|   |   |-- contracts.py                    #   AnalysisRequest dataclass
|   |   |-- service.py                      #   AOVCoreService (main entry)
|   |   +-- example_usage.py                #   Minimal usage example
|   |
|   |-- manufacturing/                      # VLM pipeline core
|   |   |-- schema.py                       #   Data contracts (ExtractedFeatures, RecognitionResult)
|   |   |-- pipeline.py                     #   Main orchestration (VLM-only)
|   |   |-- prompts.py                      #   VLM prompt templates & vocabulary
|   |   |-- extractors/
|   |   |   |-- vlm_client.py               #   LM Studio / OpenAI-compatible VLM client
|   |   |   |-- parent_parser.py            #   Parent drawing global context parser
|   |   |   |-- embeddings.py               #   DINOv2 / CLIP visual embeddings
|   |   |   |-- pdf_extractor.py            #   PDF -> high-res image extraction
|   |   |   |-- ocr.py                      #   PaddleOCR wrapper (optional)
|   |   |   |-- geometry.py                 #   Geometry extractor (reserved)
|   |   |   |-- symbols.py                  #   Symbol detector (reserved)
|   |   |   +-- tolerance_parser.py         #   Tolerance spec parser (reserved)
|   |   +-- decision/
|   |       +-- rule_router.py              #   BOM text -> CV skill triggers (regex)
|   |
|   |-- knowledge/                          # RAG knowledge base
|   |   |-- manager.py                      #   KnowledgeBaseManager (CRUD + retrieval)
|   |   +-- vector_store.py                 #   FAISS dual index + TextEmbedder
|   |
|   |-- vision/
|   |   +-- symbol_matcher.py               #   Multi-scale template matching
|   |
|   +-- features/                           # Action handlers
|       |-- analysis_actions.py             #   Run analysis, save RAG entry
|       |-- upload_flow.py                  #   Image decoding (framework-agnostic)
|       |-- knowledge_admin.py              #   KB entry CRUD
|       +-- symbol_library.py               #   Symbol template management
|
+-- components/                             # Streamlit UI components (not portable)
    |-- style.py                            #   CSS styling
    |-- sidebar.py                          #   Sidebar configuration
    |-- sidebar_panel.py                    #   Sidebar sub-panels
    |-- results_panel.py                    #   Results & HITL rendering
    |-- visualizer.py                       #   Prediction display
    +-- text_format.py                      #   Confidence tag formatting
```

### Portability

The following modules can be directly transplanted to other projects **without Streamlit**:

| Module | What it does |
|--------|-------------|
| `app/core/` | Stable API facade (`AOVCoreService`, `AnalysisRequest`) |
| `app/manufacturing/` | VLM pipeline, prompts, schema, VLM client |
| `app/knowledge/` | RAG knowledge base + FAISS vector store |
| `app/vision/` | Symbol template matching |
| `app/features/analysis_actions.py` | Analysis + RAG save orchestration |
| `app/features/upload_flow.py` | Image decoding (accepts bytes/Path/ndarray/file-like) |

`components/` and `aov_app.py` are Streamlit-specific and should be replaced with your target UI.

---

## RAG System

### How it works

1. **Save**: User corrects VLM description -> HITL saves to JSON knowledge base + computes DINOv2 image embedding + multilingual text embedding -> indexes in FAISS
2. **Retrieve**: New image comes in -> compute image embedding (DINOv2) + text embedding (from VLM initial description) -> FAISS hybrid search (0.4 image + 0.6 text) -> top-3 similar cases
3. **Inject**: Best matching reference case injected into VLM prompt as "VERIFIED REFERENCE CASE" -> VLM self-corrects its description

### Storage

| File/Dir | Content |
|----------|---------|
| `knowledge_db.json` | Entry metadata (id, hash, description, BOM context) |
| `knowledge_images/` | Copied source images |
| `knowledge_vectors/` | FAISS indices (`image.faiss`, `text.faiss`, `entry_ids.npy`) |

All three are in `.gitignore` (local runtime data).

### Rebuilding index

If you have existing `knowledge_db.json` entries without FAISS embeddings:

```python
from app.knowledge.manager import KnowledgeBaseManager
kb = KnowledgeBaseManager()
kb.rebuild_vector_index()
```

---

## Configuration

### VLM Settings

| Setting | Default | Location |
|---------|---------|----------|
| VLM endpoint | `http://localhost:1234/v1` | `app/config.py` / `vlm_client.py` |
| Temperature | 0.1 (1st call), 0.15 (RAG 2nd call) | `pipeline.py` |
| Max tokens | 512 | `pipeline.py` |
| Model | Auto-detect from LM Studio | `vlm_client.py` |

### RAG Settings

| Setting | Default | Location |
|---------|---------|----------|
| Image embedding weight | 0.4 | `vector_store.py` |
| Text embedding weight | 0.6 | `vector_store.py` |
| Image embedding model | DINOv2 ViT-Base (768-dim) | `embeddings.py` |
| Text embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) | `vector_store.py` |
| Top-K retrieval | 3 | `pipeline.py` |

---

## Troubleshooting

### VLM not responding
- Confirm LM Studio is running and a vision model is loaded
- Check `http://localhost:1234/v1/models` returns a model list
- The UI shows a warning if VLM service is unreachable

### Empty or poor results
- Lower confidence threshold (sidebar, try 0.2)
- Ensure image is a clear engineering drawing (white background, black lines)
- Provide BOM context for better cross-verification
- Enable RAG if knowledge base has entries

### First-time slow startup
- `sentence-transformers` model downloads on first use (~500MB)
- DINOv2 model downloads on first use (~350MB)
- Both are cached in `~/.cache/` after first download

---

## Team

**Lab**: NKUST Vision Lab (National Kaohsiung University of Science and Technology)
**Project**: AoV Tool — Manufacturing Process Recognition
