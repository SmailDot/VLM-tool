# Engineering Prompts 使用指南

## 概述

`prompts.py` 提供了專為視覺語言模型 (VLM) 設計的工程圖分析提示詞，支援 78 種製程的自動識別。

## 核心功能

### 1. 製程識別 Prompt

最主要的功能，引導 VLM 分析工程圖並識別所需製程。

```python
from app.manufacturing.prompts import EngineeringPrompts

# 標準詳細度 (推薦)
template = EngineeringPrompts.get_process_recognition_prompt(
    include_examples=False,
    detail_level="standard"
)

print("System Prompt:", template.system_prompt)
print("User Prompt:", template.user_prompt)
print("Expected Output:", template.expected_output)
```

### 2. 詳細度等級

支援三種詳細度等級：

- **brief**: 簡潔版本，適合快速測試
- **standard**: 標準版本，平衡詳細度與長度 (推薦)
- **detailed**: 完整版本，包含所有 78 種製程的詳細說明

```python
# 簡潔版 (快速測試)
brief_template = EngineeringPrompts.get_process_recognition_prompt(
    detail_level="brief"
)

# 詳細版 (完整製程參考)
detailed_template = EngineeringPrompts.get_process_recognition_prompt(
    detail_level="detailed"
)
```

### 3. Few-shot 學習

包含 3 個精心設計的範例，提升 VLM 識別準確度：

```python
# 包含範例
template = EngineeringPrompts.get_process_recognition_prompt(
    include_examples=True
)

# 查看範例
for example in template.examples:
    print("描述:", example['description'])
    print("輸入:", example['input'])
    print("輸出:", example['output'])
```

## 與 VLM 整合

### 方式 1：使用 VLMClient

```python
from app.manufacturing.extractors.vlm_client import VLMClient
from app.manufacturing.prompts import EngineeringPrompts

# 初始化客戶端
client = VLMClient(base_url="http://localhost:1234/v1")

# 獲取提示詞
template = EngineeringPrompts.get_process_recognition_prompt()
prompt = template.user_prompt

# 分析工程圖
result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=prompt,
    response_format="json",
    temperature=0.0
)

# 解析結果
if result:
    print("形狀:", result.get("shape_description"))
    print("複雜度:", result.get("overall_complexity"))
    print("檢測特徵:", result.get("detected_features"))
    print("建議製程:", result.get("suggested_process_ids"))
    print("信心度:", result.get("confidence_scores"))
    print("推理依據:", result.get("reasoning"))
```

### 方式 2：便捷函數

```python
from app.manufacturing.prompts import get_default_prompt
from app.manufacturing.extractors.vlm_client import VLMClient

client = VLMClient()

# 使用預設 prompt (standard detail level)
result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=get_default_prompt(),
    response_format="json"
)
```

## 其他提示詞模板

### 特徵檢測

專注於檢測幾何特徵、符號和文字標註：

```python
template = EngineeringPrompts.get_feature_detection_prompt()

result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=template.user_prompt,
    response_format="json"
)

# 輸出格式:
# {
#   "geometry_features": ["bend_lines", "holes"],
#   "symbols": ["welding_symbol"],
#   "text_annotations": ["折彎", "烤漆"],
#   "material": "SPCC",
#   "special_notes": ["去毛邊"]
# }
```

### 形狀分類

識別零件的整體形狀類型：

```python
template = EngineeringPrompts.get_shape_classification_prompt()

result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=template.user_prompt,
    response_format="json"
)

# 輸出格式:
# {
#   "shape_type": "l_shape",
#   "shape_name": "L型",
#   "confidence": 0.95,
#   "description": "單次90°折彎的L型零件",
#   "key_dimensions": {...}
# }
```

## 輸出格式

### 完整製程識別輸出

```json
{
  "shape_description": "L型折彎件，單次90°折彎",
  "overall_complexity": "簡單",
  "detected_features": {
    "geometry": ["bend_lines", "holes"],
    "symbols": ["welding_symbol"],
    "text_annotations": ["折彎", "M3 抽牙", "烤漆黑色"],
    "material_info": "SPCC 1.0T"
  },
  "suggested_process_ids": ["C05", "D01", "E01", "H08"],
  "confidence_scores": {
    "C05": 0.90,
    "D01": 0.95,
    "E01": 0.95,
    "H08": 0.85
  },
  "reasoning": "檢測到 M3 抽牙標註，需要 M3048 切割(C05)。圖面有明確折彎線，需要折彎製程(D01)。所有金屬件預設去毛邊(E01)。標註烤漆黑色，需要前處烤漆(H08)。",
  "process_sequence": ["C05", "D01", "E01", "H08"]
}
```

## 整合到製程管線

### 修改 `pipeline.py`

