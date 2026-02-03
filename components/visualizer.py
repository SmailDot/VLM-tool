
import streamlit as st
import streamlit.components.v1 as components
import os
import tempfile

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
            # use_dot=True might be needed if using dot layout, but here we use default.
            # cdn_resources='in_line' ensures it works even without internet or weird local paths
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
                fpga = node.get('fpga_constraints', {})
                clk = fpga.get('estimated_clk', 0)
                latency_type = fpga.get('latency_type', 'Unknown')
                resource = fpga.get('resource_usage', 'Unknown')
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
                
                label = f"{node_name}\n{param_line}\n{latency_type}\n{clk} clk"
                title = f"<b>{node_name}</b><br>CLK: {clk}<br>資源: {resource}<br>延遲: {latency_type}"
                
                color_map = {
                    'Low': '#C8E6C9',
                    'Medium': '#FFF9C4',
                    'High': '#FFCCBC',
                    'Very High': '#FFCDD2'
                }
                color = color_map.get(resource, '#E0E0E0')
                
                net.add_node(node_id, label=label, title=title, color=color, shape='box',
                            font={'size': 14, 'face': 'Microsoft JhengHei'}, borderWidth=2)
            
            # Add edges
            for i in range(len(pipeline) - 1):
                current_node = pipeline[i]
                next_node = pipeline[i + 1]
                
                current_id = current_node.get('id', f'node_{i}')
                next_id = next_node.get('id', f'node_{i+1}')
                
                # Safe access to fpga_constraints
                fpga = current_node.get('fpga_constraints', {})
                clk_label = f"{fpga.get('estimated_clk', 0)} clk"            
                net.add_edge(current_id, next_id, label=clk_label, color='#1976D2', arrows='to',
                            font={'size': 12, 'face': 'Microsoft JhengHei'})
            
            # Generate HTML directly using utf-8 handling
            # Note: generate_html() returns the HTML string. 
            # We don't use save_graph() because it defaults to system encoding (cp950 on Windows) which fails with special chars.
            html_content = net.generate_html()
                
            components.html(html_content, height=620, scrolling=False)
            
            total_clk = sum(n.get('fpga_constraints', {}).get('estimated_clk', 0) for n in pipeline)
            st.metric("總時脈", f"{total_clk} clk")
            
        except Exception as e:
            st.error(f"Error rendering graph: {e}")
            import traceback
            st.code(traceback.format_exc())
            
    else:
        st.warning("無法載入流程圖模組 (pyvis)。請確認已安裝：pip install pyvis")

