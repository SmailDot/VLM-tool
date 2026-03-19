# NKUST 製程辨識系統 使用手冊

> **國立高雄科技大學 視覺實驗室**  
> Manufacturing Process Recognition from Engineering Drawings  
> Version: 2.1 (Enhanced) | 最後更新：2026-02-03

---

## 📖 系統簡介

**NKUST 製程辨識系統** 是專為工程圖紙分析設計的AI辨識工具。系統能夠自動分析工程圖紙內容，並識別所需的製造製程。

### ✨ 核心特色
- 🏭 **製程自動辨識**：支援多種製程類型（動態載入）
- 🤖 **VLM 視覺重建**：多視圖文字化描述與重點標示
- 📊 **信心度評分**：每個預測都附帶信心度與辨識依據
- 🎯 **專業領域**：針對工程圖紙(白底黑線)優化
- ⚡ **即時處理**：秒級辨識速度

---

## 🚀 快速開始

### 環境需求
- Python 3.8 或更高版本
- Windows / macOS / Linux

### 安裝步驟

#### 1. 安裝 Python 套件
```bash
# 進入專案目錄
cd AoV_Tool_V2

# 安裝依賴
pip install -r requirements.txt
```

**注意**: PaddleOCR 需要 PaddlePaddle 框架(可選):
```bash
# Windows
pip install paddlepaddle==2.6.1 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html

# 如果不安裝 PaddlePaddle，關閉 OCR 功能即可正常使用
```

#### 2. 啟動應用程式
```bash
streamlit run aov_app.py
```

#### 3. 開啟瀏覽器
系統會自動開啟瀏覽器，若沒有請手動訪問：
```
http://localhost:8501
```

---

## 📋 使用流程

### 步驟 1️⃣：上傳工程圖紙
1. 在左側「上傳工程圖紙」區塊選擇圖紙檔案
2. 支援格式: JPG, PNG, BMP
3. 建議解析度: **300 DPI 以上**

### 步驟 2️⃣：設定辨識選項
1. **VLM 設定**：
   - 🤖 啟用 VLM 視覺語言模型

2. **分析參數**：
   - 最低信心度門檻（由側邊欄設定）

### 步驟 3️⃣：執行辨識
1. 點擊 **「🚀 開始辨識製程」** 按鈕
2. 等待分析完成 (通常 1-3 秒)
3. 查看右側辨識結果

---

## 📊 辨識結果說明

### 信心度顏色標記
- 🟢 **綠色** (≥70%): 高信心度，強烈推薦
- 🟡 **黃色** (50-70%): 中等信心度，建議確認
- 🔴 **紅色** (<50%): 低信心度，需人工判斷

### 辨識依據
系統會顯示每個製程的辨識依據，例如：
- 「檢測到關鍵字: 折彎」
- 「檢測到幾何特徵: 折彎線 (3條)」
- 「檢測到符號: welding」

### 診斷資訊
展開「診斷資訊」可查看：
- 處理時間
- VLM 視覺描述內容
- 父圖上下文解析結果（若有上傳父圖）

---

## 🏭 支援的製程類型

系統支援多種製程類型，實際數量由 `process_lib_v2.json` 知識庫動態載入。

### 製程分類（8 大類）

### 切割類 (7 種)
繪圖者、排版、雷射切割、剪板機、CNC 裁切、水刀切割、線切割

### 折彎類 (5 種)
折彎、滾圓、滾弧、捲管、撐孔

### 焊接類 (14 種)
點焊、氬焊、電焊、CO2 焊接、錫焊、銅焊、鋁焊、雷射焊接等

### 表面處理 (18 種)
噴砂、酸洗、烤漆、粉體烤漆、陽極處理、鍍鋅、電鍍等

### 組裝類 (20 種)
自攻牙、螺絲、鉚接、拉釘、銑牙、車牙、車削、植釘等

### 檢驗類 (12 種)
成品全檢、尺寸檢驗、外觀檢驗、氣密測試、耐壓測試等

### 清潔類 (3 種)
脫脂、拋光、化學清洗

### 其他 (17 種)
鑽孔、攻牙、倒角、磨削、雕刻、雷射雕刻、沖壓等

---

## ⚙️ 進階功能

### 使用 Python API

```python
from app.manufacturing import ManufacturingPipeline

# 初始化管線（VLM-only）
pipeline = ManufacturingPipeline(use_vlm=True)

# 辨識圖紙
result = pipeline.recognize("drawing.jpg", top_n=5)

# 顯示結果
for pred in result.predictions:
    print(f"{pred.process_name}: {pred.confidence:.2%}")
    print(f"  依據: {', '.join(pred.evidence)}")
```

### 批次處理

```python
images = ["drawing1.jpg", "drawing2.jpg", "drawing3.jpg"]
results = pipeline.batch_recognize(images, top_n=5)

for i, result in enumerate(results):
    print(f"\n圖紙 {i+1}:")
    for pred in result.predictions[:3]:
        print(f"  {pred.process_name}: {pred.confidence:.2%}")
```

---

## 🛠️ 疑難排解

### ❌ 問題 1：VLM 功能無法使用
**症狀**：VLM 無法返回視覺描述

**解決方案**：
1. 確認 LM Studio 已啟動，且 API 可連線（預設 http://localhost:1234）
2. 檢查所選模型是否已載入並可推論

### ❌ 問題 2：未檢測到任何製程
**症狀**：辨識結果為空

**解決方案**：
1. 降低信心度門檻 (調整為 0.2-0.3)
2. 確認圖紙解析度 (建議 300 DPI 以上)
3. 檢查圖紙類型是否為工程圖 (白底黑線)

