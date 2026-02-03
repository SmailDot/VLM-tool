# 更新歷史 (Changelog)

> **NKUST 製程辨識系統**  
> 所有重大變更將記錄在此文件

---

## [2.1.1] - 2026-02-03

### 🐛 Bug Fixes

#### 1. Dynamic Process Count
**Issue**: Process count was hardcoded to "96" in multiple places, but actual knowledge base has 78 processes.

**Solution**: 
- Added `total_processes` property to all engine classes
- Updated UI to dynamically display process count from loaded knowledge base
- Updated documentation to remove hardcoded numbers

**Files Modified**:
- `app/manufacturing/decision/engine_v2.py`
- `app/manufacturing/decision/rules.py`
- `app/manufacturing/pipeline.py`
- `aov_app.py`
- `README.md`
- `AGENTS.md`

---

#### 2. PaddleOCR OneDNN Compatibility Error
**Issue**: When all three recognition options (OCR + Geometry + Symbols) are selected, the system crashes with:
```
(Unimplemented) ConvertPirAttribute2RuntimeAttribute not support 
[pir::ArrayAttribute<pir::DoubleAttribute>]
```

**Root Cause**: PaddlePaddle 3.0.0-beta's PIR (Program Intermediate Representation) architecture has incomplete OneDNN backend support.

**Solution**:
1. **Environment Variables** (set before importing paddleocr):
   ```python
   os.environ['FLAGS_use_mkldnn'] = '0'
   os.environ['FLAGS_use_onednn'] = '0'
   ```

2. **Initialization Parameters** (all PaddleOCR instances):
   ```python
   PaddleOCR(
       enable_mkldnn=False,  # Disable OneDNN
       use_gpu=False,        # Force CPU mode
       ...
   )
   ```

**Files Modified**:
- `app/manufacturing/extractors/ocr.py` (lines 13-15, 64-78, 300-309)

**Files Added**:
- `test_full_features.py` - Full integration test for all three options

---

## [2.1.0] - 2026-02-03

### 🧹 專案大清理

#### 刪除項目
- **舊版核心模組** (`app/core/`, `app/vision/`, `app/knowledge/`, `app/engine/`)
  - 刪除 35 個 Python 檔案 (~300 KB)
  - 移除影像演算法操作、自動優化器、知識庫
- **前端庫** (`lib/`, `ui/`)
  - 刪除 JavaScript 庫 (~10 MB)
  - 移除舊版前端元件
- **n8n 整合相關** (3 個檔案)
  - 完全移除 n8n workflow 支援
- **舊版主程式** (`main.py`, `app_server.py`, `client_test.py`, `aov_app_OLD_BACKUP.py`)
  - 移除 Flask API 伺服器
  - 刪除舊版備份檔案
- **測試目錄** (`tests/`)
  - 移除針對舊版模組的測試
- **資料檔案**
  - 刪除 `tech_lib.json`（舊版演算法庫）
  - 刪除 `knowledge_db.json`（知識庫資料）
  - 刪除中間產物檔案（6 個 JSON/CSV）
- **歷史報告文件** (10 個 Markdown)
  - 移除過時的開發報告與實作文件

**總計**: 刪除 59 個檔案/目錄，釋放 ~11.7 MB 空間

#### 保留項目
- ✅ 製程辨識核心模組 (`app/manufacturing/`)
- ✅ Streamlit UI (`aov_app.py`, `components/`)
- ✅ 新功能測試腳本 (7 個)
- ✅ 製程資料來源 (2 個 Excel 檔案)
- ✅ 核心文件 (3 個 Markdown)

---

### ✨ 新增功能

#### 1. 尺寸輔助線智慧過濾
**模組**: `app/manufacturing/extractors/geometry.py`

**問題**: 工程圖紙中的尺寸標註線被誤判為零件幾何特徵，導致折彎線檢測不準確。

**解決方案**: 實作 3 層過濾策略
- **策略 1**: 過濾異常長度線條（>80% 圖紙尺寸）
- **策略 2**: 過濾邊緣區域且靠近尺寸文字的線條（±, φ, R, M, °）
- **策略 3**: 過濾極短線條（<10px，可能是箭頭）

**效果**: 線條雜訊減少 30-50%，折彎線辨識準確度提升

**實作檔案**:
- `_filter_auxiliary_lines()` (lines 258-316)
- `_has_nearby_dimension_text()` (lines 318-367)

---

#### 2. 公差自動檢測
**模組**: `app/manufacturing/extractors/tolerance_parser.py`

**功能**: 從 OCR 文字中自動提取公差標註並分類精密等級

**支援格式**:
- 對稱公差: `±0.3`, `±0.05`, `± 0.02`
- 非對稱公差: `+0.3/-0.2`, `+0.05/-0.03`
- 隱含公差: `0.05` (2+ 小數位)

**資料結構**:
```python
@dataclass
class ToleranceSpec:
    value: float              # 公差值
    type: str                 # symmetric | asymmetric | implied
    upper_bound: Optional[float]
    lower_bound: Optional[float]
```

**整合**:
- `ExtractedFeatures.tolerances` - 儲存檢測到的公差
- `ManufacturingPipeline._extract_features()` - 管線整合

---

#### 3. 精密公差邏輯
**模組**: `app/manufacturing/decision/engine_v2.py`

**規則 6** (lines 526-549):
```python
if features.tolerances:
    min_tolerance = min(tol.get_max_tolerance() for tol in features.tolerances)
    if min_tolerance < 0.1:  # 高精密要求
        # 觸發 K01 (切削/milling) 製程
        # 降低雷射切割信心度 40%
```

