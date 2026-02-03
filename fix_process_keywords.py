"""
自動從 process_lib.json 的 description 中提取關鍵字並填充到 keywords 欄位
"""

import json
import re
from pathlib import Path
from datetime import datetime

def extract_keywords_from_description(description: str) -> list:
    """
    從 description 中提取關鍵字
    
    規則：
    1. 提取「」內的詞語
    2. 提取 M3/M4/M5 這種格式
    3. 移除空白和重複
    """
    keywords = []
    
    # 提取「」內的內容
    quoted_pattern = r'「([^」]+)」'
    quoted_matches = re.findall(quoted_pattern, description)
    keywords.extend(quoted_matches)
    
    # 提取 M3/M4/M5 這種格式（螺絲規格）
    screw_pattern = r'M\d+(?:/M\d+)*'
    screw_matches = re.findall(screw_pattern, description)
    keywords.extend(screw_matches)
    
    # 清理：移除空白、去重
    keywords = [k.strip() for k in keywords if k.strip()]
    keywords = list(set(keywords))  # 去重
    
    return keywords


def fix_process_library():
    """修復 process_lib.json 中的空白 keywords"""
    
    lib_path = Path(__file__).parent / "app" / "manufacturing" / "process_lib.json"
    
    # 讀取 JSON
    print(f"讀取: {lib_path}")
    with open(lib_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 備份
    backup_path = lib_path.with_suffix('.json.bak')
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已備份至: {backup_path}")
    
    # 處理每個製程
    updated_count = 0
    for pid, pdata in data['processes'].items():
        description = pdata.get('description', '')
        current_keywords = pdata.get('keywords', [])
        current_triggers_kw = pdata.get('triggers', {}).get('keywords', [])
        
        # 如果 keywords 和 triggers.keywords 都是空的，嘗試從 description 提取
        if not current_keywords and not current_triggers_kw and description:
            extracted = extract_keywords_from_description(description)
            
            if extracted:
                pdata['keywords'] = extracted
                pdata['triggers']['keywords'] = extracted
                updated_count += 1
                print(f"[{pid}] {pdata['name']}: 新增 {len(extracted)} 個關鍵字 - {extracted}")
    
    # 更新時間戳記
    data['last_updated'] = datetime.now().isoformat()
    
    # 儲存
    with open(lib_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成！更新了 {updated_count} 個製程")
    print(f"總共 {len(data['processes'])} 個製程")
    
    # 顯示統計
    total_processes = len(data['processes'])
    processes_with_keywords = sum(1 for p in data['processes'].values() if p.get('keywords'))
    processes_without_keywords = total_processes - processes_with_keywords
    
    print(f"\n📊 統計:")
    print(f"  有關鍵字: {processes_with_keywords}")
    print(f"  無關鍵字: {processes_without_keywords}")


if __name__ == "__main__":
    fix_process_library()
