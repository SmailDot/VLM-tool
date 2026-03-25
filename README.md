# VLM Tool — 工業製程圖紙辨識工具

> **國立高雄科技大學 AIIAStudents**
> 基於 VLM + Multi-Model RAG 的工業製程圖紙幾何描述系統

---

## 系統簡介

VLM Tool 是專為工業製程圖紙設計的 AI 輔助辨識工具。系統使用本地端 Vision Language Model（VLM）對板金零件的 2D 工程圖紙進行幾何描述，並透過 RAG（Retrieval-Augmented Generation）結合人工修正的歷史案例，持續提升描述品質。

**核心設計原則：**
- VLM 強制輸出**英文**結構化描述（避免小型模型中文詞彙不足的問題）
- VLM 只負責**幾何描述**，不預測製程（製程推理由下游 LLM 負責）
- RAG 採用**雙通道語意檢索**（圖片 embedding + 文字 embedding）提升案例召回率
- Human-in-the-Loop（HITL）修正後的描述會累積到知識庫，系統越用越準

---

## 系統架構

```
工程圖紙 (JPG / PNG / PDF)
    |
    v
[SymbolMatcher] --- CV 模板比對（VLM 前執行）
    |                 -> 注入 [CV-CONFIRMED] 錨點
    v
[VLM] --- Gemma 3 4B via LM Studio（第 1 次呼叫）
    |       -> 輸出三段式幾何描述
    v
[RAG 檢索] --- FAISS 雙索引
    |   圖片通道: DINOv2 ViT-Base（768-dim，權重 0.4）
    |   文字通道: multilingual-MiniLM-L12-v2（384-dim，權重 0.6）
    |   快速路徑: SHA-256 精確比對 > Jaccard 關鍵字 fallback
    v
[VLM] --- （第 2 次呼叫，注入參考案例）
    |       -> 自我修正後的描述
    v
[輸出] --- raw_vlm_description（英文結構化文字）
    |
    v
[HITL] --- 使用者修正描述 -> 存入知識庫
             -> Embedding 同步更新至 FAISS 索引
```

---

## 快速開始

### 環境需求

