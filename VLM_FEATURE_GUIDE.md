# VLM 特徵提取器使用說明

## 概述

`vlm_client.py` 提供了與視覺語言模型 (Vision-Language Model, VLM) 互動的介面，用於分析工程圖紙並提取製程相關資訊。

## 功能特性

- ✅ **OpenAI 相容 API**：支援 LM Studio 本地伺服器和 OpenAI API
- ✅ **自動圖片編碼**：支援檔案路徑和 NumPy 陣列（OpenCV 圖片）
- ✅ **結構化輸出**：自動解析 JSON 格式回應
- ✅ **完善錯誤處理**：連線失敗、檔案不存在等情況自動處理
- ✅ **鈑金工程領域**：專門針對鈑金加工的系統提示詞

## 安裝依賴

### 1. 安裝 Python 套件

```bash
pip install openai>=1.0.0
```

或從 `requirements.txt` 安裝所有依賴：

```bash
pip install -r requirements.txt
```

### 2. 設定 LM Studio（本地推理）

**推薦配置**：使用 LM Studio 在本地執行視覺語言模型

1. **下載 LM Studio**：https://lmstudio.ai/
2. **下載視覺模型**：
   - 推薦：`LLaVA 1.6` (7B 或 13B)
   - 其他選項：`Qwen-VL`, `Phi-3-Vision`
3. **啟動本地伺服器**：
   - 開啟 LM Studio
   - 選擇 "Local Server" 分頁
   - 點擊 "Start Server"（預設端口：1234）
4. **載入模型**：
   - 在 LM Studio 中選擇已下載的視覺模型
   - 點擊 "Load Model"

### 3. 驗證安裝

執行測試腳本：

```bash
python test_vlm.py
```

測試項目：
- ✅ 客戶端初始化
- ✅ 服務可用性檢查
- ✅ 圖片編碼（檔案路徑和 NumPy 陣列）
- ✅ 基本圖片分析
- ✅ 錯誤處理

## 使用方式

### 基本用法（快速分析）

```python
from app.manufacturing.extractors.vlm_client import analyze_engineering_drawing

# 分析單張工程圖
result = analyze_engineering_drawing(
    image_path="drawing.jpg",
    question="請識別此工程圖所需的製程類型"
)

if result:
    print("製程列表:", result.get("processes", []))
    print("信心度:", result.get("confidence", 0))
    print("判斷依據:", result.get("reasoning", ""))
else:
    print("分析失敗（VLM 服務可能未啟動）")
```

### 進階用法（客戶端實例）

```python
from app.manufacturing.extractors.vlm_client import VLMClient
import cv2

# 初始化客戶端
client = VLMClient(
    base_url="http://localhost:1234/v1",  # LM Studio 預設位址
    model="local-model",                  # 模型名稱
    timeout=60,                           # 請求超時（秒）
    max_retries=2                         # 最大重試次數
)

# 檢查服務可用性
if not client.is_available():
    print("VLM 服務未啟動")
    exit(1)

# 方式 1：從檔案路徑分析
result = client.analyze_image(
    image_path="drawing.jpg",
    prompt="識別所有製程類型並以 JSON 格式輸出",
    response_format="json",
    temperature=0.0,        # 確定性輸出（不隨機）
    max_tokens=2000         # 最大回應長度
)

# 方式 2：從 OpenCV 圖片分析
image = cv2.imread("drawing.jpg")
result = client.analyze_image(
    image_path=image,  # 可以直接傳入 np.ndarray
    prompt="這張圖需要哪些製程？",
    response_format="json"
)

print(result)
```

### 批次處理

```python
from app.manufacturing.extractors.vlm_client import VLMClient

client = VLMClient()

# 分析多張圖片
images = ["drawing1.jpg", "drawing2.jpg", "drawing3.jpg"]
results = client.batch_analyze(
    images=images,
    prompt="識別製程類型",
    response_format="json"
)

for i, result in enumerate(results):
    if result:
        print(f"圖片 {i+1}: {result.get('processes', [])}")
    else:
        print(f"圖片 {i+1}: 分析失敗")
```

## 提示詞範例

### 製程識別

```python
prompt = """
請分析這張工程圖，識別所有可能需要的製程類型。

以 JSON 格式回答：
{
    "processes": ["製程1", "製程2", "..."],
    "confidence": 0.85,
    "reasoning": "判斷依據說明"
}

可能的製程包括但不限於：
- 切割類：雷射切割、剪板機、水刀切割
- 折彎類：折彎、滾圓、滾弧
- 焊接類：點焊、氬焊、電焊
- 表面處理：噴砂、烤漆、電鍍
- 組裝類：螺絲、鉚接、攻牙
"""
```

### 幾何特徵檢測

```python
prompt = """
請分析此工程圖的幾何特徵，並回答：

1. 是否有折彎線？（有/無，數量）
2. 是否有圓孔或圓形特徵？（有/無，數量）
3. 是否有複雜曲線或弧形？（有/無）
4. 整體形狀描述

以 JSON 格式輸出：
{
    "bend_lines": {"exists": true, "count": 3},
    "holes": {"exists": true, "count": 8},
    "curves": {"exists": false},
    "shape_description": "矩形鈑金件，帶多個螺絲孔"
}
"""
```

