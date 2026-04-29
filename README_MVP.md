# MVP 多 Agent 製程辨識系統技術文件

## 整個系統框架粗略設定

<img width="4094" height="2282" alt="膠帶" src="https://github.com/user-attachments/assets/1d14ac52-0a74-4dfb-83dc-8ecabd00399d" />

---

## 1. 系統概述

本系統是一個基於多 Agent 協作架構的視覺辨識管線（Pipeline），旨在透過大語言模型（VLM）與檢索增強生成（RAG）技術，自動從工程圖中辨識製造製程。系統採用「先觀察、後推理」的分層架構，將視覺特徵提取與領域知識判斷分離，以提升辨識的精確度與專業性。

---

## 2. 系統架構與流程圖

系統流程分為兩個主要階段：**視覺觀察（Visual Observer）**與**平行領域專家推理（Domain Expert Agents）**。

```
[輸入：工程圖]
(父圖 PDF + 子視圖 3~4 張 JPG，或僅父圖 PDF — 缺子圖時自動以 PDF 首頁充當)
        |
        v
+------------------------------------------+
|  Step 1: Visual Observer  (1 call)        |
|  純視覺特徵描述，禁止命名製程             |
|  輸出：5 段繁中描述（150~250字）          |
+---------------------+--------------------+
                      |
                      | Step1 自然語言描述 + 原始圖面
                      v
+------------------------------------------+
|  Step 2: 4 Parallel Domain Expert Agents  |
|  (ThreadPoolExecutor，4 calls 並行)        |
|  每個 Agent 接收 RAG 注入的候選清單       |
+---+----------+----------+----------+-----+
    |          |          |          |
[Agent 1]  [Agent 2]  [Agent 3]  [Agent 4]
 幾何成型   結構結合   表面工程   品質規範
    |          |          |          |
    +----------+----+-----+----------+
                    |
                    v
             [Step 3: 已停用]
       彙整作業由團隊外部處理
       Pipeline 直接回傳 Step 2 輸出
```

---

## 3. 詳細管線步驟

### Step 1：視覺觀察員 (Visual Observer)

- **輸入**：工程圖父圖（PDF 轉影像，200 DPI）+ 子視圖 3~4 張（JPG）
- **職責**：執行純粹的視覺特徵提取。**禁止在觀察階段直接命名或輸出製程編號**，避免模型幻覺或過早定論。
- **衝突原則**：若圖面與描述衝突，以圖面為準。

**輸出格式**：150~250 字繁體中文，5 段固定結構：

| 段落 | 說明 |
|------|------|
| 1. 材料/表面標註 | 材質文字、表面符號、塗裝色號、防烤/遮蔽標記 |
| 2. 幾何特徵 | 折彎線、孔位、螺紋孔、沉頭孔、切口、圓管、特殊形狀 |
| 3. 焊接/接合特徵 | 焊接符號、點焊標記、鉚合符號、組立關係 |
| 4. 文字標註與備註 | 所有中英文備註、公差要求、特殊加工指示 |
| 5. 整體判斷 | 零件類型（單件鈑金/組合件/管件）、複雜度 |

---

### Step 2：平行領域專家 Agent (Domain Experts)

系統透過 `ThreadPoolExecutor` 同時啟動 4 個專家 Agent，各 Agent 僅關注其負責領域，並參考 RAG 注入的候選清單進行推理。

**每個 Agent 輸出格式（每製程一行）：**
```
[製程編號] [製程名稱] | VLM:[0.00] | 依據：[具體觀察與推論過程]
```

> VLM 評分採 0.00–1.00、**0.01 級距**（例：0.37、0.62、0.83），prompt 已明文禁止收斂至 0.05 級距以提升辨識度。

#### Agent 職責分配

| Agent | 領域 | 負責製程 |
|-------|------|---------|
| **Agent 1** | 幾何成型（Geometry & Shaping） | C01 單機切割、C03 複合機、C05 M3048、D01 折彎、D10 折彎整平、E11 燕巢傳統銑床、F05 廠內捲圓、F06 廠內裁管、K01 燕巢切削 |
| **Agent 2** | 結構結合/熱處理（Structural Joining & Thermal） | D06 植零件、F01 焊接、F03 SPOT、F14 焊接研磨、F23 應力消除、Q01 組裝 |
| **Agent 3** | 表面工程/化學（Surface & Chemical Engineering） | E01 去毛邊、E02 去毛邊2、F11 廠內烤漆、H01 除焦洗淨、H03 包裝網蓋貼、H04 鋁洗淨、H06 脫脂洗淨、H14 廠內鈍化、O02 設計雷射雕刻、Q04 清潔/脫脂/鉻酸鹽、Q07 防烤/表處遮蔽 |
| **Agent 4** | 品質規範/環境（QA & Environment） | H26 燕巢無塵室清潔、H27 燕巢無塵室包裝、I02 成品全檢2、I04 測漏全檢、I12 保壓測試、I19 燕巢無塵室成品全檢、Q11 燕巢無塵室組裝 |

**共通評分原則：**
- 任意單一視角（正/俯/側/等角）看到特徵即可觸發
- 有疑問時，INCLUDE 並給低分，勿省略
- 禁止在 Agent 階段執行互斥或依賴邏輯（交由外部彙整）
- 禁止使用 LaTeX 符號，一律使用 Unicode：φ、°、≥、≤

---

### Step 3：已停用

Step 3 彙整功能目前已停用，製程最終決策由團隊外部系統處理。Pipeline 直接回傳 Step 2 的 4 個 Agent 輸出結果。

---

## 4. RAG 機制說明