```python
from .extractors.vlm_client import VLMClient
from .prompts import EngineeringPrompts

class ManufacturingPipeline:
    def __init__(self, use_vlm: bool = False, **kwargs):
        self.use_vlm = use_vlm
        
        if use_vlm:
            self.vlm_client = VLMClient()
            self.vlm_prompt_template = EngineeringPrompts.get_process_recognition_prompt()
    
    def recognize(self, image_path: str, **kwargs):
        features = {}
        
        # VLM 分析 (如果啟用)
        if self.use_vlm and self.vlm_client.is_available():
            vlm_result = self.vlm_client.analyze_image(
                image_path=image_path,
                prompt=self.vlm_prompt_template.user_prompt,
                response_format="json"
            )
            
            if vlm_result:
                features["vlm_analysis"] = {
                    "shape": vlm_result.get("shape_description"),
                    "complexity": vlm_result.get("overall_complexity"),
                    "detected_features": vlm_result.get("detected_features"),
                    "suggested_processes": vlm_result.get("suggested_process_ids"),
                    "confidence_scores": vlm_result.get("confidence_scores"),
                    "reasoning": vlm_result.get("reasoning")
                }
        
        # 傳統特徵提取
        if self.use_ocr:
            features["ocr"] = self.ocr_extractor.extract(...)
        
        if self.use_geometry:
            features["geometry"] = self.geometry_extractor.extract(...)
        
        # 多模態融合決策
        return self._make_decision(features)
```

## 提示詞設計原則

### 1. 結構化輸出

所有 prompt 都明確要求 JSON 格式輸出，確保結果可解析。

### 2. 專業角色設定

系統提示詞設定為「資深鈑金加工工程師」，提升專業領域準確度。

### 3. 步驟引導

使用「步驟 1、步驟 2、步驟 3」的結構，引導 VLM 系統化分析。

### 4. 具體範例

提供清晰的特徵列表和製程代碼參考，減少模糊性。

### 5. Few-shot 學習

包含 3 個典型案例（簡單/中等/複雜），提升識別準確度。

## 效能考量

### Prompt 長度

| 詳細度 | 字元數 | 適用場景 |
|--------|--------|----------|
| brief | ~500 | 快速測試、簡單零件 |
| standard | ~1,600 | 一般使用 (推薦) |
| detailed | ~3,000+ | 複雜零件、完整參考 |

### 推理時間

- **brief**: ~2-3 秒
- **standard**: ~3-5 秒  
- **detailed**: ~5-8 秒

(基於 LM Studio + LLaVA 1.6 7B 本地推理)

### 記憶體使用

- Prompt 本身: < 10 KB
- VLM 推理: 取決於模型大小 (7B: ~8GB, 13B: ~16GB)

## 最佳實踐

### 1. 選擇適當的詳細度

```python
# 簡單零件
brief_template = EngineeringPrompts.get_process_recognition_prompt(
    detail_level="brief"
)

# 複雜零件
detailed_template = EngineeringPrompts.get_process_recognition_prompt(
    detail_level="detailed"
)
```

### 2. 使用 Few-shot 提升準確度

```python
# 啟用範例 (推薦用於生產環境)
template = EngineeringPrompts.get_process_recognition_prompt(
    include_examples=True
)
```

### 3. 設定適當的溫度

```python
# 確定性輸出 (推薦)
result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=prompt,
    temperature=0.0  # 完全確定性
)

# 稍微隨機 (多樣性)
result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=prompt,
    temperature=0.2  # 輕微隨機
)
```

### 4. 錯誤處理

```python
result = client.analyze_image(
    image_path="drawing.jpg",
    prompt=prompt,
    response_format="json"
)

if result:
    # 檢查必要欄位
    if "suggested_process_ids" in result:
        process_ids = result["suggested_process_ids"]
        
        # 驗證製程編號格式
        valid_pattern = r'^[A-Z]\d{2}$'
        valid_ids = [
            pid for pid in process_ids
            if re.match(valid_pattern, pid)
        ]
    else:
        print("警告: VLM 未返回製程建議")
else:
    print("錯誤: VLM 分析失敗")
```

### 5. 批次處理

```python
images = ["drawing1.jpg", "drawing2.jpg", "drawing3.jpg"]
prompt = get_default_prompt()

results = []
for img in images:
    result = client.analyze_image(
        image_path=img,
        prompt=prompt,
        response_format="json"
    )
    results.append(result)
```

## 疑難排解

### 問題 1: JSON 解析失敗

**症狀**: VLM 回傳的不是有效 JSON

**解決方案**:
1. 檢查 `response_format="json"` 參數
2. 降低 `temperature` 至 0.0
3. 使用更明確的 JSON schema 範例
4. 檢查 VLM 模型是否支援 JSON 輸出

### 問題 2: 識別準確度低

**症狀**: 建議的製程不正確

**解決方案**:
1. 使用 `detail_level="detailed"` 提供完整參考
2. 啟用 `include_examples=True`
3. 檢查圖片品質 (解析度、清晰度)
4. 嘗試使用更大的 VLM 模型 (13B vs 7B)

### 問題 3: 回應時間過長

**症狀**: VLM 推理超過 10 秒

**解決方案**:
1. 使用 `detail_level="brief"` 減少 prompt 長度
2. 禁用 `include_examples` (False)
3. 考慮使用更小的模型
4. 使用 GPU 加速

## 版本資訊

- **版本**: 1.0.0
- **日期**: 2026-02-06
- **作者**: 國立高雄科技大學視覺實驗室
- **相容性**: 
  - OpenAI GPT-4 Vision
  - LM Studio (LLaVA, Qwen-VL, Phi-3-Vision)
  - 任何 OpenAI 相容 API

## 授權

本專案為 NKUST 製程辨識系統的一部分。
