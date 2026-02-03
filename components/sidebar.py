
import streamlit as st

def render_sidebar(engine):
    """
    渲染側邊欄 (System Info & LLM Settings)
    """
    with st.sidebar:
        st.header("System Info")
        
        # Access safely in case engine is still initializing or lib load failed
        try:
            schema_ver = engine.lib_manager.data.get('schema_version', 'N/A')
            libs = engine.lib_manager.data.get('libraries', {})
            official_count = len(libs.get('official', {}))
            contrib_count = len(libs.get('contributed', {}))
        except Exception:
            schema_ver, official_count, contrib_count = "Error", 0, 0
        
        st.caption(f"Ver: {schema_ver}")
        st.caption(f"Official: {official_count}")
        st.caption(f"Contrib: {contrib_count}")
        
        st.divider()
        
        st.header("LLM Settings")
        st.caption("Set up LLM API for intelligence")
        
        # Ensure session state exists
        if 'use_mock_llm' not in st.session_state:
            st.session_state.use_mock_llm = True
        if 'llm_api_key' not in st.session_state:
            st.session_state.llm_api_key = ""
        if 'llm_base_url' not in st.session_state:
            st.session_state.llm_base_url = "https://api.openai.com/v1"
        
        use_mock = st.toggle("使用 Mock 模式 (測試用)", value=st.session_state.use_mock_llm)
        st.session_state.use_mock_llm = use_mock
        
        if not use_mock:
            # 1. 定義預設設定 (Presets) - Updated 2025.01 (Gemini 2.5 Era)
            PROVIDERS = {
                "Google Gemini": {
                    "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "models": [
                        "gemini-2.0-flash",
                        "gemini-2.0-flash-exp", 
                        "gemini-2.5-flash",
                        "gemini-exp-1206"
                    ],
                    "help": "Gemini 1.5 已移除。請使用 2.0 或 2.5 系列。"
                },
                "Groq": {
                    "url": "https://api.groq.com/openai/v1",
                    "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
                    "help": "速度極快 (LPU)。推薦 Llama 3.3 或 3.1。"
                },
                "OpenAI (Official)": {
                    "url": "https://api.openai.com/v1",
                    "models": ["gpt-4o", "gpt-4o-mini"],
                    "help": "需綁定信用卡。推薦 gpt-4o-mini (高性價比)。"
                },
                "DeepSeek": {
                    "url": "https://api.deepseek.com",
                    "models": ["deepseek-chat", "deepseek-reasoner"],
                    "help": "chat (V3) 通用，reasoner (R1) 適合複雜推理。"
                },
                "Local (LM Studio / Ollama)": {
                    "url": "http://localhost:1234/v1",
                    "models": ["local-model"],
                    "help": "本地執行，隱私最安全。需自行架設 Server。"
                },
                "Custom (自訂)": {
                    "url": "",
                    "models": [],
                    "help": "手動輸入所有設定。"
                }
            }

            # 2. 選擇服務商 (Provider)
            provider = st.selectbox(
                "選擇服務商 (Provider)", 
                list(PROVIDERS.keys()),
                index=0,
                help="選擇後會自動帶入對應的 URL 與模型建議"
            )
            
            selected_preset = PROVIDERS[provider]
            
            # 3. Base URL (Auto-filled but editable)
            # 使用 key 來強制更新預設值，當 provider 改變時
            base_url = st.text_input(
                "Base URL", 
                value=selected_preset["url"],
                help=selected_preset["help"],
                key=f"url_{provider}" # Trick to auto-update value when provider changes
            )
            
            # 4. API Key
            api_key = st.text_input("API Key", type="password", value=st.session_state.llm_api_key)
            
            # 5. Model Selection
            # 合併預設模型與「手動輸入」選項
            model_options = selected_preset["models"] + ["Custom Input..."]
            
            selected_model_option = st.selectbox(
                "Model Name",
                model_options,
                help="Select a model or choose Custom Input"
            )
            
            if selected_model_option == "Custom Input...":
                final_model_name = st.text_input("Enter Model Name", placeholder="e.g. gpt-4-32k")
            else:
                final_model_name = selected_model_option
            
            # Connection Test Button
            if st.button("Test Connection", use_container_width=True):
                with st.spinner("Testing connection..."):
                    is_ok, msg = engine.prompt_master.test_connection(api_key, base_url, final_model_name)
                    if is_ok:
                        st.toast("Connection Successful")
                        st.success(f"Connection Verified\n\n- URL: OK\n- Key: OK\n- Model: {final_model_name}")
                    else:
                        st.toast("Connection Failed")
                        st.error(f"Connection Failed\n\n{msg}")

            # Save to Session State
            if api_key and final_model_name:
                st.session_state.llm_api_key = api_key
                st.session_state.llm_base_url = base_url
                st.session_state.llm_model_name = final_model_name
                
                # Show status
                st.caption(f"Provider: {provider}")
            else:
                st.warning("Please enter API Key and Model Name")
        
        st.divider()
        st.caption("NKUST Vision Lab")
