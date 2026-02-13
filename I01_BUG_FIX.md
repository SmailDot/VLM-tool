# I01 Bug 修復報告

## 錯誤描述

**錯誤訊息**:
```
StreamlitAPIException: The default value 'I01' is not part of the options. 
Please make sure that every default values also exists in the options.
```

**發生位置**: `aov_app.py` 第 1011 行（知識庫管理頁面）

**發生時機**: 
- 使用者啟動應用程式後，**直接切換到「知識庫管理」Tab**
- 知識庫中有條目，且 `correct_processes` 包含 `I01` 等製程代碼
- Streamlit multiselect 的 `default` 參數包含不在 `options` 中的值

---

## 根本原因

### 問題代碼（修復前）

```python
# aov_app.py 第 996-1000 行
pipeline = st.session_state.mfg_pipeline
if pipeline is not None:
    all_process_ids = list(pipeline.decision_engine.processes.keys())
else:
    all_process_ids = []  # ← 這裡是問題！
```

### 原因分析

1. **Pipeline 初始化時機**:
   - `st.session_state.mfg_pipeline` 只在以下情況初始化：
     - 使用者點擊「開始辨識製程」按鈕（第 340-347 行）
     - 使用者點擊「🔄 是，重新辨識」按鈕（Task 5，第 716-722 行）
   
2. **知識庫管理頁面載入時機**:
   - 使用者可以在**未執行任何辨識**的情況下，直接切換到「知識庫管理」Tab
   - 此時 `st.session_state.mfg_pipeline` 為 `None`（初始值）
   
3. **Multiselect 衝突**:
   - `all_process_ids = []`（空清單）
   - 知識庫條目的 `correct_processes = ['I01', 'J01', 'E01', ...]`（78 個製程中的某些）
   - Streamlit 檢查 `default` 值是否在 `options` 中
   - `'I01' not in []` → 拋出異常

---

## 修復方案

### 修復後代碼

```python
# aov_app.py 第 991-1010 行
from app.knowledge.manager import KnowledgeBaseManager
import json

kb_manager = KnowledgeBaseManager()
entries = kb_manager.db

# Get process IDs - either from pipeline or directly from JSON
pipeline = st.session_state.mfg_pipeline
if pipeline is not None:
    all_process_ids = list(pipeline.decision_engine.processes.keys())
else:
    # Pipeline not initialized - load directly from process_lib_v2.json
    try:
        process_lib_path = "app/manufacturing/process_lib_v2.json"
        with open(process_lib_path, 'r', encoding='utf-8') as f:
            process_data = json.load(f)
            all_process_ids = list(process_data.get('processes', {}).keys())
    except Exception as e:
        st.error(f"無法載入製程清單: {e}")
        all_process_ids = []
```

### 修復邏輯

1. **優先使用 Pipeline**（已初始化時）:
   - 從 `pipeline.decision_engine.processes` 獲取製程清單
   - 保持原有行為，確保一致性

2. **回退到 JSON 直接載入**（Pipeline 未初始化時）:
   - 直接讀取 `process_lib_v2.json`
   - 從 `processes` 字典中提取所有 process_id
   - 返回完整的 78 個製程代碼清單

3. **錯誤處理**:
   - 如果 JSON 載入失敗，顯示錯誤訊息
   - 回退到空清單（最差情況）

---

## 驗證

### 測試步驟

1. **重現原始錯誤**（修復前）:
   ```bash
   streamlit run aov_app.py
   ```
   - 不要點擊任何辨識按鈕
   - 直接切換到「知識庫管理」Tab
   - **預期**: 拋出 `StreamlitAPIException: The default value 'I01' is not part of the options`

2. **驗證修復**（修復後）:
   ```bash
   streamlit run aov_app.py
   ```
   - 不要點擊任何辨識按鈕
   - 直接切換到「知識庫管理」Tab
   - **預期**: 正常顯示知識庫條目
   - **預期**: multiselect 下拉清單包含所有 78 個製程
   - **預期**: 預設值 `I01`, `J01` 等正確顯示

