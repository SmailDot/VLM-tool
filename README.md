# AoV Tool V2 — 工程圖紙 VLM 分析系統

> **國立高雄科技大學 視覺實驗室**
> 基於 VLM + Multi-Model RAG 的工程圖紙幾何描述系統

---

## 系統簡介

AoV Tool V2 是專為工程圖紙分析設計的 AI 輔助工具。系統使用本地端 Vision Language Model（VLM）對板金零件的 2D 工程圖紙進行幾何描述，並透過 RAG（Retrieval-Augmented Generation）結合人工修正的歷史案例，持續提升描述品質。

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

### VLM 輸出格式（三段式報告）

```
### 1. VIEW-BY-VIEW OBSERVATION
  各視角幾何描述，以 <green>/<orange>/<red> 標記信心度

### 2. SYMBOL & TEXT SEARCH
  - Weld symbol detected: True/False
  - Surface finish mark detected: True/False
  - Other text annotation found: True/False

### 3. 3D RECONSTRUCTION INFERENCE
  工程師視角的 3D 結構推論說明
```

---

## 快速開始

### 環境需求

- Python 3.10+
- [LM Studio](https://lmstudio.ai/)，並載入視覺模型（例如 `google/gemma-3-4b-it`）

### 安裝

```bash
cd AoV_Tool_V2
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

### 基本流程

1. **上傳**子圖（必填）+ 可選的父圖 + BOM 圖片
2. **多視角**上傳：支援 Top / Front / Side / Isometric 視角
3. **設定** VLM 與 RAG 參數（側邊欄）
4. **執行**分析
5. **查看**右側 VLM 幾何描述
6. **修正**描述（HITL 文字編輯器）
7. **儲存**修正後的描述至 RAG 知識庫

### Python API

```python
from app.core import AOVCoreService, AnalysisRequest

service = AOVCoreService()
request = AnalysisRequest(
    image="path/to/child_drawing.jpg",
    parent_image="path/to/parent_drawing.jpg",  # 可選
    use_vlm=True,
    use_rag=True,
    bom_context="SUS304, T1.5, 耐震支架",
)
result = service.analyze(request)
print(result.features.raw_vlm_description)
```

---

## 專案結構

```
AoV_Tool_V2/
|-- aov_app.py                              # Streamlit UI 主入口
|-- main.py                                 # 啟動腳本
|-- requirements.txt
|
|-- app/
|   |-- config.py                           # 全域設定
|   |
|   |-- core/                               # 可移植的 API 外觀層
|   |   |-- contracts.py                    #   AnalysisRequest dataclass
|   |   |-- service.py                      #   AOVCoreService（主要入口）
|   |   +-- example_usage.py                #   最小可執行範例
|   |
|   |-- manufacturing/                      # VLM Pipeline 核心
|   |   |-- schema.py                       #   資料合約（ExtractedFeatures, RecognitionResult）
|   |   |-- pipeline.py                     #   主流程協調（VLM-only）
|   |   |-- prompts.py                      #   VLM Prompt 模板與詞彙控制
|   |   |-- extractors/
|   |   |   |-- vlm_client.py               #   LM Studio / OpenAI-compatible VLM Client
|   |   |   |-- parent_parser.py            #   父圖全域資訊解析器
|   |   |   |-- embeddings.py               #   DINOv2 / CLIP 視覺 Embedding
|   |   |   |-- pdf_extractor.py            #   PDF 轉高解析度圖片
|   |   |   |-- ocr.py                      #   PaddleOCR 封裝（可選）
|   |   |   |-- geometry.py                 #   幾何特徵提取（保留備用）
|   |   |   |-- symbols.py                  #   符號偵測（保留備用）
|   |   |   +-- tolerance_parser.py         #   公差規格解析（保留備用）
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
+-- components/                             # Streamlit UI 元件（不可移植）
    |-- style.py                            #   CSS 樣式
    |-- sidebar.py                          #   側邊欄
    |-- sidebar_panel.py                    #   側邊欄子面板
    |-- results_panel.py                    #   結果顯示 & HITL 渲染
    |-- visualizer.py                       #   預測結果顯示
    +-- text_format.py                      #   信心度標籤格式化
```

### 模組可移植性

以下模組可直接移植到其他專案（不依賴 Streamlit）：

| 模組 | 功能說明 |
|------|---------|
| `app/core/` | 穩定的 API 外觀層（`AOVCoreService`、`AnalysisRequest`） |
| `app/manufacturing/` | VLM Pipeline、Prompt、Schema、VLM Client |
| `app/knowledge/` | RAG 知識庫 + FAISS 向量索引 |
| `app/vision/` | 符號模板比對 |
| `app/features/analysis_actions.py` | 分析執行與 RAG 儲存協調 |
| `app/features/upload_flow.py` | 圖片解碼（支援 bytes / Path / ndarray / file-like） |

`components/` 與 `aov_app.py` 為 Streamlit 專屬，移植時需替換為目標 UI。

---

## RAG 知識庫

### 運作原理

1. **儲存**：使用者修正 VLM 描述 -> HITL 存入 JSON + 計算 DINOv2 圖片 Embedding + multilingual 文字 Embedding -> 更新 FAISS 索引
2. **檢索**：新圖進來 -> 計算圖片 Embedding（DINOv2）+ 文字 Embedding（VLM 初次描述）-> FAISS 混合搜尋（圖片 0.4 + 文字 0.6）-> 取 top-3 相似案例
3. **注入**：最佳匹配案例注入 VLM Prompt 作為「VERIFIED REFERENCE CASE」-> VLM 第二次呼叫自我修正描述

### 儲存位置

| 路徑 | 內容 |
|------|------|
| `knowledge_db.json` | 案例 metadata（id、hash、描述、BOM 上下文） |
| `knowledge_images/` | 圖片副本 |
| `knowledge_vectors/` | FAISS 索引（`image.faiss`、`text.faiss`、`entry_ids.npy`） |

以上三項皆在 `.gitignore`，屬本地運行資料，不納入版控。

### 重建索引

若有既存的 `knowledge_db.json` 案例尚未建立 FAISS Embedding：

```python
from app.knowledge.manager import KnowledgeBaseManager
kb = KnowledgeBaseManager()
kb.rebuild_vector_index()
```

---

## 參數設定

### VLM 設定

| 參數 | 預設值 | 位置 |
|------|--------|------|
| VLM 端點 | `http://localhost:1234/v1` | `app/config.py` / `vlm_client.py` |
| Temperature（第 1 次呼叫） | 0.1 | `pipeline.py` |
| Temperature（RAG 第 2 次呼叫） | 0.15 | `pipeline.py` |
| Max tokens | 512 | `pipeline.py` |
| 模型 | 自動偵測 LM Studio 已載入模型 | `vlm_client.py` |

### RAG 設定

| 參數 | 預設值 | 位置 |
|------|--------|------|
| 圖片 Embedding 權重 | 0.4 | `vector_store.py` |
| 文字 Embedding 權重 | 0.6 | `vector_store.py` |
| 圖片 Embedding 模型 | DINOv2 ViT-Base（768-dim） | `embeddings.py` |
| 文字 Embedding 模型 | `paraphrase-multilingual-MiniLM-L12-v2`（384-dim） | `vector_store.py` |
| Top-K 檢索數量 | 3 | `pipeline.py` |

---

## 疑難排解

### VLM 無回應
- 確認 LM Studio 已啟動且已載入視覺模型
- 確認 `http://localhost:1234/v1/models` 可回傳模型清單
- UI 側邊欄會顯示 VLM 連線狀態警告

### 分析結果空白或品質差
- 降低信心度門檻（側邊欄，建議試 0.2）
- 確認圖紙為白底黑線的工程圖
- 提供 BOM 上下文有助於交叉驗證
- 若知識庫有資料，建議啟用 RAG

### 首次啟動速度較慢
- `sentence-transformers` 模型首次使用時自動下載（約 500MB）
- DINOv2 模型首次使用時自動下載（約 350MB）
- 下載後快取於 `~/.cache/`，之後啟動正常速度

---

## 開發團隊

**實驗室**：國立高雄科技大學 視覺實驗室（NKUST Vision Lab）
**專案**：AoV Tool — 工程圖紙製程辨識系統
