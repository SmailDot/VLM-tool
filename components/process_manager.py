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
    
    lib_path: Path
    data: Dict[str, Any]
    
    def __init__(self, lib_path: Optional[str] = None):
        """
        初始化管理器
        
        Args:
            lib_path: process_lib.json 檔案路徑
        """
        if lib_path is None:
            # 預設路徑
            base_dir = Path(__file__).parent.parent
            self.lib_path = base_dir / "app" / "manufacturing" / "process_lib.json"
        else:
            self.lib_path = Path(lib_path)
        
        self.data = self._load_library()
    
    def _load_library(self) -> Dict[str, Any]:
        """載入製程庫"""
        try:
            with open(self.lib_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"無法載入製程庫: {e}")
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
            st.error(f"儲存失敗: {e}")
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
            st.warning(f"製程 {process_id} 已存在")
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
            st.error(f"製程 {process_id} 不存在")
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
            st.error(f"製程 {process_id} 不存在")
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
    
    st.markdown("## 製程庫管理")
    
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
    
    # 簡化為兩個 Tabs
    tab1, tab2 = st.tabs(["管理製程", "新增製程"])
    
    # Tab 1: 管理製程（合併瀏覽、編輯、刪除）
    with tab1:
        render_manage_tab(manager)
    
    # Tab 2: 新增製程
    with tab2:
        render_add_tab(manager)


