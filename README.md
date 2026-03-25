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

**實驗室**：國立高雄科技大學 AIIA實驗室
**專案**：VLM Tool — 工業製程圖紙辨識工具
