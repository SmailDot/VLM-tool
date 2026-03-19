
import streamlit as st
import streamlit.components.v1 as components
from typing import List

from app.manufacturing.schema import RecognitionResult

# Try importing Pyvis
try:
    from pyvis.network import Network
except ImportError as e:
    st.error(f"Pyvis Library Error: {e}")
    Network = None

def render_pipeline_graph(pipeline):
    """
    渲染 Pipeline 流程圖 (PyVis)
    """
    if not pipeline:
        st.info("請先產生 Pipeline")
        return

    if Network:
        try:
            # Create pyvis network
            net = Network(height="600px", width="100%", bgcolor="#ffffff", cdn_resources='in_line')
            
            # Configure physics
            net.set_options("""
            {
                "physics": {
                "enabled": true,
                "stabilization": {"enabled": true, "iterations": 100},
                "barnesHut": {"gravitationalConstant": -8000, "centralGravity": 0.3, "springLength": 200}
                },
                "interaction": {"dragNodes": true, "dragView": true, "zoomView": true}
            }
            """)
            
            # Add nodes
            for idx, node in enumerate(pipeline):
                node_id = node.get('id', f'node_{idx}')
                node_name = node.get('name', '未知')
                params = node.get('parameters', {})
                
                param_strs = []
                for i, (k, v) in enumerate(params.items()):
                    if i >= 2:
                        break
                    default_val = v.get('default', '?')
                    if isinstance(default_val, list):
                        default_val = str(default_val)
                    param_strs.append(f"{k}:{default_val}")
                
                param_line = ", ".join(param_strs) if param_strs else "無參數"
                
                label = f"{node_name}\n{param_line}"
                title = f"<b>{node_name}</b><br>參數: {param_line}"
                
                # Simple color scheme without FPGA resource usage
                color = '#E3F2FD'  # Light blue for all nodes
                
                net.add_node(node_id, label=label, title=title, color=color, shape='box',
                            font={'size': 14, 'face': 'Microsoft JhengHei'}, borderWidth=2)
            
            # Add edges
            for i in range(len(pipeline) - 1):
                current_node = pipeline[i]
                next_node = pipeline[i + 1]
                
                current_id = current_node.get('id', f'node_{i}')
                next_id = next_node.get('id', f'node_{i+1}')
                
                net.add_edge(current_id, next_id, color='#1976D2', arrows='to',
                            font={'size': 12, 'face': 'Microsoft JhengHei'})
            
            # Generate HTML
            html_content = net.generate_html()
                
            components.html(html_content, height=620, scrolling=False)
            
            st.info(f"Pipeline 共 {len(pipeline)} 個節點")
            
        except Exception as e:
            st.error(f"Error rendering graph: {e}")
            import traceback
            st.code(traceback.format_exc())
            
    else:
        st.warning("無法載入流程圖模組 (pyvis)。請確認已安裝：pip install pyvis")


def render_predictions(result: RecognitionResult, min_confidence: float) -> None:
    """
    Render prediction list with collapsed expanders.

    Args:
        result: RecognitionResult to display.
        min_confidence: Confidence threshold for display.
    """
    predictions = [p for p in result.predictions if p.confidence >= min_confidence]

    if not predictions:
        st.warning("⚠️ 未找到符合條件的製程")
        st.info("💡 **建議**:\n- 降低信心度門檻\n- 檢查圖紙品質與解析度\n- 確認 VLM 服務連線正常")
        return

    for i, pred in enumerate(predictions, 1):
        confidence_pct = pred.confidence * 100

        if confidence_pct >= 70:
            color_emoji = "🟢"
            color_text = "高"
            color_style = "color: #28a745; font-weight: bold;"
        elif confidence_pct >= 50:
            color_emoji = "🟡"
            color_text = "中"
            color_style = "color: #ffc107; font-weight: bold;"
        else:
            color_emoji = "🔴"
            color_text = "低"
            color_style = "color: #dc3545; font-weight: bold;"

        with st.expander(
            f"{color_emoji} **{i}. {pred.name}** ({confidence_pct:.1f}%) - {color_text}信心度",
            expanded=False
        ):
            col_prog1, col_prog2 = st.columns([3, 1])
            with col_prog1:
                st.progress(pred.confidence)
            with col_prog2:
                st.markdown(
                    f"<span style='{color_style}'>{confidence_pct:.1f}%</span>",
                    unsafe_allow_html=True
                )

            if pred.reasoning:
                st.markdown("**辨識依據:**")
                for evidence_item in pred.reasoning.split("\n"):
                    if evidence_item.strip():
                        st.markdown(f"- {evidence_item}")
            else:
                st.caption("(依據經驗判斷)")

            st.caption(f"製程 ID: {pred.process_id}")