### ❌ 問題 3：辨識結果不準確
**症狀**：推薦的製程不符合預期

**解決方案**：
1. 檢查辨識依據是否合理
2. 提高圖紙品質 (更清晰的掃描或圖片)
3. 人工確認低信心度結果
4. 提供反饋以改進系統

---

## 📂 檔案結構

```
AoV_Tool_V2/
├── aov_app.py                          # 主應用程式 (Streamlit UI)
├── requirements.txt                    # Python 依賴清單
│
├── app/
│   └── manufacturing/                  # 製程辨識核心模組
│       ├── schema.py                   # 資料結構定義
│       ├── process_lib.json            # 製程定義 (v1, 測試用)
│       ├── process_lib_v2.json         # 製程定義 (v2, 正式版)
│       ├── pipeline.py                 # 管線協調器
│       ├── extractors/                 # 特徵與輸入解析器
│       │   ├── ocr.py                  # OCR 模組（父圖/BOM 掃描使用）
│       │   ├── geometry.py             # 幾何分析模組（保留）
│       │   ├── symbols.py              # 符號模組（保留）
│       │   ├── tolerance_parser.py     # 公差解析
│       │   ├── parent_parser.py        # 父圖解析器
│       │   └── embeddings.py           # 視覺嵌入 (可選)
│       └── decision/                   # 決策引擎
│           ├── engine_v2.py            # 多模態決策引擎
│           └── rules.py                # 規則定義
│
├── components/                         # UI 元件
│   ├── style.py                        # 樣式設定
│   ├── sidebar.py                      # 側邊欄元件
│   └── visualizer.py                   # 視覺化元件
│
├── test_*.py                           # 測試腳本
│   ├── test_manufacturing.py           # 製程辨識測試
│   ├── test_dimension_filter.py        # 尺寸過濾測試
│   ├── test_tolerance_detection.py     # 公差檢測測試
│   └── test_dual_image.py              # 雙圖模式測試
│
├── 製程步驟項目提問 20260126-確認.xlsx    # 製程資料來源
├── new.xlsx                            # 製程定義表
│
├── outputs/                            # 系統輸出目錄
├── uploads/                            # 使用者上傳目錄
│
└── 文件/
    ├── README.md                       # 使用手冊 (本文件)
    ├── AGENTS.md                       # AI Agent 上下文
    ├── MANUFACTURING.md                # 技術架構文件
    ├── MANUFACTURING_USER_GUIDE.md     # 詳細使用手冊
    ├── NEW_FEATURES_SUMMARY.md         # 新功能摘要 (v2.1)
    ├── DIMENSION_FILTER_IMPLEMENTATION.md  # 尺寸過濾實作說明
    └── DUAL_IMAGE_FEATURE.md           # 雙圖模式說明
```

---

## 📚 相關文件

### 核心文件
- **README.md** (本文件): 快速入門與使用指南
- **MANUFACTURING.md**: 技術架構與實作細節
- **MANUFACTURING_USER_GUIDE.md**: 詳細使用手冊

### 新功能文件 (v2.1)
- **NEW_FEATURES_SUMMARY.md**: 新功能總覽
- **DIMENSION_FILTER_IMPLEMENTATION.md**: 尺寸線過濾技術說明
- **DUAL_IMAGE_FEATURE.md**: 雙圖模式（父圖+子圖）使用說明

### 開發文件
- **AGENTS.md**: AI Agent 開發上下文

---

## 🎯 系統架構

```
工程圖紙 (JPG/PNG)
    ↓
VLM 視覺理解（多視圖 + BOM/父圖上下文）
    ↓
RAG 參考案例增強（可選）
    ↓
視覺重建結果與診斷資訊
```

---

## 👥 開發團隊

**實驗室**: 國立高雄科技大學 視覺實驗室  
**專案**: NKUST AoV Tool - Manufacturing Process Recognition  
**版本**: 2.1.1 (Dynamic Process Count + OneDNN Fix)  
**日期**: 2026-02-03

---

## 📞 技術支援

若遇到問題，請依序嘗試：
1. 查看本手冊的「疑難排解」章節
2. 檢查診斷資訊中的錯誤訊息
3. 參考 MANUFACTURING_USER_GUIDE.md 詳細說明
4. 聯繫實驗室助教或指導教授

---

**祝你使用愉快！** 🎉

**Version 2.1.1 更新重點 (2026-02-03)**：
- ✅ **動態製程數量**: 從知識庫自動讀取，不再硬編碼「96 種」
- ✅ **OneDNN 錯誤修復**: 解決全選三個辨識選項時的 PIR 相容性問題
  - 環境變數禁用 OneDNN: `FLAGS_use_mkldnn=0`, `FLAGS_use_onednn=0`
  - PaddleOCR 初始化參數: `enable_mkldnn=False`, `use_gpu=False`
- ✅ **新增測試檔案**: `test_full_features.py` 驗證全選功能

**Version 2.1 更新重點**：
- ✅ **程式碼大清理**: 移除所有舊版遺留檔案
  - 刪除影像演算法模組 (`app/vision/`, `app/core/`)
  - 刪除 Auto Tune 優化器、知識庫模組
  - 刪除 n8n 整合、前端庫（lib/）
  - 刪除舊版測試、歷史報告文件
- ✅ **新增功能** (v2.1):
  - 尺寸輔助線智慧過濾（減少 30-50% 雜訊）
  - 公差自動檢測與精密製程推薦
  - 雙圖辨識模式（父圖+子圖）
- ✅ **專注核心**: 工程圖紙製程辨識
- ✅ **簡化架構**: 清爽的目錄結構，易於維護