- Python 3.10+
- [LM Studio](https://lmstudio.ai/)，並載入視覺模型（例如 `google/gemma-3-4b-it`）

### 安裝

```bash
pip install -r requirements.txt
```

首次執行時 `sentence-transformers` 模型會自動下載（約 500MB，下載後快取）。

PaddleOCR 為可選功能（僅用於父圖 / BOM OCR 掃描）：

```bash
# Windows
pip install paddlepaddle==2.6.1 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
```

### 啟動

```bash
streamlit run aov_app.py
```

開啟瀏覽器至 http://localhost:8501

### LM Studio 設定

1. 下載安裝 [LM Studio](https://lmstudio.ai/)
2. 載入視覺模型（建議 `google/gemma-3-4b-it`）
3. 啟動本地伺服器（預設 `http://localhost:1234`）
4. 系統會透過 OpenAI-compatible API 自動連線

---

## 使用流程

1. **上傳**子圖（必填）+ 可選的父圖 + BOM 圖片
2. **多視角**上傳：支援 Top / Front / Side / Isometric 視角
3. **設定** VLM 與 RAG 參數（側邊欄）
4. **執行**分析
5. **查看**右側 VLM 幾何描述
6. **修正**描述（HITL 文字編輯器）
7. **儲存**修正後的描述至 RAG 知識庫

---

## 專案結構

```
vlm_tool/
|-- aov_app.py                              # Streamlit UI 主入口
|-- main.py                                 # 啟動腳本
|-- requirements.txt
|
|-- app/
|   |-- config.py                           # 全域設定
|   |
|   |-- core/                               # API 外觀層
|   |   |-- contracts.py                    #   AnalysisRequest dataclass
|   |   +-- service.py                      #   AOVCoreService（主要入口）
|   |
|   |-- manufacturing/                      # VLM Pipeline 核心
|   |   |-- schema.py                       #   資料合約（ExtractedFeatures, RecognitionResult）
|   |   |-- pipeline.py                     #   主流程協調（VLM-only）
|   |   |-- prompts.py                      #   VLM Prompt 模板與詞彙控制
|   |   |-- extractors/
|   |   |   |-- vlm_client.py               #   LM Studio / OpenAI-compatible VLM Client
|   |   |   |-- parent_parser.py            #   父圖全域資訊解析器
|   |   |   |-- embeddings.py               #   DINOv2 視覺 Embedding
|   |   |   |-- pdf_extractor.py            #   PDF 轉高解析度圖片
|   |   |   +-- ocr.py                      #   PaddleOCR 封裝（可選）
|   |   +-- decision/
|   |       +-- rule_router.py              #   BOM 文字 -> CV 技能觸發（正則規則）
|   |
|   |-- knowledge/                          # RAG 知識庫
|   |   |-- manager.py                      #   KnowledgeBaseManager（CRUD + 語意檢索）
|   |   +-- vector_store.py                 #   FAISS 雙索引 + TextEmbedder
|   |
|   |-- vision/
|   |   +-- symbol_matcher.py               #   多尺度 CV 模板比對
|   |
|   +-- features/                           # 功能動作層
|       |-- analysis_actions.py             #   執行分析、儲存 RAG 案例
|       |-- upload_flow.py                  #   圖片解碼（框架無關）
|       |-- knowledge_admin.py              #   知識庫 CRUD
|       +-- symbol_library.py               #   符號模板管理
|
+-- components/                             # Streamlit UI 元件
    |-- style.py                            #   CSS 樣式
    |-- sidebar.py                          #   側邊欄
    |-- sidebar_panel.py                    #   側邊欄子面板
    |-- results_panel.py                    #   結果顯示 & HITL 渲染
    +-- text_format.py                      #   信心度標籤格式化
```

---

## 模組化移植指南

以下各模組可獨立抽取使用，依據需求挑選即可。

### 1. VLM Client — 視覺語言模型呼叫

> **檔案**：`app/manufacturing/extractors/vlm_client.py`
> **用途**：對任何圖片發送 prompt 給 LM Studio / OpenAI-compatible VLM，取得文字回應
> **pip 依賴**：`openai>=1.0.0`, `opencv-python`, `numpy`
> **內部依賴**：`app/config.py`（僅讀 `VLM_BASE_URL`，可直接改寫）

```python
from app.manufacturing.extractors.vlm_client import VLMClient

client = VLMClient(base_url="http://localhost:1234/v1")
if client.is_available():
    result = client.analyze_image(
        image_path="drawing.jpg",
        prompt="描述這張圖片的內容",
        temperature=0.1,
        max_tokens=512,
    )
    print(result)
```

**移植方式**：複製 `vlm_client.py`，將 `from app.config import ...` 改為直接寫死或讀環境變數。

---

### 2. Visual Embedder — DINOv2 圖片向量化

> **檔案**：`app/manufacturing/extractors/embeddings.py`
> **用途**：將圖片轉為 768 維向量（DINOv2 ViT-Base），適用於圖片相似度比對
> **pip 依賴**：`torch`, `timm`, `Pillow`, `opencv-python`, `numpy`
> **內部依賴**：無

```python
from app.manufacturing.extractors.embeddings import VisualEmbedder

embedder = VisualEmbedder(model_type="dinov2")
vec = embedder.extract_from_file("drawing.jpg")  # shape: (768,)
```

**移植方式**：直接複製 `embeddings.py`，零修改可用。

---

### 3. RAG 知識庫 — FAISS 雙通道檢索 + HITL 儲存

> **檔案**：`app/knowledge/manager.py` + `app/knowledge/vector_store.py`
> **用途**：儲存人工修正案例，雙通道（圖片 + 文字）語意檢索最相似案例
> **pip 依賴**：`faiss-cpu>=1.7.4`, `sentence-transformers>=3.0.0`, `numpy`
> **內部依賴**：`embeddings.py`（圖片向量化）

```python
from app.knowledge.manager import KnowledgeBaseManager

kb = KnowledgeBaseManager(db_path="my_kb.json", image_storage_dir="my_images")

# 新增案例
kb.add_entry(
    image_path="drawing.jpg",
    features={"raw_vlm_description": "corrected description here"},
    correct_processes=[],
    reasoning="人工修正備註",
    bom_context="SUS304, T1.5",
)

# 檢索相似案例
results = kb.retrieve_similar(
    vlm_feats=None,
    image_path="new_drawing.jpg",
    raw_vlm_text="VLM first-pass output",
    top_k=3,
)
```

**向量索引細節**（`vector_store.py`）：

| 通道 | 模型 | 維度 | 權重 |
|------|------|------|------|
| 圖片 | DINOv2 ViT-Base | 768 | 0.4 |
| 文字 | `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 0.6 |

**移植方式**：複製 `knowledge/` 資料夾 + `embeddings.py`，共 3 個檔案。

---

### 4. Symbol Matcher — CV 模板比對

> **檔案**：`app/vision/symbol_matcher.py`
> **用途**：多尺度模板比對，偵測工程圖紙上的焊接符號、表面處理標記等
> **pip 依賴**：`opencv-python`, `numpy`
> **內部依賴**：無

```python
from app.vision.symbol_matcher import SymbolMatcher

matcher = SymbolMatcher(library_dir="data/symbol_library", threshold=0.70)
hits = matcher.match_symbols(target_img)
# [{"name": "weld_v", "confidence": 0.85, "location": (x, y, w, h)}, ...]
```

**特性**：多尺度掃描（0.2x–1.0x）、支援 alpha 遮罩 PNG、NCC 評分

**移植方式**：直接複製 `symbol_matcher.py` + 模板圖片資料夾，零修改可用。

---

### 5. PDF Extractor — PDF 轉高解析度圖片

> **檔案**：`app/manufacturing/extractors/pdf_extractor.py`
> **用途**：將 PDF 頁面轉為高 DPI 的 numpy array，支援全頁或區域擷取
> **pip 依賴**：`PyMuPDF>=1.26.0`, `Pillow`, `opencv-python`, `numpy`
> **內部依賴**：無

```python
from app.manufacturing.extractors.pdf_extractor import PDFImageExtractor

extractor = PDFImageExtractor(target_dpi=300)
img = extractor.extract_full_page("drawing.pdf", page_num=0)  # np.ndarray (BGR)
```

**移植方式**：直接複製 `pdf_extractor.py`，零修改可用。

---

### 6. OCR Extractor — PaddleOCR 中英文辨識

> **檔案**：`app/manufacturing/extractors/ocr.py`
> **用途**：對圖片進行 OCR 文字辨識，支援中英日韓多語系
> **pip 依賴**：`paddleocr>=3.4.0`, `paddlepaddle>=2.6.2`, `opencv-python`, `numpy`
> **內部依賴**：`app/manufacturing/schema.py`（僅用 `OCRResult` dataclass，可自行定義替代）

```python
from app.manufacturing.extractors.ocr import OCRExtractor

ocr = OCRExtractor(lang="ch")
results = ocr.extract(image, confidence_threshold=0.6)
# [OCRResult(text="SUS304", confidence=0.95, bbox=[...]), ...]
```

**移植方式**：複製 `ocr.py`，將 `OCRResult` import 改為自定義 dataclass 或直接用 dict。

---

### 7. Parent Image Parser — 父圖 BOM 資訊解析

> **檔案**：`app/manufacturing/extractors/parent_parser.py`
> **用途**：解析父圖（組立圖）中的材質、板厚、客戶、表面處理等 BOM 資訊
> **pip 依賴**：`openai>=1.0.0`, `opencv-python`, `numpy`
> **內部依賴**：`vlm_client.py`（VLM 呼叫）、`ocr.py`（可選）

```python
from app.manufacturing.extractors.parent_parser import ParentImageParser

parser = ParentImageParser(vlm_client=my_vlm_client)
ctx = parser.parse(parent_image)
# ctx.material = "SUS304", ctx.thickness = "T1.5", ctx.customer = "ASML"
```

**內建關鍵字規則**：材質（白鐵/鋁板/鐵板）、客戶（ASML/日本）、潔淨室等級、表面處理

**移植方式**：複製 `parent_parser.py` + `vlm_client.py`。

---

### 8. Rule Router — BOM 文字觸發 CV 技能

> **檔案**：`app/manufacturing/decision/rule_router.py`
> **用途**：根據 BOM 文字內容（焊接、攻牙、折彎等關鍵字）決定需啟動哪些 CV 掃描技能
> **pip 依賴**：無（純 Python `re`）
> **內部依賴**：無

```python
from app.manufacturing.decision.rule_router import plan_vision_skills, describe_skills

skills = plan_vision_skills("材質: SUS304, 製程: 焊接, 攻牙M6")
# ['scan_weld_symbols', 'scan_thread_marks']

print(describe_skills(skills))
# "焊接符號掃描、螺紋標記掃描"
```

**移植方式**：直接複製 `rule_router.py`，零依賴。

---

### 9. Prompt Builder — VLM Prompt 模板生成

> **檔案**：`app/manufacturing/prompts.py`
> **用途**：組裝 VLM prompt，包含 BOM 事實、RAG 參考案例、CV 錨點、anti-hallucination 規則
> **pip 依賴**：無（純字串組裝）
> **內部依賴**：無

```python
from app.manufacturing.prompts import get_vlm_descriptive_prompt

prompt = get_vlm_descriptive_prompt(
    bom_context="SUS304, T1.5, 耐震支架",
    rag_context="[參考案例描述]",
    system_anchors=["[CV-CONFIRMED] weld_v_groove detected"],
)
```

**移植方式**：直接複製 `prompts.py`，零依賴。

---

### 10. Schema — 資料合約與詞彙表

> **檔案**：`app/manufacturing/schema.py`
> **用途**：定義所有資料結構（`ExtractedFeatures`, `RecognitionResult`, `OCRResult` 等）與 Tier-1 標準詞彙表
> **pip 依賴**：`numpy`
> **內部依賴**：無

**主要 dataclass**：

| Class | 用途 |
|-------|------|
| `ExtractedFeatures` | VLM 輸出 + 嵌入向量 + 符號偵測結果 |
| `RecognitionResult` | 最終分析結果（features + 時間 + 警告 + RAG 參考） |
| `OCRResult` | OCR 辨識結果（文字 + 信心度 + bbox） |
| `SymbolDetection` | 符號偵測結果 |
| `TIER1_VOCABULARY` | 35 個板金標準英文術語 |

**移植方式**：直接複製 `schema.py`，零依賴。

---

### 模組依賴關係圖

```
[schema] [prompts] [rule_router]        ← 零依賴，可獨立使用
    |        |          |
    v        v          v
[vlm_client] [embeddings] [ocr] [pdf_extractor] [symbol_matcher]  ← 單一功能模組
    |             |         |
    v             v         v
[parent_parser]  [vector_store]         ← 組合模組
                      |
                      v
                 [kb_manager]           ← RAG 完整功能
                      |
                      v
                  [pipeline]            ← 主流程（組裝以上全部）
                      |
                      v
                [core/service]          ← 對外 Facade
```

---

## RAG 知識庫

### 運作原理

1. **儲存**：使用者修正 VLM 描述 -> 存入 JSON + 計算 DINOv2 圖片 Embedding + multilingual 文字 Embedding -> 更新 FAISS 索引
2. **檢索**：新圖進來 -> 計算圖片 Embedding + 文字 Embedding -> FAISS 混合搜尋（圖片 0.4 + 文字 0.6）-> 取 top-3 相似案例
3. **注入**：最佳匹配案例注入 VLM Prompt 作為參考 -> VLM 第二次呼叫自我修正描述

### 儲存位置

| 路徑 | 內容 |
|------|------|
| `knowledge_db.json` | 案例 metadata（id、hash、描述、BOM 上下文） |
| `knowledge_images/` | 圖片副本 |
| `knowledge_vectors/` | FAISS 索引（`image.faiss`、`text.faiss`、`entry_ids.npy`） |

以上皆在 `.gitignore`，屬本地運行資料，不納入版控。

---

## 參數設定

### VLM

| 參數 | 預設值 |
|------|--------|
| VLM 端點 | `http://localhost:1234/v1` |
| Temperature（第 1 次呼叫） | 0.1 |
| Temperature（RAG 第 2 次呼叫） | 0.15 |
| Max tokens | 512 |
| 模型 | 自動偵測 LM Studio 已載入模型 |

### RAG

| 參數 | 預設值 |
|------|--------|
| 圖片 Embedding 權重 | 0.4 |
| 文字 Embedding 權重 | 0.6 |
| 圖片 Embedding 模型 | DINOv2 ViT-Base（768-dim） |
| 文字 Embedding 模型 | `paraphrase-multilingual-MiniLM-L12-v2`（384-dim） |
| Top-K 檢索數量 | 3 |

---

## 開發團隊

**實驗室**：國立高雄科技大學 AIIAStudents（NKUST AIIAStudents）
**專案**：VLM Tool — 工業製程圖紙辨識工具