3. **檢查製程清單完整性**:
   ```python
   import json
   with open('app/manufacturing/process_lib_v2.json', 'r', encoding='utf-8') as f:
       data = json.load(f)
       processes = data['processes']
       print(f"Total processes: {len(processes)}")
       print(f"I01 exists: {'I01' in processes}")
   ```
   **預期輸出**:
   ```
   Total processes: 78
   I01 exists: True
   ```

---

## 其他潛在問題點檢查

### 檢查 1: 主辨識頁面的 process_defs

**位置**: `aov_app.py` 第 450-460 行

```python
pipeline = st.session_state.mfg_pipeline
process_defs: Dict[str, Dict[str, object]] = {}
if pipeline is not None:
    process_defs = {...}
```

**分析**: 
- ✅ **無問題** - 這段代碼在 `if st.session_state.recognition_result is not None:` 條件內（第 419 行）
- 如果有辨識結果，pipeline 必定已初始化
- 不需要回退機制

### 檢查 2: 手動輸入製程功能（Task 4）

**位置**: `aov_app.py` 第 533-653 行

**分析**:
- ✅ **無問題** - 同樣在 `if recognition_result is not None:` 條件內
- 使用 `process_defs` 字典進行匹配
- 只有在執行過辨識後才會顯示

### 檢查 3: 其他使用 pipeline.decision_engine 的地方

**搜尋結果**: 只有兩處使用
1. `aov_app.py:459` - 主辨識頁面（已確認無問題）
2. `aov_app.py:1000` - 知識庫管理頁面（**已修復**）

---

## 歷史記錄

根據使用者描述，這個問題在專案建置過程中出現過**至少 4 次**。

### 可能的重複原因

1. **多次重構知識庫管理頁面**:
   - 每次重構時都重新寫了 `all_process_ids` 邏輯
   - 忘記添加 Pipeline 未初始化的回退機制

2. **Session State 初始化時機不明確**:
   - Pipeline 只在特定操作時初始化
   - 沒有在應用程式啟動時預初始化

3. **缺乏防禦性編程**:
   - 假設 Pipeline 總是存在
   - 沒有處理 `None` 狀態

### 建議的預防措施

1. **添加 Pipeline 初始化檢查輔助函數**:
   ```python
   def get_all_process_ids() -> List[str]:
       """Get all process IDs from pipeline or JSON fallback"""
       pipeline = st.session_state.mfg_pipeline
       if pipeline is not None:
           return list(pipeline.decision_engine.processes.keys())
       else:
           # Fallback to JSON
           try:
               with open('app/manufacturing/process_lib_v2.json', 'r', encoding='utf-8') as f:
                   data = json.load(f)
                   return list(data.get('processes', {}).keys())
           except:
               return []
   ```

2. **在應用程式啟動時預載製程清單**:
   ```python
   # At the top of aov_app.py, after st.set_page_config
   if "all_process_ids_cache" not in st.session_state:
       try:
           with open('app/manufacturing/process_lib_v2.json', 'r', encoding='utf-8') as f:
               data = json.load(f)
               st.session_state.all_process_ids_cache = list(data['processes'].keys())
       except:
           st.session_state.all_process_ids_cache = []
   ```

3. **使用 @st.cache_data 緩存製程清單**:
   ```python
   @st.cache_data
   def load_process_ids() -> List[str]:
       """Load process IDs from JSON (cached)"""
       try:
           with open('app/manufacturing/process_lib_v2.json', 'r', encoding='utf-8') as f:
               data = json.load(f)
               return list(data.get('processes', {}).keys())
       except:
           return []
   ```

---

## 結論

### 修復內容
- ✅ 修復知識庫管理頁面的 `I01` 錯誤
- ✅ 添加 JSON 直接載入回退機制
- ✅ 添加錯誤處理

### 受影響的檔案
- `aov_app.py` (第 991-1010 行)

### 測試狀態
- ⏳ 等待測試驗證

### 後續建議
- 考慮實作上述預防措施，避免問題再次出現
- 在應用程式啟動時預載製程清單
- 創建輔助函數統一處理製程清單獲取邏輯

---

**修復日期**: 2026-02-13  
**修復者**: Sisyphus Agent  
**相關 Issue**: I01 不在 multiselect options 中（第 5 次出現）
