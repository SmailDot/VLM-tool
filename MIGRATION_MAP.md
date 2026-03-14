# MIGRATION MAP - AoV Tool Modular Porting Guide

> 目標：把目前專案以「拼圖式」移植到其他專案，並確保 VLM + RAG 核心功能完整。

---

## 1) 三大模組邊界（已落地）

### A. 圖紙上傳模組（Upload Flow）
- 責任：父圖/子圖/BOM 上傳、解碼、OCR 掃描、暫存拼圖
- 主要檔案：
  - `app/features/upload_flow.py`

### B. VLM 系統模組（含 BOM/子圖注入）
- 責任：
  - 組裝 `AnalysisRequest`
  - 注入 `bom_context`、`child_images`、`view_labels`
  - 呼叫核心分析服務
- 主要檔案：
  - `app/features/analysis_actions.py`
  - `app/core/contracts.py`
  - `app/core/service.py`
  - `app/manufacturing/pipeline.py`

### C. 修正區 + Multi-Model RAG 模組
- 責任：
  - HITL 修正
  - RAG 案例儲存、查詢、更新
- 主要檔案：
  - `app/features/knowledge_admin.py`
  - `app/features/analysis_actions.py`（`save_rag_entry`）
  - `app/knowledge/manager.py`

---

## 2) UI 組裝層（可選，若你要沿用 Streamlit）

- `aov_app.py`：組裝層（orchestration）
- `components/results_panel.py`：結果區渲染（摘要/VLM/HITL/父圖注意事項/diagnostics）
- `components/sidebar_panel.py`：側欄區塊（符號庫/狀態/清除/關於）
- `components/text_format.py`：VLM 標籤格式化工具
- `components/sidebar.py`, `components/style.py`

---

## 3) 最小可移植集合（核心功能版）

若目標專案只要「上傳 → VLM 描述 → HITL + RAG」，至少搬這些：

### Core + Domain
- `app/core/__init__.py`
- `app/core/contracts.py`
- `app/core/service.py`
- `app/manufacturing/pipeline.py`
- `app/manufacturing/schema.py`
- `app/manufacturing/prompts.py`
- `app/manufacturing/extractors/vlm_client.py`
- `app/manufacturing/extractors/parent_parser.py`
- `app/manufacturing/extractors/ocr.py`
- `app/manufacturing/extractors/geometry.py`
- `app/manufacturing/extractors/symbols.py`
- `app/manufacturing/extractors/pdf_extractor.py`

### Features
- `app/features/__init__.py`
- `app/features/analysis_actions.py`
- `app/features/upload_flow.py`
- `app/features/knowledge_admin.py`
- `app/features/symbol_library.py`

### Knowledge
- `app/knowledge/manager.py`

---

## 4) 移植順序（建議照這個順序）

1. **先搬核心**：`app/core` + `app/manufacturing` + `app/knowledge`
2. **再搬 feature 層**：`app/features`
3. **最後搬 UI**（若需要）：`components` + `aov_app.py`
4. 在新專案修正 import root
5. 跑 smoke tests（見第 6 節）

---

## 5) 目前穩定契約（不要隨便改名）

### API 契約
- `AnalysisRequest`（`app/core/contracts.py`）
- `AOVCoreService.analyze()`（`app/core/service.py`）
- `build_analysis_request()`（`app/features/analysis_actions.py`）
- `run_analysis()`（`app/features/analysis_actions.py`）

### Session State Key 契約（Streamlit UI）
避免改名，否則容易破壞 UI/模組互通：

- `core_service`, `mfg_pipeline`
- `uploaded_drawing`, `uploaded_drawings`, `uploaded_view_labels`
- `parent_drawing`, `bom_drawings`, `bom_scanned_text`, `bom_context_input`, `locked_bom`, `_last_synced_bom`
- `temp_file_path`, `recognition_result`, `hitl_corrected_text`, `_hitl_result_key`
- `use_vlm`, `use_rag`, `min_confidence`, `last_settings`

---

## 6) 移植完成後必跑驗證

### A. 編譯檢查
```bash
python -m py_compile aov_app.py
python -m py_compile app/core/service.py app/features/analysis_actions.py app/features/upload_flow.py
python -m py_compile components/results_panel.py components/sidebar_panel.py
```

### B. 核心整合測試
```bash
python test_vlm_integration.py
```

### C. 手動流程驗證（必跑）
1. 上傳子圖（至少一張）
2. 上傳 BOM 或父圖並執行 OCR 掃描
3. 觸發 VLM 分析
4. 在修正區修改內容後儲存至 RAG
5. 再次分析，確認有 RAG 參考案例回灌

---

## 7) 目前已完成的模組化 commit（參考）

- `628d72b`：抽出可嵌入 core API
- `eed24cf`：分析執行/知識庫/符號庫切到 features
- `a651352`：上傳/BOM 掃描與文字格式化抽離
- `52a0b1c`：BOM 與子圖注入責任收斂到 VLM 模組
- `33c9111`：結果摘要與 HITL 抽離到 results_panel
- `ccaf820`：父圖注意事項與 diagnostics 收斂到 results_panel
- `618e8a7`：側欄與無結果佔位抽離到 sidebar_panel
- `47631f6`：主入口 orchestration 清理

---

## 8) 常見風險與避免方式

1. **風險：BOM 注入丟失**
   - 避免：只用 `build_analysis_request()` 產生請求，不要在 UI 自己拼

2. **風險：子圖視角順序錯亂**
   - 避免：沿用 `decode_child_views()` 的輸出順序與 `uploaded_view_labels`

3. **風險：RAG 寫入後無法回灌**
   - 避免：保留 `raw_vlm_description` + `reasoning` 的更新規則

4. **風險：UI 狀態跨模組失效**
   - 避免：不要改 SessionState key 名稱

---

## 9) 一句話總結

把這個專案移植到其他系統時，請把它當成：
**「Upload Flow → VLM Core → HITL/RAG」三段式管線**，
UI 只是包裝層，核心價值在 `app/core + app/features + app/manufacturing + app/knowledge`。
