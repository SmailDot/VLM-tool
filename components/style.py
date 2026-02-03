
import streamlit as st

def apply_custom_style():
    """
    注入客製化 CSS 樣式 (Cyberpunk/Tech Theme)
    科技感主題：深色背景、霓虹光效、玻璃拟态
    """
    # 注入 CSS
    st.markdown("""
        <style>
        /* Import Fonts: Inter & JetBrains Mono */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        /* Global Reset & Tech Theme */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #12121a 50%, #0d0d12 100%);
            color: #ffffff !important;
        }

        /* Force all text to be white/highly visible */
        p, span, div, label, h1, h2, h3, h4, h5, h6, li, a, button {
            color: #ffffff !important;
        }

        /* Special styling for titles with neon glow */
        h1, h2, h3 {
            color: #00ffff !important;
            text-shadow: 0 0 20px rgba(0, 255, 255, 0.5), 0 0 40px rgba(0, 200, 255, 0.3) !important;
        }

        /* Subtitles and descriptions */
        .stMarkdown p, .stMarkdown span {
            color: #ffffff !important;
            line-height: 1.6;
        }

        /* Ensure all Streamlit text elements are visible */
        [data-testid="stText"] {
            color: #ffffff !important;
        }

        /* Sidebar text visibility */
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
            color: #ffffff !important;
        }

        /* All expander content */
        .streamlit-expanderContent {
            color: #ffffff !important;
        }
        .streamlit-expanderContent p, .streamlit-expanderContent span {
            color: #ffffff !important;
        }

        /* Ensure ALL Streamlit text components are visible */
        .element-container {
            color: #ffffff !important;
        }

        /* Override all possible text containers */
        .stMarkdown, .stText, .stCode, .stJson, .stDataFrame {
            color: #ffffff !important;
        }

        /* Ensure widget labels are visible */
        .stWidgetLabel {
            color: #ffffff !important;
            font-weight: 500 !important;
        }

        /* All paragraphs and text within widgets */
        .stMarkdown p, .stMarkdown div {
            color: #ffffff !important;
        }

        /* Sidebar specific - ensure all text is white */
        [data-testid="stSidebar"] .element-container {
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] p {
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] .stMarkdown {
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] .stCaption {
            color: #b0c4de !important;
        }

        /* Specific fix for st.caption - make it more visible */
        .stCaption {
            color: #a0c4e8 !important;
            font-size: 0.9rem !important;
            font-weight: 500 !important;
        }

        /* Specific fix for st.header */
        .stHeader, [data-testid="stHeader"] {
            color: #00ffff !important;
        }

        /* Fix for all st.subheader */
        [data-testid="stSubheader"] {
            color: #00ccff !important;
            font-weight: 600 !important;
        }

        /* Tech Grid Background Pattern */
        .stApp {
            background: 
                linear-gradient(135deg, rgba(10, 10, 15, 0.97) 0%, rgba(18, 18, 26, 0.95) 50%, rgba(13, 13, 18, 0.97) 100%),
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 50px,
                    rgba(0, 255, 255, 0.03) 50px,
                    rgba(0, 255, 255, 0.03) 51px
                ),
                repeating-linear-gradient(
                    90deg,
                    transparent,
                    transparent 50px,
                    rgba(0, 255, 255, 0.03) 50px,
                    rgba(0, 255, 255, 0.03) 51px
                );
            background-attachment: fixed;
        }

        /* Main Container */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 95%;
        }

        /* ================= Hero Header - Tech Style ================= */
        .hero-header {
            background: 
                linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.85) 100%),
                linear-gradient(90deg, rgba(0, 255, 255, 0.1) 0%, transparent 50%, rgba(0, 200, 255, 0.1) 100%);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 
                0 0 40px rgba(0, 255, 255, 0.15),
                0 0 80px rgba(0, 200, 255, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        /* Animated Glow Border */
        .hero-header::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, #00ffff, #0080ff, #00ffff, #0080ff);
            border-radius: 18px;
            z-index: -1;
            opacity: 0.5;
            animation: borderGlow 3s linear infinite;
        }
        
        @keyframes borderGlow {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.7; }
        }
        
        .hero-title {
            font-size: 2.2rem;
            font-weight: 700;
            margin: 0;
            background: linear-gradient(90deg, #00ffff 0%, #00ccff 50%, #0080ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-family: 'JetBrains Mono', monospace;
            text-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
            letter-spacing: -0.02em;
        }
        .hero-subtitle {
            font-size: 1rem;
            color: #94a3b8;
            margin-top: 0.75rem;
            font-weight: 500;
            letter-spacing: 0.05em;
        }

        /* ================= Glassmorphism Cards ================= */
        .stExpander, div[data-testid="stExpander"] {
            background: rgba(30, 41, 59, 0.4) !important;
            backdrop-filter: blur(12px);
            border-radius: 12px;
            border: 1px solid rgba(0, 255, 255, 0.15);
            box-shadow: 
                0 4px 24px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }
        .stExpander:hover {
            border-color: rgba(0, 255, 255, 0.3);
            box-shadow: 
                0 8px 32px rgba(0, 255, 255, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }
        
        .streamlit-expanderHeader {
            font-weight: 600;
            color: #00ccff !important;
            background: rgba(30, 41, 59, 0.6) !important;
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
            padding: 1rem 1.25rem;
        }
        
        /* Fix for expander header text - always visible on dark background */
        .streamlit-expanderHeader p,
        .streamlit-expanderHeader span,
        .streamlit-expanderHeader div,
        [data-testid="stExpanderHeader"] p,
        [data-testid="stExpanderHeader"] span,
        [data-testid="stExpanderHeader"] div {
            color: #00ccff !important;
            font-weight: 600 !important;
            background: transparent !important;
        }
        
        /* Expander when expanded - keep header visible */
        [data-testid="stExpander"][aria-expanded="true"] [data-testid="stExpanderHeader"],
        .streamlit-expanderHeader[aria-expanded="true"] {
            background: rgba(30, 41, 59, 0.8) !important;
            color: #00ccff !important;
        }
        
        /* ALL text inside expander headers - bright cyan */
        [data-testid="stExpanderHeader"] *,
        .streamlit-expanderHeader * {
            color: #00ccff !important;
            text-shadow: 0 0 10px rgba(0, 200, 255, 0.5) !important;
        }

        /* ================= Tech Buttons ================= */
        div.stButton > button {
            border-radius: 8px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.85rem;
            border: none;
            position: relative;
            overflow: hidden;
        }
        
        div.stButton > button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        div.stButton > button:hover::before {
            left: 100%;
        }
        
        div.stButton > button:active {
            transform: scale(0.96);
        }
        
        /* Primary Button - Cyberpunk Blue */
        div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0066cc 0%, #0099ff 50%, #00ccff 100%);
            box-shadow: 
                0 4px 15px rgba(0, 153, 255, 0.4),
                0 0 30px rgba(0, 200, 255, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.2);
            color: white;
        }
        div.stButton > button[kind="primary"]:hover {
            box-shadow: 
                0 6px 20px rgba(0, 153, 255, 0.6),
                0 0 40px rgba(0, 200, 255, 0.3);
            transform: translateY(-2px);
        }
        
        /* Secondary Button - Dark Tech */
        div.stButton > button:not([kind="primary"]) {
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(0, 255, 255, 0.3);
            color: #00ccff;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        div.stButton > button:not([kind="primary"]):hover {
            background: rgba(0, 255, 255, 0.1);
            border-color: rgba(0, 255, 255, 0.5);
            box-shadow: 0 4px 12px rgba(0, 255, 255, 0.2);
        }

        /* ================= Input Fields - Tech Style ================= */
        .stTextInput input, .stNumberInput input, .stTextArea textarea {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 8px;
            color: #ffffff !important;
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
            text-shadow: 0 0 2px rgba(0, 0, 0, 0.8);
        }
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
            border-color: rgba(0, 255, 255, 0.8);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
            background: rgba(15, 23, 42, 0.95);
            outline: none;
        }
        .stTextInput input::placeholder, .stTextArea textarea::placeholder {
            color: #94a3b8 !important;
            opacity: 1;
        }
        
        /* Labels */
        label, .stTextInput label, .stNumberInput label {
            color: #ffffff !important;
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            text-shadow: 0 0 10px rgba(0, 200, 255, 0.5);
        }

        /* ================= Slider - Tech Blue ================= */
        div[data-testid="stSlider"] div[role="slider"] {
            background: linear-gradient(90deg, #00ffff, #0080ff);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        }
        div[data-testid="stSlider"] > div > div {
            background: rgba(0, 255, 255, 0.2);
        }

        /* ================= Sidebar - Dark Tech ================= */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(10, 10, 15, 0.98) 100%);
            border-right: 1px solid rgba(0, 255, 255, 0.2);
            box-shadow: 4px 0 24px rgba(0, 0, 0, 0.4);
        }
        [data-testid="stSidebar"] > div {
            padding: 1.5rem;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #00ccff !important;
            font-family: 'JetBrains Mono', monospace;
            border-bottom: 1px solid rgba(0, 255, 255, 0.2);
            padding-bottom: 0.5rem;
        }

        /* ================= Tabs - Neon Style ================= */
        .stTabs [data-baseweb="tab-list"] {
            background: rgba(30, 41, 59, 0.4);
            border-radius: 12px;
            padding: 0.5rem;
            border: 1px solid rgba(0, 255, 255, 0.1);
        }
        .stTabs [data-baseweb="tab"] {
            color: #94a3b8;
            font-weight: 500;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: rgba(0, 200, 255, 0.2);
            color: #00ffff;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
            border: 1px solid rgba(0, 255, 255, 0.3);
        }

        /* ================= Code & Metrics ================= */
        code, pre {
            font-family: 'JetBrains Mono', monospace !important;
            background: rgba(0, 0, 0, 0.3) !important;
            border: 1px solid rgba(0, 255, 255, 0.2);
            border-radius: 6px;
            color: #00ffaa !important;
        }
        
        [data-testid="stMetricValue"] {
            font-family: 'JetBrains Mono', monospace;
            color: #00ffff !important;
            font-size: 1.5rem;
            font-weight: 700;
            text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        }
        [data-testid="stMetricLabel"] {
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.75rem;
        }

        /* ================= Toast Notifications ================= */
        .stToast {
            background: rgba(15, 23, 42, 0.95) !important;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0, 255, 255, 0.15);
            backdrop-filter: blur(10px);
        }

        /* ================= Success/Info/Error Messages ================= */
        .stSuccess, .stInfo, .stWarning, .stError {
            border-radius: 12px;
            border: 1px solid;
            backdrop-filter: blur(10px);
            background: rgba(15, 23, 42, 0.8) !important;
        }
        .stSuccess {
            border-color: rgba(0, 255, 170, 0.4);
            box-shadow: 0 0 20px rgba(0, 255, 170, 0.1);
        }
        .stSuccess > div:first-child {
            color: #00ffaa !important;
        }
        .stInfo {
            border-color: rgba(0, 200, 255, 0.4);
            box-shadow: 0 0 20px rgba(0, 200, 255, 0.1);
        }
        .stInfo > div:first-child {
            color: #00ccff !important;
        }
        .stWarning {
            border-color: rgba(255, 200, 0, 0.4);
            box-shadow: 0 0 20px rgba(255, 200, 0, 0.1);
        }
        .stWarning > div:first-child {
            color: #ffcc00 !important;
        }
        .stError {
            border-color: rgba(255, 80, 80, 0.4);
            box-shadow: 0 0 20px rgba(255, 80, 80, 0.1);
        }
        .stError > div:first-child {
            color: #ff5555 !important;
        }

        /* ================= Scrollbar - Tech Style ================= */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(15, 23, 42, 0.5);
        }
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #00ffff, #0080ff);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #00ccff, #0099ff);
        }

        /* ================= Image Display ================= */
        .stImage {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(0, 255, 255, 0.2);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        .stImage > div > div > div {
            font-size: 0.8rem;
            color: #00ccff;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(0, 0, 0, 0.5);
            padding: 0.5rem;
        }

        /* ================= Help Tooltip & Info Icons - EXTENSIVE FIX ================= */
        /* Fix for ALL st.help tooltip popups - targeting multiple possible selectors */
        
        /* Main tooltip container - try multiple selectors */
        [data-testid="stHelpTooltip"],
        .stTooltip,
        div[role="tooltip"],
        [class*="tooltip"],
        [data-baseweb="tooltip"] {
            background: rgba(5, 10, 20, 0.98) !important;
            border: 2px solid rgba(0, 255, 255, 0.8) !important;
            border-radius: 12px !important;
            box-shadow: 
                0 0 40px rgba(0, 255, 255, 0.4),
                0 8px 32px rgba(0, 0, 0, 0.6) !important;
            padding: 1rem 1.2rem !important;
            max-width: 320px !important;
        }
        
        /* Tooltip content - force dark background on ALL inner elements */
        [data-testid="stHelpTooltip"] *,
        .stTooltip *,
        div[role="tooltip"] *,
        [class*="tooltip"] *,
        [data-baseweb="tooltip"] * {
            background: transparent !important;
        }
        
        /* Tooltip content text - force white with high contrast */
        [data-testid="stHelpTooltip"] *,
        .stTooltip *,
        div[role="tooltip"] *,
        [class*="tooltip"] *,
        [data-baseweb="tooltip"] *,
        [data-testid="stHelpTooltip"] > div,
        [data-testid="stHelpTooltip"] p,
        [data-testid="stHelpTooltip"] span,
        [data-testid="stHelpTooltip"] div {
            color: #00ffff !important;
            font-size: 0.95rem !important;
            line-height: 1.6 !important;
            font-weight: 600 !important;
            text-shadow: 0 0 10px rgba(0, 0, 0, 1.0), 0 0 20px rgba(0, 0, 0, 0.8) !important;
        }
        
        /* Help icon (?) styling - more visible */
        [data-testid="stHelpIcon"],
        svg[data-testid="stHelpIcon"],
        [class*="HelpIcon"] {
            color: #00ffff !important;
            fill: #00ffff !important;
            background: rgba(0, 255, 255, 0.2) !important;
            border: 2px solid rgba(0, 255, 255, 0.5) !important;
            border-radius: 50% !important;
            width: 22px !important;
            height: 22px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-weight: 700 !important;
            font-size: 0.9rem !important;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.4) !important;
        }
        
        [data-testid="stHelpIcon"]:hover,
        svg[data-testid="stHelpIcon"]:hover {
            background: rgba(0, 255, 255, 0.35) !important;
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.6) !important;
            transform: scale(1.1);
        }

        /* ================= Select Box & Dropdown ================= */
        .stSelectbox > div > div {
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 8px;
            color: #ffffff !important;
        }
        .stSelectbox > div > div > div {
            color: #ffffff !important;
        }
        .stSelectbox > div > div:hover {
            border-color: rgba(0, 255, 255, 0.5);
        }

        /* Dropdown menu options - AGGRESSIVE FIX for white background */
        [data-baseweb="menu"],
        [data-baseweb="select-menu"],
        [data-baseweb="popover"],
        [data-baseweb="layer"],
        [data-baseweb="select"] [role="listbox"],
        div[role="listbox"],
        ul[role="listbox"] {
            background: rgba(5, 10, 20, 1.0) !important;
            background-color: rgba(5, 10, 20, 1.0) !important;
            border: 2px solid rgba(0, 255, 255, 0.6) !important;
            border-radius: 8px !important;
            box-shadow: 0 0 40px rgba(0, 255, 255, 0.3), 0 4px 20px rgba(0, 0, 0, 0.8) !important;
        }

        /* ALL dropdown items - force dark background and visible text */
        [data-baseweb="menu"] *,
        [data-baseweb="select-menu"] *,
        [data-baseweb="popover"] *,
        div[role="listbox"] *,
        ul[role="listbox"] *,
        [role="option"] {
            background: transparent !important;
            background-color: transparent !important;
        }

        /* Dropdown options text - bright cyan for visibility */
        [data-baseweb="menu"] li,
        [data-baseweb="select-menu"] li,
        [data-baseweb="popover"] li,
        [role="option"],
        [data-baseweb="menu"] div,
        [data-baseweb="select-menu"] div {
            color: #00ffff !important;
            background: transparent !important;
            font-weight: 600 !important;
            text-shadow: 0 0 10px rgba(0, 0, 0, 0.9) !important;
        }

        /* Hover state for options - bright background */
        [data-baseweb="menu"] li:hover,
        [data-baseweb="select-menu"] li:hover,
        [data-baseweb="popover"] li:hover,
        [role="option"]:hover {
            background: rgba(0, 200, 255, 0.25) !important;
            background-color: rgba(0, 200, 255, 0.25) !important;
            color: #ffffff !important;
        }

        /* Selected option - highlight */
        [data-baseweb="menu"] li[aria-selected="true"],
        [data-baseweb="select-menu"] li[aria-selected="true"],
        [role="option"][aria-selected="true"] {
            background: rgba(0, 255, 255, 0.35) !important;
            background-color: rgba(0, 255, 255, 0.35) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
        }

        /* ================= Checkbox & Radio ================= */
        .stCheckbox > div, .stRadio > div {
            color: #ffffff !important;
        }
        .stCheckbox > div > div, .stRadio > div > div {
            color: #ffffff !important;
        }
        .stCheckbox > div > div > div:first-child, .stRadio > div > div > div:first-child {
            background: rgba(0, 255, 255, 0.2);
            border-color: rgba(0, 255, 255, 0.4);
        }
        
        /* ================= Section Headers ================= */
        h1, h2, h3, h4, h5, h6 {
            color: #00ffff !important;
            font-family: 'JetBrains Mono', monospace;
            text-shadow: 0 0 20px rgba(0, 255, 255, 0.5) !important;
            letter-spacing: -0.02em;
        }
        h1 {
            border-bottom: 2px solid;
            border-image: linear-gradient(90deg, #00ffff, #0080ff) 1;
            padding-bottom: 0.5rem;
        }

        /* ================= Subheaders and Labels ================= */
        .stSubheader, [data-testid="stSubheader"] {
            color: #00ccff !important;
            font-weight: 600;
        }

        /* ================= Caption ================= */
        .stCaption {
            color: #a0c4e8 !important;
            font-size: 0.9rem !important;
            font-weight: 500 !important;
        }
        
        /* ================= Divider ================= */
        .stDivider {
            background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.5), transparent);
            height: 2px;
            border: none;
        }

        /* ================= Tech Loading Animation ================= */
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        
        .tech-scanline {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.8), transparent);
            animation: scanline 4s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }

        /* ================= Status Indicators ================= */
        .status-indicator {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .status-active {
            background: rgba(0, 255, 170, 0.15);
            border: 1px solid rgba(0, 255, 170, 0.4);
            color: #00ffaa;
        }

        .status-active::before {
            content: '';
            width: 8px;
            height: 8px;
            background: #00ffaa;
            border-radius: 50%;
            box-shadow: 0 0 10px #00ffaa;
            animation: pulse-dot 2s ease-in-out infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }

        /* ================= Holographic Effect ================= */
        .holographic {
            background: linear-gradient(
                135deg,
                rgba(0, 255, 255, 0.1) 0%,
                rgba(0, 200, 255, 0.05) 25%,
                rgba(0, 150, 255, 0.1) 50%,
                rgba(0, 200, 255, 0.05) 75%,
                rgba(0, 255, 255, 0.1) 100%
            );
            background-size: 400% 400%;
            animation: holographic-shift 8s ease infinite;
        }

        @keyframes holographic-shift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }

        /* ================= File Uploader - Dark Theme Fix ================= */
        [data-testid="stFileUploader"] {
            background: rgba(10, 15, 25, 0.95) !important;
            border: 3px dashed rgba(0, 255, 255, 0.5) !important;
            border-radius: 16px !important;
            padding: 1.5rem !important;
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.15),
                inset 0 0 20px rgba(0, 0, 0, 0.5);
        }
        
        [data-testid="stFileUploader"] > div {
            background: rgba(15, 25, 40, 0.9) !important;
            border: 2px solid rgba(0, 200, 255, 0.3) !important;
            border-radius: 12px !important;
            padding: 2rem !important;
        }
        
        /* File uploader text - bright cyan for visibility on dark bg */
        [data-testid="stFileUploader"] p,
        [data-testid="stFileUploader"] span,
        [data-testid="stFileUploader"] div,
        [data-testid="stFileUploader"] label {
            color: #00ffff !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            text-shadow: 0 0 10px rgba(0, 255, 255, 0.3) !important;
        }
        
        /* Drag and drop text - even brighter */
        [data-testid="stFileUploader"] [role="button"] {
            color: #ffffff !important;
            font-weight: 700 !important;
            text-shadow: 0 0 20px rgba(0, 255, 255, 1.0) !important;
            font-size: 1.2rem !important;
            letter-spacing: 0.05em;
        }
        
        /* Browse files button */
        [data-testid="stFileUploader"] button {
            background: linear-gradient(135deg, #0066cc, #00ccff) !important;
            color: #ffffff !important;
            border: 2px solid rgba(0, 255, 255, 0.5) !important;
            border-radius: 8px !important;
            padding: 0.75rem 2rem !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
            box-shadow: 0 0 20px rgba(0, 200, 255, 0.4) !important;
            margin-top: 1rem !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
        }
        
        /* Hover states */
        [data-testid="stFileUploader"]:hover {
            border-color: rgba(0, 255, 255, 0.8) !important;
            background: rgba(15, 25, 45, 0.98) !important;
            box-shadow: 
                0 0 40px rgba(0, 255, 255, 0.3),
                inset 0 0 30px rgba(0, 0, 0, 0.6);
        }
        
        [data-testid="stFileUploader"]:hover > div {
            border-color: rgba(0, 255, 255, 0.6) !important;
            background: rgba(20, 35, 55, 0.95) !important;
        }

        /* Icon in file uploader */
        [data-testid="stFileUploader"] svg,
        [data-testid="stFileUploader"] [data-testid="stIcon"] {
            color: #00ffff !important;
            fill: #00ffff !important;
            filter: drop-shadow(0 0 12px rgba(0, 255, 255, 0.8)) !important;
            width: 48px !important;
            height: 48px !important;
        }
        
        /* Small text like file limits */
        [data-testid="stFileUploader"] small {
            color: #88ccff !important;
            font-size: 0.85rem !important;
            opacity: 0.9;
        }

        /* ================= Cursor Effects ================= */
        /* Custom Tech Cursor */
        * {
            cursor: crosshair !important;
        }
        
        a, button, [role="button"], input, select, textarea, .stButton button {
            cursor: pointer !important;
        }

        /* ================= Hover Glow Effects ================= */
        /* Interactive elements glow on hover */
        .stButton button:hover,
        [data-testid="stFileUploader"]:hover,
        .stExpander:hover,
        .stTextInput input:hover,
        .stNumberInput input:hover,
        .stSelectbox > div > div:hover {
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.4),
                0 0 60px rgba(0, 200, 255, 0.2) !important;
            transition: all 0.3s ease;
        }

        /* Card hover lift effect */
        .stExpander:hover {
            transform: translateY(-3px);
        }

        /* Image hover glow */
        .stImage:hover {
            box-shadow: 
                0 0 40px rgba(0, 255, 255, 0.3),
                0 0 80px rgba(0, 200, 255, 0.2) !important;
            transform: scale(1.02);
            transition: all 0.4s ease;
        }
        </style>
    """, unsafe_allow_html=True)

    # 注入 JavaScript 动画
    st.markdown("""
        <script>
        // 添加扫描线效果
        function addScanline() {
            if (!document.getElementById('tech-scanline')) {
                const scanline = document.createElement('div');
                scanline.id = 'tech-scanline';
                scanline.className = 'tech-scanline';
                document.body.appendChild(scanline);
            }
        }
        
        // ================= Mouse Ripple Effect =================
        function createRipple(event) {
            const ripple = document.createElement('div');
            ripple.style.position = 'fixed';
            ripple.style.left = event.clientX + 'px';
            ripple.style.top = event.clientY + 'px';
            ripple.style.width = '0px';
            ripple.style.height = '0px';
            ripple.style.borderRadius = '50%';
            ripple.style.background = 'radial-gradient(circle, rgba(0,255,255,0.6) 0%, rgba(0,200,255,0.3) 40%, transparent 70%)';
            ripple.style.pointerEvents = 'none';
            ripple.style.zIndex = '99999';
            ripple.style.transform = 'translate(-50%, -50%)';
            ripple.style.animation = 'ripple-expand 0.6s ease-out forwards';
            
            document.body.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        }
        
        // Add ripple animation style
        const rippleStyle = document.createElement('style');
        rippleStyle.textContent = `
            @keyframes ripple-expand {
                0% {
                    width: 0px;
                    height: 0px;
                    opacity: 1;
                }
                100% {
                    width: 100px;
                    height: 100px;
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(rippleStyle);
        
        // ================= Mouse Trail Effect =================
        const trailDots = [];
        const maxTrailDots = 20;
        
        function createTrailDot(x, y) {
            const dot = document.createElement('div');
            dot.style.position = 'fixed';
            dot.style.left = x + 'px';
            dot.style.top = y + 'px';
            dot.style.width = '4px';
            dot.style.height = '4px';
            dot.style.backgroundColor = 'rgba(0, 255, 255, 0.8)';
            dot.style.borderRadius = '50%';
            dot.style.pointerEvents = 'none';
            dot.style.zIndex = '99998';
            dot.style.boxShadow = '0 0 10px rgba(0, 255, 255, 0.8), 0 0 20px rgba(0, 200, 255, 0.5)';
            dot.style.transform = 'translate(-50%, -50%)';
            
            document.body.appendChild(dot);
            trailDots.push(dot);
            
            // Fade out animation
            dot.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
            setTimeout(() => {
                dot.style.opacity = '0';
                dot.style.transform = 'translate(-50%, -50%) scale(0)';
            }, 10);
            
            // Remove after animation
            setTimeout(() => {
                dot.remove();
                const index = trailDots.indexOf(dot);
                if (index > -1) {
                    trailDots.splice(index, 1);
                }
            }, 510);
        }
        
        let lastTrailTime = 0;
        const trailInterval = 30; // ms
        
        document.addEventListener('mousemove', function(e) {
            const now = Date.now();
            if (now - lastTrailTime > trailInterval) {
                createTrailDot(e.clientX, e.clientY);
                lastTrailTime = now;
            }
        });
        
        // ================= Click Effects =================
        document.addEventListener('click', function(e) {
            createRipple(e);
            
            // Create burst effect
            for (let i = 0; i < 8; i++) {
                const angle = (i / 8) * Math.PI * 2;
                const distance = 30;
                const x = e.clientX + Math.cos(angle) * distance;
                const y = e.clientY + Math.sin(angle) * distance;
                
                setTimeout(() => {
                    createTrailDot(x, y);
                }, i * 30);
            }
        });
        
        // 页面加载完成后添加效果
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(addScanline, 1000);
        });
        
        // 添加打字机效果到特定元素
        function typeWriter(element, text, speed = 50) {
            let i = 0;
            element.textContent = '';
            function type() {
                if (i < text.length) {
                    element.textContent += text.charAt(i);
                    i++;
                    setTimeout(type, speed);
                }
            }
            type();
        }
        </script>
    """, unsafe_allow_html=True)