### 文字與標註提取

```python
prompt = """
請讀取此工程圖中的所有文字和標註，包括：
- 尺寸標註
- 材質說明
- 製程要求
- 公差標示

以 JSON 格式輸出：
{
    "dimensions": ["100mm", "50mm", "..."],
    "material": "SPCC",
    "process_notes": ["折彎半徑 R=2mm", "..."],
    "tolerances": ["±0.1mm", "..."]
}
"""
```

## 整合到製程辨識管線

### 修改 `pipeline.py`

```python
from .extractors.vlm_client import VLMClient

class ManufacturingPipeline:
    def __init__(self, use_vlm: bool = False, **kwargs):
        self.use_vlm = use_vlm
        
        if use_vlm:
            self.vlm_client = VLMClient()
            if not self.vlm_client.is_available():
                print("Warning: VLM service unavailable, disabling VLM features")
                self.use_vlm = False
    
    def recognize(self, image_path: str, **kwargs):
        features = {}
        
        # 現有的特徵提取...
        if self.use_ocr:
            features["ocr"] = self.ocr_extractor.extract(...)
        
        # 新增：VLM 特徵提取
        if self.use_vlm:
            vlm_result = self.vlm_client.analyze_image(
                image_path=image_path,
                prompt="識別工程圖所需製程",
                response_format="json"
            )
            
            if vlm_result:
                features["vlm_processes"] = vlm_result.get("processes", [])
                features["vlm_confidence"] = vlm_result.get("confidence", 0)
        
        # 決策引擎融合所有特徵...
        return self._make_decision(features)
```

## 疑難排解

### ❌ 問題 1：連線失敗

**症狀**：
```
Error during VLM API request: Connection refused
```

**解決方案**：
1. 確認 LM Studio 正在執行
2. 檢查伺服器位址：http://localhost:1234
3. 測試連線：
   ```bash
   curl http://localhost:1234/v1/models
   ```

### ❌ 問題 2：模型未載入

**症狀**：
```
VLM service unavailable
```

**解決方案**：
1. 開啟 LM Studio
2. 選擇並載入一個視覺語言模型
3. 等待模型載入完成（可能需要幾秒）
4. 重新執行程式

### ❌ 問題 3：回應不是 JSON 格式

**症狀**：
```
Warning: Failed to parse response as JSON
```

**解決方案**：
1. 在提示詞中明確要求 JSON 格式
2. 降低 `temperature` 參數（設為 0.0）
3. 使用更明確的 JSON 範例在提示詞中
4. 查看 `raw_response` 欄位了解實際回應

### ❌ 問題 4：OpenAI 套件未安裝

**症狀**：
```
ImportError: OpenAI SDK not installed
```

**解決方案**：
```bash
pip install openai>=1.0.0
```

## API 參數說明

### `VLMClient.__init__()`

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `base_url` | str | `"http://localhost:1234/v1"` | API 端點位址 |
| `api_key` | str | `"not-needed"` | API 金鑰（LM Studio 不需要） |
| `model` | str | `"local-model"` | 模型名稱 |
| `timeout` | int | `60` | 請求超時（秒） |
| `max_retries` | int | `2` | 最大重試次數 |

### `VLMClient.analyze_image()`

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `image_path` | str/Path/np.ndarray | - | 圖片來源 |
| `prompt` | str | - | 分析提示詞 |
| `response_format` | str | `"json"` | 回應格式（`"json"` 或 `"text"`) |
| `temperature` | float | `0.0` | 採樣溫度（0=確定性，1=創造性） |
| `max_tokens` | int | `2000` | 最大回應長度 |

## 進階配置

### 使用 OpenAI API（雲端推理）

```python
client = VLMClient(
    base_url="https://api.openai.com/v1",
    api_key="your-openai-api-key",
    model="gpt-4o"  # 或 "gpt-4-vision-preview"
)
```

### 自訂系統提示詞

```python
client = VLMClient()
# 修改系統提示詞
client.SYSTEM_PROMPT = "你是專業的 CAD 圖紙分析專家..."
```

## 效能考量

- **推理速度**：本地 7B 模型約 2-5 秒/張（視硬體而定）
- **記憶體需求**：7B 模型約需 8GB RAM，13B 模型約需 16GB
- **批次處理**：建議分批處理，避免超時
- **快取機制**：考慮快取常見問題的回應

## 最佳實踐

1. **提示詞工程**：
   - 明確指定輸出格式（JSON schema）
   - 提供具體範例
   - 使用溫度 0.0 確保一致性

2. **錯誤處理**：
   - 始終檢查 `is_available()` 再使用
   - 處理 `None` 回應
   - 記錄失敗案例供後續改進

3. **效能優化**：
   - 預先檢查服務可用性
   - 批次處理降低通訊開銷
   - 考慮非同步處理大量圖片

## 授權與支援

- **專案**：NKUST 製程辨識系統
- **版本**：1.0.0
- **作者**：國立高雄科技大學視覺實驗室
- **日期**：2026-02-06
