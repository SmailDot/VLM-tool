"""
製程管理界面 - Process Library Manager
允許直接在 Streamlit UI 中增減製程、編輯特徵、調整優先級
"""

import streamlit as st
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class ProcessLibraryManager:
    """製程庫管理器"""
    
    def __init__(self, lib_path: str = None):
        """
        初始化管理器
        
        Args:
            lib_path: process_lib.json 檔案路徑
        """
        if lib_path is None:
            # 預設路徑
            base_dir = Path(__file__).parent.parent
            lib_path = base_dir / "app" / "manufacturing" / "process_lib.json"
        
        self.lib_path = Path(lib_path)
        self.data = self._load_library()
    
    def _load_library(self) -> Dict[str, Any]:
        """載入製程庫"""
        try:
            with open(self.lib_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"❌ 無法載入製程庫: {e}")
            return {
                "schema_version": "2.0.0",
                "last_updated": datetime.now().isoformat(),
                "description": "NKUST 鈑金製程知識庫",
                "total_processes": 0,
                "processes": {}
            }
    
    def _save_library(self) -> bool:
        """儲存製程庫"""
        try:
            # 更新時間戳和總數
            self.data['last_updated'] = datetime.now().isoformat()
            self.data['total_processes'] = len(self.data.get('processes', {}))
            
            # 備份舊檔案
            if self.lib_path.exists():
                backup_path = self.lib_path.with_suffix('.json.bak')
                import shutil
                shutil.copy2(self.lib_path, backup_path)
            
            # 寫入新檔案
            with open(self.lib_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            st.error(f"❌ 儲存失敗: {e}")
            return False
    
    def get_all_processes(self) -> Dict[str, Dict[str, Any]]:
        """取得所有製程"""
        return self.data.get('processes', {})
    
    def get_process(self, process_id: str) -> Optional[Dict[str, Any]]:
        """取得單一製程"""
        return self.data.get('processes', {}).get(process_id)
    
    def add_process(self, process_id: str, process_data: Dict[str, Any]) -> bool:
        """
        新增製程
        
        Args:
            process_id: 製程 ID (例如 "Z99")
            process_data: 製程資料
        
        Returns:
            bool: 是否成功
        """
        if process_id in self.data['processes']:
            st.warning(f"⚠️ 製程 {process_id} 已存在！")
            return False
        
        # 確保必要欄位存在
        default_data = {
            "id": process_id,
            "name": "未命名製程",
            "description": "",
            "frequency": "中",
            "triggers": {
                "keywords": [],
                "geometry_features": [],
                "symbols": [],
                "material_conditions": [],
                "customer_specific": []
            },
            "category": "其他",
            "keywords": [],
            "geometry_features": [],
            "symbols": []
        }
        
        # 合併資料
        merged_data = {**default_data, **process_data}
        merged_data['id'] = process_id  # 強制使用傳入的 ID
        
        self.data['processes'][process_id] = merged_data
        return self._save_library()
    
    def update_process(self, process_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新製程
        
        Args:
            process_id: 製程 ID
            updates: 要更新的欄位
        
        Returns:
            bool: 是否成功
        """
        if process_id not in self.data['processes']:
            st.error(f"❌ 製程 {process_id} 不存在！")
            return False
        
        # 更新資料
        self.data['processes'][process_id].update(updates)
        return self._save_library()
    
    def delete_process(self, process_id: str) -> bool:
        """
        刪除製程
        
        Args:
            process_id: 製程 ID
        
        Returns:
            bool: 是否成功
        """
        if process_id not in self.data['processes']:
            st.error(f"❌ 製程 {process_id} 不存在！")
            return False
        
        del self.data['processes'][process_id]
        return self._save_library()
    
    def get_categories(self) -> List[str]:
        """取得所有分類"""
        categories = set()
        for process in self.data.get('processes', {}).values():
            if 'category' in process:
                categories.add(process['category'])
        return sorted(list(categories))
    
    def get_frequency_levels(self) -> List[str]:
        """取得優先級選項"""
        return ["高", "中", "低"]


def render_process_manager():
    """渲染製程管理界面"""
    
    st.markdown("## 🔧 製程庫管理")
    st.markdown("在這裡你可以新增、編輯、刪除製程，以及調整特徵與優先級。")
    
    # 初始化管理器
    if 'process_manager' not in st.session_state:
        st.session_state.process_manager = ProcessLibraryManager()
    
    manager = st.session_state.process_manager
    
    # 頂部統計資訊
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總製程數", len(manager.get_all_processes()))
    with col2:
        st.metric("分類數", len(manager.get_categories()))
    with col3:
        st.metric("版本", manager.data.get('schema_version', 'N/A'))
    
    st.divider()
    
    # 操作 Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 瀏覽製程",
        "➕ 新增製程",
        "✏️ 編輯製程",
        "🗑️ 刪除製程"
    ])
    
    # === Tab 1: 瀏覽製程 ===
    with tab1:
        render_browse_tab(manager)
    
    # === Tab 2: 新增製程 ===
    with tab2:
        render_add_tab(manager)
    
    # === Tab 3: 編輯製程 ===
    with tab3:
        render_edit_tab(manager)
    
    # === Tab 4: 刪除製程 ===
    with tab4:
        render_delete_tab(manager)


def render_browse_tab(manager: ProcessLibraryManager):
    """渲染瀏覽製程 Tab"""
    
    st.markdown("### 📋 所有製程")
    
    # 篩選選項
    col1, col2, col3 = st.columns(3)
    
    with col1:
        categories = ["全部"] + manager.get_categories()
        selected_category = st.selectbox("分類篩選", categories)
    
    with col2:
        frequencies = ["全部"] + manager.get_frequency_levels()
        selected_frequency = st.selectbox("優先級篩選", frequencies)
    
    with col3:
        search_query = st.text_input("搜尋製程", placeholder="輸入製程 ID 或名稱...")
    
    # 取得並篩選製程
    all_processes = manager.get_all_processes()
    filtered_processes = {}
    
    for pid, pdata in all_processes.items():
        # 分類篩選
        if selected_category != "全部" and pdata.get('category') != selected_category:
            continue
        
        # 優先級篩選
        if selected_frequency != "全部" and pdata.get('frequency') != selected_frequency:
            continue
        
        # 搜尋篩選
        if search_query:
            query_lower = search_query.lower()
            if (query_lower not in pid.lower() and 
                query_lower not in pdata.get('name', '').lower()):
                continue
        
        filtered_processes[pid] = pdata
    
    st.markdown(f"**顯示 {len(filtered_processes)} / {len(all_processes)} 個製程**")
    
    # 顯示製程卡片
    if not filtered_processes:
        st.info("📭 沒有符合篩選條件的製程")
    else:
        for pid, pdata in sorted(filtered_processes.items()):
            with st.expander(f"**{pid}** - {pdata.get('name', '未命名')}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**描述**: {pdata.get('description', 'N/A')}")
                    st.markdown(f"**分類**: `{pdata.get('category', 'N/A')}`")
                    
                    # 關鍵字
                    keywords = pdata.get('keywords', []) + pdata.get('triggers', {}).get('keywords', [])
                    if keywords:
                        st.markdown(f"**關鍵字**: {', '.join(keywords)}")
                    
                    # 符號
                    symbols = pdata.get('symbols', []) + pdata.get('triggers', {}).get('symbols', [])
                    if symbols:
                        st.markdown(f"**符號**: {', '.join(symbols)}")
                
                with col2:
                    freq_color = {
                        "高": "🔴",
                        "中": "🟡",
                        "低": "🟢"
                    }
                    freq = pdata.get('frequency', '中')
                    st.markdown(f"**優先級**: {freq_color.get(freq, '⚪')} {freq}")


def render_add_tab(manager: ProcessLibraryManager):
    """渲染新增製程 Tab"""
    
    st.markdown("### ➕ 新增製程")
    
    with st.form("add_process_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_id = st.text_input(
                "製程 ID *",
                placeholder="例如: Z99",
                help="唯一識別碼，建議格式: 字母+數字 (例如 C05, D01)"
            )
            
            new_name = st.text_input(
                "製程名稱 *",
                placeholder="例如: 雷射切割"
            )
            
            new_category = st.selectbox(
                "分類 *",
                ["切割", "折彎成型", "焊接", "表面處理", "組裝", "檢驗", "清潔", "其他"]
            )
        
        with col2:
            new_frequency = st.selectbox(
                "優先級 *",
                ["高", "中", "低"],
                index=1
            )
            
            new_description = st.text_area(
                "描述",
                placeholder="說明此製程的觸發條件與特徵...",
                height=100
            )
        
        st.divider()
        
        # 特徵設定
        st.markdown("#### 特徵設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_keywords = st.text_area(
                "關鍵字 (每行一個)",
                placeholder="例如:\n折彎\n90度\n彎曲",
                height=100
            )
        
        with col2:
            new_symbols = st.text_area(
                "符號 (每行一個)",
                placeholder="例如:\nwelding\nbending\nangle",
                height=100
            )
        
        # 提交按鈕
        submitted = st.form_submit_button("✅ 新增製程", use_container_width=True)
        
        if submitted:
            # 驗證必填欄位
            if not new_id or not new_name:
                st.error("❌ 請填寫製程 ID 和名稱！")
            elif new_id in manager.get_all_processes():
                st.error(f"❌ 製程 ID `{new_id}` 已存在！")
            else:
                # 處理特徵
                keywords_list = [k.strip() for k in new_keywords.split('\n') if k.strip()]
                symbols_list = [s.strip() for s in new_symbols.split('\n') if s.strip()]
                
                # 建立製程資料
                process_data = {
                    "id": new_id,
                    "name": new_name,
                    "description": new_description,
                    "frequency": new_frequency,
                    "category": new_category,
                    "keywords": keywords_list,
                    "symbols": symbols_list,
                    "geometry_features": [],
                    "triggers": {
                        "keywords": keywords_list,
                        "geometry_features": [],
                        "symbols": symbols_list,
                        "material_conditions": [],
                        "customer_specific": []
                    }
                }
                
                # 新增製程
                if manager.add_process(new_id, process_data):
                    st.success(f"✅ 成功新增製程: {new_id} - {new_name}")
                    st.balloons()
                    
                    # 重新載入管理器
                    st.session_state.process_manager = ProcessLibraryManager()
                    st.rerun()


def render_edit_tab(manager: ProcessLibraryManager):
    """渲染編輯製程 Tab"""
    
    st.markdown("### ✏️ 編輯製程")
    
    # 選擇要編輯的製程
    all_processes = manager.get_all_processes()
    
    if not all_processes:
        st.info("📭 目前沒有任何製程可編輯")
        return
    
    process_options = {f"{pid} - {pdata.get('name', '未命名')}": pid 
                       for pid, pdata in sorted(all_processes.items())}
    
    selected_label = st.selectbox(
        "選擇要編輯的製程",
        options=list(process_options.keys())
    )
    
    selected_id = process_options[selected_label]
    process = manager.get_process(selected_id)
    
    if not process:
        st.error("❌ 找不到選擇的製程")
        return
    
    st.divider()
    
    # 編輯表單
    with st.form("edit_process_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            edit_name = st.text_input(
                "製程名稱 *",
                value=process.get('name', '')
            )
            
            edit_category = st.selectbox(
                "分類 *",
                ["切割", "折彎成型", "焊接", "表面處理", "組裝", "檢驗", "清潔", "其他"],
                index=["切割", "折彎成型", "焊接", "表面處理", "組裝", "檢驗", "清潔", "其他"].index(
                    process.get('category', '其他')
                ) if process.get('category', '其他') in ["切割", "折彎成型", "焊接", "表面處理", "組裝", "檢驗", "清潔", "其他"] else 7
            )
        
        with col2:
            edit_frequency = st.selectbox(
                "優先級 *",
                ["高", "中", "低"],
                index=["高", "中", "低"].index(process.get('frequency', '中'))
            )
            
            edit_description = st.text_area(
                "描述",
                value=process.get('description', ''),
                height=100
            )
        
        st.divider()
        
        # 特徵設定
        st.markdown("#### 特徵設定")
        
        col1, col2 = st.columns(2)
        
        # 取得現有特徵
        current_keywords = process.get('keywords', []) + process.get('triggers', {}).get('keywords', [])
        current_symbols = process.get('symbols', []) + process.get('triggers', {}).get('symbols', [])
        
        with col1:
            edit_keywords = st.text_area(
                "關鍵字 (每行一個)",
                value='\n'.join(list(set(current_keywords))),
                height=150
            )
        
        with col2:
            edit_symbols = st.text_area(
                "符號 (每行一個)",
                value='\n'.join(list(set(current_symbols))),
                height=150
            )
        
        # 提交按鈕
        col1, col2 = st.columns([3, 1])
        
        with col1:
            submitted = st.form_submit_button("💾 儲存變更", use_container_width=True)
        
        with col2:
            cancelled = st.form_submit_button("❌ 取消", use_container_width=True)
        
        if submitted:
            # 處理特徵
            keywords_list = [k.strip() for k in edit_keywords.split('\n') if k.strip()]
            symbols_list = [s.strip() for s in edit_symbols.split('\n') if s.strip()]
            
            # 建立更新資料
            updates = {
                "name": edit_name,
                "description": edit_description,
                "frequency": edit_frequency,
                "category": edit_category,
                "keywords": keywords_list,
                "symbols": symbols_list,
                "triggers": {
                    "keywords": keywords_list,
                    "geometry_features": process.get('triggers', {}).get('geometry_features', []),
                    "symbols": symbols_list,
                    "material_conditions": process.get('triggers', {}).get('material_conditions', []),
                    "customer_specific": process.get('triggers', {}).get('customer_specific', [])
                }
            }
            
            # 更新製程
            if manager.update_process(selected_id, updates):
                st.success(f"✅ 成功更新製程: {selected_id}")
                
                # 重新載入管理器
                st.session_state.process_manager = ProcessLibraryManager()
                st.rerun()


def render_delete_tab(manager: ProcessLibraryManager):
    """渲染刪除製程 Tab"""
    
    st.markdown("### 🗑️ 刪除製程")
    st.warning("⚠️ 刪除操作無法復原！系統會自動備份舊檔案為 `.json.bak`")
    
    # 選擇要刪除的製程
    all_processes = manager.get_all_processes()
    
    if not all_processes:
        st.info("📭 目前沒有任何製程可刪除")
        return
    
    process_options = {f"{pid} - {pdata.get('name', '未命名')}": pid 
                       for pid, pdata in sorted(all_processes.items())}
    
    selected_label = st.selectbox(
        "選擇要刪除的製程",
        options=list(process_options.keys())
    )
    
    selected_id = process_options[selected_label]
    process = manager.get_process(selected_id)
    
    if not process:
        st.error("❌ 找不到選擇的製程")
        return
    
    st.divider()
    
    # 顯示製程詳細資訊
    st.markdown("#### 確認刪除以下製程：")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**ID**: `{selected_id}`")
        st.markdown(f"**名稱**: {process.get('name', 'N/A')}")
        st.markdown(f"**分類**: {process.get('category', 'N/A')}")
        st.markdown(f"**描述**: {process.get('description', 'N/A')}")
    
    with col2:
        st.markdown(f"**優先級**: {process.get('frequency', 'N/A')}")
        keywords = process.get('keywords', [])
        st.markdown(f"**關鍵字數**: {len(keywords)}")
        symbols = process.get('symbols', [])
        st.markdown(f"**符號數**: {len(symbols)}")
    
    st.divider()
    
    # 確認刪除
    confirm_text = st.text_input(
        f"輸入製程 ID `{selected_id}` 以確認刪除",
        placeholder=selected_id
    )
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🗑️ 確認刪除", type="primary", use_container_width=True):
            if confirm_text == selected_id:
                if manager.delete_process(selected_id):
                    st.success(f"✅ 成功刪除製程: {selected_id}")
                    
                    # 重新載入管理器
                    st.session_state.process_manager = ProcessLibraryManager()
                    st.rerun()
            else:
                st.error(f"❌ 輸入的 ID 不正確！請輸入 `{selected_id}`")
    
    with col2:
        st.info("💡 提示: 舊檔案會自動備份為 `process_lib.json.bak`")
