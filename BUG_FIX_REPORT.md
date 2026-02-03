# Bug 修復報告 - PaddleOCR 相容性問題

> **日期**: 2026-02-03  
> **版本**: v2.1.2  
> **狀態**: ✅ 已識別根本原因，提供多重解決方案

---

## 📋 問題摘要

### 問題 1：動態製程數量（✅ 已修復）
系統中硬編碼「96 種製程」，但實際知識庫有 78 種。

**解決方案**：實作動態讀取機制。
**狀態**：✅ 已完全修復

---

### 問題 2：PaddleOCR 初始化失敗（⚠️ 部分修復）

#### 錯誤 A：不支援的參數
**症狀**：
```
ValueError: Unknown argument: use_gpu
ValueError: Unknown argument: enable_mkldnn  
ValueError: Unknown argument: show_log
```

**原因**：PaddleOCR 3.4.0 移除了這些參數

**解決方案**：✅ 已修復
- 移除所有不支援的參數
- 只保留 `use_textline_orientation` 和 `lang`

---

#### 錯誤 B：PyTorch DLL 載入失敗（⚠️ 環境問題）
**症狀**：
```
OSError: [WinError 127] 找不到指定的程序。
Error loading "D:\python\Lib\site-packages\torch\lib\shm.dll" or one of its dependencies.
```

**根本原因**：
1. PaddleOCR 3.4.0 新增依賴 `paddlex`
2. `paddlex` 依賴 `modelscope`
3. `modelscope` 在導入時自動載入 `torch`
4. 系統中的 PyTorch 安裝損壞（DLL 檔案缺失或損壞）

**依賴鏈**：
```
PaddleOCR 3.4.0
  └─> paddlex
      └─> modelscope
          └─> torch (PyTorch) ❌ DLL 錯誤
```

**解決方案選項**：

##### 選項 1：修復 PyTorch（推薦）
```bash
# 完全重新安裝 PyTorch
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**注意**：需要關閉所有使用 Python 的程序

##### 選項 2：禁用 Model Source Check（部分有效）
```python
import os
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
```

**限制**：必須在 **Python 程序最開始** 設定，在任何模組導入前

##### 選項 3：降級 PaddleOCR（未測試）
```bash
pip install paddleocr==2.7.3
```

**注意**：舊版本可能有其他相容性問題

##### 選項 4：不使用 OCR 功能（臨時方案）
系統設計支援三種特徵提取方式：
- ✅ 幾何特徵分析（不依賴 PaddleOCR）
- ✅ 符號辨識（不依賴 PaddleOCR）
- ⚠️ OCR 文字辨識（依賴 PaddleOCR）

**使用方法**：
```python
pipeline = ManufacturingPipeline(
    use_ocr=False,      # ❌ 關閉 OCR
    use_geometry=True,  # ✅ 啟用幾何
    use_symbols=True    # ✅ 啟用符號
)
```

---

#### 錯誤 C：OneDNN 相容性問題（✅ 已修復）
**症狀**：
```
NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support 
[pir::ArrayAttribute<pir::DoubleAttribute>]
位置: onednn_instruction.cc:118
```

**原因**：PaddlePaddle 3.3.0 的 PIR 架構與 OneDNN 後端不完全相容

**解決方案**：✅ 已在代碼中實作
```python
import os
os.environ['FLAGS_use_mkldnn'] = 'False'
os.environ['FLAGS_use_onednn'] = 'False'