### 現狀（靜態注入）

目前 RAG 候選清單由 `製程步驟項目提問-自然描述版.xlsx` 靜態預填，依製程類別分組注入至對應 Agent。

**RAG 注入格式：**
```
[製程編號] [製程名稱]
自然語言描述：{製程的自然語言觸發條件說明，供 VLM 作為辨識小抄}
```

> 早期版本曾在每筆候選之後固定填入 `RAG relevance: 0.80`，並在 Agent 輸出中保留 `RAG:[相關度]` 欄位；
> 為避免 VLM 被假相關度誤導，現已將該欄位整批移除，等真實向量檢索接上後再恢復。

### 未來（動態檢索）

未來將接 FAISS 向量資料庫，透過 metadata filter 按類別動態檢索：

| Agent | Metadata Filter |
|-------|----------------|
| Agent 1 | `category IN ["幾何成型"]` |
| Agent 2 | `category IN ["結構結合", "熱處理"]` |
| Agent 3 | `category IN ["表面工程", "化學處理"]` |
| Agent 4 | `category IN ["品質規範", "環境要求"]` |

新增製程只需：在 xlsx 加一行（含製程編號、自然語言描述、類別標籤）→ 重新 embed → 更新向量資料庫，Prompt 無需修改。

### 信心度計算公式

$$ \text{Final Score} = \alpha \cdot \text{VLM Score} + (1-\alpha) \cdot \text{RAG Score} $$

其中 **α = 0.6**（偏重 VLM 視覺判斷），RAG 向量相似度為輔。

---

## 5. CLI 使用說明

```bash
# 執行 test_jpg/ 內所有可用 Group
python -m mvp.run

# 指定單一或多個 Group
python -m mvp.run --group 108-001416-13A
python -m mvp.run --group 108-001416-13A TSDH-230-3

# 列出目前支援的所有 Group ID
python -m mvp.run --list

# ★ 任意路徑輸入（不必把檔案丟進 test_jpg/）
python -m mvp.run --path "D:/somewhere/folder"          # 任意資料夾，套用同一套 discovery
python -m mvp.run --path "D:/somewhere/部品圖.pdf"      # 單一 PDF — 視為單群組的父圖
python -m mvp.run --path "D:/somewhere/view.jpg"        # 單張影像 — 視為單群組的子圖
python -m mvp.run --path "D:/somewhere/folder" --list   # 預覽該資料夾掃出的 Group

# 圖像傳送模式
python -m mvp.run --no-parent      # 跳過父圖，只送子視圖
python -m mvp.run --parent-only    # 只送父圖，不送子視圖

# 效能調整（Step 2 並行執行緒數，預設 4）
python -m mvp.run --workers 2
```

**僅含父圖 PDF 的 fallback：**
若某 Group 只有父圖 PDF、沒有任何子視圖，Pipeline 會自動把 PDF 首頁渲染後當作唯一子圖，
讓 default / `--no-parent` / `--parent-only` 三種模式皆可正常執行。

**輸出路徑：** `test_output/mvp_<group>_<mode>_<timestamp>.txt`
其中 `<mode>` 為 `full` / `child-only` / `parent-only`。

---

## 6. 可用測試 Group

| Group ID | 說明 |
|----------|------|
| `108-001416-13A` | 人類加註版（含正/俯/側視圖） |
| `161-01489-00_A` | 人類未加註版（含仰視/俯視/側視/立體圖） |
| `161-01757-00_A` | 人類未加註版（含前/俯/側/立體圖） |
| `5010-555691-13A` | 含前/俯/側/立體圖 |
| `5010-586800-11A` | 含前/俯/側/立體圖 |
| `F0050-00_耐震ブラケット` | 含前/俯/側視圖 |
| `TSDH-230-3` | 含俯/側/立體圖 |

---

## 7. 檔案結構

```
mvp/
├── __init__.py       # Package 標記
├── client.py         # VLM 請求封裝（OpenAI-compatible API 調用）
├── prompts.py        # 所有 System Prompt 與 RAG 靜態注入
│                     #   • STEP1_SYSTEM / STEP1_USER
│                     #   • AGENT_1~4_SYSTEM + RAG 注入字串
│                     #   • AGENTS 登錄表（名稱 + prompt）
├── pipeline.py       # MVPPipeline — 兩步驟核心協調器
│                     #   • Step 1：呼叫 Visual Observer
│                     #   • Step 2：ThreadPool 並行呼叫 4 Agents
│                     #   • Step 3：已停用
└── run.py            # CLI 執行器
                      #   • 參數解析（--group / --path / --workers / --no-parent / --parent-only）
                      #   • test_jpg/ 與任意 --path 的 group 自動探勘
                      #   • PDF → 影像轉換（PDFImageExtractor）
                      #   • 缺子圖時的 PDF-as-child fallback
                      #   • 結果寫入 test_output/
```

---

## 8. 已知限制

| 項目 | 說明 |
|------|------|
| 父圖規格 | 一律使用人類未加註 PDF（200 DPI），確保 VLM 不受人工提示影響 |
| RAG 靜態注入 | 目前僅有「自然語言描述」的靜態候選清單，尚未接真實向量檢索；先前的 `RAG relevance: 0.80` 佔位欄位已整批移除 |
| Step 3 停用 | 4 個 Agent 輸出獨立呈現，最終彙整由外部處理 |
| VRAM 需求 | Gemma-4-26B 搭配多張圖面時需獨佔 GPU，避免其他應用同時占用 VRAM |
| LaTeX 符號 | Prompt 已禁止 LaTeX 輸出，輸出中若仍出現請回報 |