def render_hero_section():
    """
    渲染頂部 Hero 區塊 - 科技風格
    """
    st.markdown("""
        <div class="hero-header">
            <div>
                <div class="hero-title">◈ NKUST AoV Tool</div>
                <div class="hero-subtitle">FPGA-AWARE COMPUTER VISION PIPELINE GENERATOR</div>
            </div>
            <div style="text-align: right;">
                <div style="font-family: 'JetBrains Mono', monospace; color: #00ffff; font-size: 0.75rem;">
                    ◉ SYSTEM STATUS: <span style="color: #00ffaa;">ONLINE</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; color: #64748b; font-size: 0.7rem; margin-top: 0.5rem;">
                    v2.0.0 | NKUST Visual Lab
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_tech_card(title, content, icon="◈"):
    """
    渲染科技感卡片
    """
    st.markdown(f"""
        <div style="
            background: rgba(30, 41, 59, 0.4);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 255, 255, 0.2);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
        ">
            <div style="
                font-family: 'JetBrains Mono', monospace;
                color: #00ffff;
                font-size: 1.1rem;
                font-weight: 600;
                margin-bottom: 0.75rem;
                border-bottom: 1px solid rgba(0, 255, 255, 0.2);
                padding-bottom: 0.5rem;
            ">
                {icon} {title}
            </div>
            <div style="color: #e2e8f0; line-height: 1.6;">
                {content}
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_tech_badge(text, color="#00ffff"):
    """
    渲染科技徽章
    """
    st.markdown(f"""
        <span style="
            display: inline-block;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid {color};
            border-radius: 4px;
            padding: 0.25rem 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: {color};
            margin: 0.25rem;
        ">
            {text}
        </span>
    """, unsafe_allow_html=True)

def render_neon_text(text, color="#00ffff", size="1rem"):
    """
    渲染霓虹文字
    """
    st.markdown(f"""
        <span style="
            font-family: 'JetBrains Mono', monospace;
            color: {color};
            font-size: {size};
            text-shadow: 0 0 10px {color}80;
        ">
            {text}
        </span>
    """, unsafe_allow_html=True)

def render_status_indicator(status="active", text="ONLINE"):
    """
    渲染狀態指示器
    """
    status_class = f"status-{status}"
    st.markdown(f"""
        <div class="status-indicator {status_class}">
            {text}
        </div>
    """, unsafe_allow_html=True)