import paddle
paddle.set_flags({'FLAGS_use_mkldnn': False})
```

---

## 🔧 已修改的檔案

### 1. `app/manufacturing/extractors/ocr.py`
**修改內容**：
- ✅ 移除不支援的參數（`use_gpu`, `enable_mkldnn`, `show_log`）
- ✅ 新增環境變數設定（OneDNN 禁用、Model Source Check 禁用）
- ✅ 新增 `paddle.set_flags()` 確保 flags 生效

### 2. `aov_app.py`
**修改內容**：
- ✅ 在程序最開始設定環境變數
- ✅ 確保在所有 import 之前設定

### 3. `test_full_features.py`
**修改內容**：
- ✅ 同步環境變數設定
- ✅ 確保測試環境一致

### 4. 文檔更新
- ✅ `README.md` - 新增 PyTorch DLL 錯誤說明
- ✅ `CHANGELOG.md` - 記錄所有修改
- ✅ `AGENTS.md` - 更新製程數量描述
- ✅ `BUG_FIX_REPORT.md` (本文件) - 完整問題報告

---

## 🧪 驗證步驟

### 測試 1：驗證 PyTorch 安裝
```bash
python -c "import torch; print(f'PyTorch version: {torch.__version__}')"
```

**預期輸出**：
```
PyTorch version: 2.5.1+cu121
```

**如果失敗**：執行選項 1（重新安裝 PyTorch）

---

### 測試 2：驗證環境變數生效
```bash
python -c "import os; os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'; from paddleocr import PaddleOCR; print('Success')"
```

**預期輸出**：
```
[33mConnectivity check to the model hoster has been skipped...[0m
Success
```

---

### 測試 3：驗證系統啟動（不使用 OCR）
```bash
streamlit run aov_app.py
```

**操作**：
1. 不勾選「OCR 文字辨識」
2. 勾選「幾何特徵分析」和「符號辨識」
3. 上傳圖紙並執行辨識

**預期**：✅ 正常運作，不出現錯誤

---

### 測試 4：驗證完整功能（使用 OCR）
**前提**：PyTorch 已修復（測試 1 通過）

```bash
python test_full_features.py
```

**預期輸出**：
```
=== 測試完整功能（OCR + 幾何 + 符號）===
✅ 辨識成功！共找到 5 個製程預測
...
```

---

## 📊 修復狀態總結

| 問題 | 嚴重程度 | 狀態 | 解決方案 |
|------|----------|------|----------|
| 動態製程數量 | 🟡 中 | ✅ 已修復 | 實作 `total_processes` 屬性 |
| PaddleOCR 參數錯誤 | 🔴 高 | ✅ 已修復 | 移除不支援的參數 |
| PyTorch DLL 錯誤 | 🔴 高 | ⚠️ 環境問題 | 需重新安裝 PyTorch |
| OneDNN 相容性 | 🔴 高 | ✅ 已修復 | 環境變數禁用 OneDNN |

---

## 💡 給使用者的建議

### 情境 1：PyTorch 安裝正常
1. 關閉所有 Python 程序
2. 重新啟動 Streamlit：`streamlit run aov_app.py`
3. 可以使用全部三個特徵（OCR + 幾何 + 符號）

### 情境 2：PyTorch 安裝有問題
1. **臨時方案**：不勾選「OCR 文字辨識」，使用幾何+符號
2. **永久方案**：重新安裝 PyTorch（見上方步驟）

### 情境 3：不需要 OCR 功能
- 製程辨識主要依賴幾何特徵和符號
- OCR 文字是輔助功能
- 關閉 OCR 不影響核心功能

---

## 🚀 後續行動

### 立即行動（使用者）
- [ ] 關閉所有 Python 程序
- [ ] 重新啟動 Streamlit
- [ ] 測試不使用 OCR 的辨識功能

### 短期行動（使用者）
- [ ] 重新安裝 PyTorch（如果需要 OCR）
- [ ] 驗證全選功能正常運作

### 長期行動（開發者）
- [ ] 考慮替換為更輕量的 OCR 方案（如 EasyOCR）
- [ ] 將 OCR 功能設為完全可選的插件
- [ ] 新增更詳細的錯誤訊息和除錯指引

---

## 📝 技術備註

### PaddleOCR 3.4.0 重大變更
1. 新增 `paddlex` 依賴（增加了體積和複雜度）
2. 移除多個初始化參數（向下不相容）
3. 引入 `modelscope` 依賴（需要 PyTorch）

### PyTorch DLL 問題常見原因
1. 安裝不完整（網路中斷）
2. 與其他版本衝突
3. Windows Defender 或防毒軟體干擾
4. 磁碟空間不足

### OneDNN 相容性問題
- 影響版本：PaddlePaddle 3.x + OneDNN 3.6.2
- 根本原因：PIR 架構尚未完全支援
- 官方修復：預計 PaddlePaddle 3.4+

---

## 📚 參考資料

- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR
- PaddlePaddle 文檔: https://www.paddlepaddle.org.cn/
- PyTorch 安裝: https://pytorch.org/get-started/locally/
- Issue Tracker: (待建立)

---

**最後更新**：2026-02-03 22:45  
**報告人**：Sisyphus AI Agent  
**版本**：v2.1.2 (Bug Fix Report)