def render_manage_tab(manager: ProcessLibraryManager):
    """渲染管理製程 Tab（合併瀏覽、編輯、刪除）"""
    
    st.markdown("### 管理製程")
    
    # 篩選選項
    col1, col2, col3 = st.columns(3)
    
    with col1:
        categories = ["全部"] + manager.get_categories()
        selected_category = st.selectbox("分類", categories)
    
    with col2:
        frequencies = ["全部"] + manager.get_frequency_levels()
        selected_frequency = st.selectbox("優先級", frequencies)
    
    with col3:
        search_query = st.text_input("搜尋", placeholder="ID 或名稱")
    
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
    
    st.caption(f"顯示 {len(filtered_processes)} / {len(all_processes)} 個製程")
    
    st.divider()
    
    # 顯示製程表格（直接可編輯）
    if not filtered_processes:
        st.info("沒有符合條件的製程")
    else:
        for pid, pdata in sorted(filtered_processes.items()):
            with st.expander(f"{pid} - {pdata.get('name', '未命名')}", expanded=False):
                # 使用 form 讓用戶可以編輯
                with st.form(key=f"edit_form_{pid}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        edit_name = st.text_input("名稱", value=pdata.get('name', ''), key=f"name_{pid}")
                        edit_description = st.text_area("描述", value=pdata.get('description', ''), height=80, key=f"desc_{pid}")
                    
                    with col2:
                        # 安全取得 category index
                        categories = ["切割", "折彎成型", "焊接", "表面處理", "組裝", "檢驗", "清潔", "其他"]
                        current_cat = pdata.get('category', '其他')
                        cat_index = categories.index(current_cat) if current_cat in categories else 7
                        
                        edit_category = st.selectbox(
                            "分類",
                            categories,
                            index=cat_index,
                            key=f"cat_{pid}"
                        )
                        
                        # 安全取得 frequency index
                        frequencies = ["高", "中", "低"]
                        current_freq = pdata.get('frequency', '中')
                        freq_index = frequencies.index(current_freq) if current_freq in frequencies else 1
                        
                        edit_frequency = st.selectbox(
                            "優先級",
                            frequencies,
                            index=freq_index,
                            key=f"freq_{pid}"
                        )
                        
                        edit_frequency = st.selectbox(
                            "優先級",
                            ["高", "中", "低"],
                            index=["高", "中", "低"].index(pdata.get('frequency', '中')),
                            key=f"freq_{pid}"
                        )
                    
                    st.divider()
                    
                    # 特徵設定
                    col1, col2 = st.columns(2)
                    
                    current_keywords = pdata.get('keywords', []) + pdata.get('triggers', {}).get('keywords', [])
                    current_symbols = pdata.get('symbols', []) + pdata.get('triggers', {}).get('symbols', [])
                    
                    with col1:
                        edit_keywords = st.text_area(
                            "關鍵字（每行一個）",
                            value='\n'.join(list(set(current_keywords))),
                            height=120,
                            key=f"kw_{pid}"
                        )
                    
                    with col2:
                        edit_symbols = st.text_area(
                            "符號（每行一個）",
                            value='\n'.join(list(set(current_symbols))),
                            height=120,
                            key=f"sym_{pid}"
                        )
                    
                    # 操作按鈕
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        save_btn = st.form_submit_button("儲存", use_container_width=True)
                    
                    with col2:
                        delete_btn = st.form_submit_button("刪除", use_container_width=True, type="secondary")
                    
                    with col3:
                        st.form_submit_button("取消", use_container_width=True)
                    
                    # 處理儲存
                    if save_btn:
                        keywords_list = [k.strip() for k in edit_keywords.split('\n') if k.strip()]
                        symbols_list = [s.strip() for s in edit_symbols.split('\n') if s.strip()]
                        
                        updates = {
                            "name": edit_name,
                            "description": edit_description,
                            "frequency": edit_frequency,
                            "category": edit_category,
                            "keywords": keywords_list,
                            "symbols": symbols_list,
                            "triggers": {
                                "keywords": keywords_list,
                                "geometry_features": pdata.get('triggers', {}).get('geometry_features', []),
                                "symbols": symbols_list,
                                "material_conditions": pdata.get('triggers', {}).get('material_conditions', []),
                                "customer_specific": pdata.get('triggers', {}).get('customer_specific', [])
                            }
                        }
                        
                        if manager.update_process(pid, updates):
                            st.success(f"已更新製程 {pid}")
                            st.session_state.process_manager = ProcessLibraryManager()
                            st.rerun()
                    
                    # 處理刪除
                    if delete_btn:
                        # 使用 session state 記錄要刪除的 ID
                        if 'confirm_delete' not in st.session_state:
                            st.session_state.confirm_delete = None
                        
                        if st.session_state.confirm_delete == pid:
                            # 執行刪除
                            if manager.delete_process(pid):
                                st.success(f"已刪除製程 {pid}")
                                st.session_state.confirm_delete = None
                                st.session_state.process_manager = ProcessLibraryManager()
                                st.rerun()
                        else:
                            # 要求確認
                            st.session_state.confirm_delete = pid
                            st.warning(f"再次點擊「刪除」確認刪除 {pid}")
                            st.rerun()


def render_add_tab(manager: ProcessLibraryManager):
    """渲染新增製程 Tab"""
    
    st.markdown("### 新增製程")
    
    with st.form("add_process_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_id = st.text_input(
                "製程 ID",
                placeholder="例如: Z99",
                help="建議格式: 字母+數字"
            )
            
            new_name = st.text_input(
                "製程名稱",
                placeholder="例如: 雷射切割"
            )
            
            new_category = st.selectbox(
                "分類",
                ["切割", "折彎成型", "焊接", "表面處理", "組裝", "檢驗", "清潔", "其他"]
            )
        
        with col2:
            new_frequency = st.selectbox(
                "優先級",
                ["高", "中", "低"],
                index=1
            )
            
            new_description = st.text_area(
                "描述",
                placeholder="說明此製程的觸發條件",
                height=100
            )
        
        st.divider()
        
        # 特徵設定
        col1, col2 = st.columns(2)
        
        with col1:
            new_keywords = st.text_area(
                "關鍵字（每行一個）",
                placeholder="折彎\n90度\n彎曲",
                height=100
            )
        
        with col2:
            new_symbols = st.text_area(
                "符號（每行一個）",
                placeholder="welding\nbending\nangle",
                height=100
            )
        
        # 提交按鈕
        submitted = st.form_submit_button("新增", use_container_width=True)
        
        if submitted:
            # 驗證必填欄位
            if not new_id or not new_name:
                st.error("請填寫製程 ID 和名稱")
            elif new_id in manager.get_all_processes():
                st.error(f"製程 ID {new_id} 已存在")
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
                    st.success(f"已新增製程: {new_id} - {new_name}")
                    st.session_state.process_manager = ProcessLibraryManager()
                    st.rerun()