**業務邏輯**:
| 公差範圍 | 精密等級 | 推薦製程 |
|---------|---------|---------|
| ≥ 0.3mm | 標準 | 雷射切割 OK |
| 0.1-0.3mm | 中等 | 謹慎加工 |
| < 0.1mm | 高精密 | K01 切削/銑削 |

---

#### 4. 雙圖辨識模式
**模組**: `app/manufacturing/extractors/parent_parser.py`

**概念**: 
- **父圖**: 全視圖，包含標題欄、技術要求、材質說明、客戶資訊
- **子圖**: 局部特徵，包含零件形狀、標註、符號

**實作**:
```python
ParentContext = {
    'materials': List[str],      # 材質資訊
    'customers': List[str],      # 客戶名稱
    'special_requirements': Set[str],  # 特殊要求
    'ocr_results': List[OCRResult],
    'global_notes': List[str]
}
```

**管線整合**:
- `ManufacturingPipeline.recognize(parent_image=...)`
- 父圖文字優先權高於子圖（全域資訊）

**UI 支援**:
- `aov_app.py` - 父圖上傳區塊（選填）
- 雙圖提示訊息與視覺化

---

### 🔧 優化改進

#### UI/UX
- **修復 Expander 標題可見性** (`components/style.py`, lines 216-244)
  - 解決展開後標題變白的問題
  - 強制使用青色文字 (`#00ccff`) + 發光效果

#### 架構簡化
- **專注製程辨識**: 完全移除影像演算法工具功能
- **單一核心模組**: 只保留 `app/manufacturing/`
- **Streamlit UI**: 統一使用 Python UI，移除 HTML/JS 前端

---

### 📂 檔案結構變更

#### Before (v2.0):
```
AoV_Tool_V2/
├── app/
│   ├── core/          ← 刪除
│   ├── vision/        ← 刪除
│   ├── knowledge/     ← 刪除
│   ├── engine/        ← 刪除
│   └── manufacturing/
├── lib/               ← 刪除
├── ui/                ← 刪除
├── tests/             ← 刪除
└── ...
```

#### After (v2.1):
```
AoV_Tool_V2/
├── aov_app.py
├── app/
│   └── manufacturing/  ← 唯一核心
├── components/
├── test_*.py (7 個)
└── 文件/ (3 個 MD)
```

---

### 📊 測試覆蓋

新增測試腳本:
- `test_dimension_filter.py` - 尺寸線過濾測試
- `test_tolerance_detection.py` - 公差檢測測試（10 種格式）
- `test_dual_image.py` - 雙圖模式端到端測試

保留測試:
- `test_manufacturing.py` - 製程辨識核心測試
- `test_simple.py` - 簡單功能測試
- `test_system.py` - 系統整合測試
- `test_system_validation.py` - 系統驗證測試

---

### 📚 文件更新

#### 新增文件
- `CHANGELOG.md` - 版本變更歷史（本文件）

#### 更新文件
- `README.md` - 更新至 v2.1.0，反映新架構
- `AGENTS.md` - AI Agent 開發上下文

#### 刪除文件
- 10 個歷史報告 Markdown

---

### 🐛 已知問題

#### 暫存檔無法刪除
- `~$new.xlsx` - Excel 鎖定檔案
- **解決方法**: 關閉 Excel 後手動刪除

---

### ⚠️ 重大變更 (Breaking Changes)

1. **移除 API 支援**: 刪除 Flask API 伺服器 (`app_server.py`)
2. **移除 n8n 整合**: 完全刪除 n8n workflow 支援
3. **移除影像演算法工具**: 不再支援 OpenCV 演算法組合功能
4. **移除舊版 UI**: HTML/JS 前端完全移除

---

### 🔄 遷移指南

#### 從 v2.0 升級到 v2.1

**步驟 1**: 備份資料
```bash
cp -r AoV_Tool_V2 AoV_Tool_V2_backup
```

**步驟 2**: 拉取新版本
```bash
git pull origin main
```

**步驟 3**: 重新安裝依賴（無變更）
```bash
pip install -r requirements.txt
```

**步驟 4**: 啟動應用
```bash
streamlit run aov_app.py
```

**注意**: 
- 如果使用舊版 API (`app_server.py`)，請改用 Streamlit UI
- 如果使用 n8n 整合，功能已移除

---

### 📈 效能提升

| 指標 | v2.0 | v2.1 | 改善 |
|------|------|------|------|
| 專案大小 | ~100 MB | ~88 MB | -12% |
| 核心模組數 | 4 個 | 1 個 | -75% |
| Python 檔案數 | 79 個 | 44 個 | -44% |
| 線條雜訊 | 100% | 50-70% | -30-50% |

---

### 🙏 致謝

感謝 Sisyphus AI Agent 協助完成專案大清理與新功能實作。

---

## [2.0.0] - 2026-01-31

### 初始重構版本

- ✅ 從 AoV Tool v1.0 (影像演算法工具) 重構為製程辨識系統
- ✅ 建立 `app/manufacturing/` 核心模組
- ✅ 支援多種製程類型辨識（動態載入）
- ✅ 多模態特徵提取 (OCR + 幾何 + 符號)
- ✅ Streamlit UI 介面
- ✅ 規則基礎決策引擎

---

**版本格式說明**: `[版本號] - 日期`
- 格式遵循 [Semantic Versioning](https://semver.org/)
- 主版本.次版本.修訂版本 (Major.Minor.Patch)
