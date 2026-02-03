
import streamlit as st
import json

def render_parameter_editor(node: dict, idx: int, node_id: str):
    """
    渲染參數編輯器 (UI Component)
    """
    params = node.get('parameters', {})
    if not params:
        return

    st.markdown("**操作參數**")
    for param_name, param_info in params.items():
        param_default = param_info.get('default')
        # [Fix] Ensure description is not None. 
        # .get('description', default) only works if key is missing. If key exists but is None, it returns None.
        param_desc = param_info.get('description') or param_name
        
        col_p1, col_p2 = st.columns([1, 2])
        with col_p1:
            st.caption(str(param_desc))
        
        with col_p2:
            key = f"param_{node_id}_{param_name}"
            
            # Debug: Check for potential collision or bad values
            # print(f"[Debug] Rendering {key}: Type={type(param_default)}, Value={param_default}")

            # Boolean
            if isinstance(param_default, bool):
                new_value = st.checkbox(str(param_desc), value=param_default, key=key, label_visibility="collapsed")
            
            # Integer
            elif isinstance(param_default, int):
                # [Fix] Streamlit number_input crashes if label is not string
                new_value = st.number_input(str(param_desc), value=int(param_default), step=1, key=key, label_visibility="collapsed")
            
            # Float
            elif isinstance(param_default, float):
                # [Fix] Streamlit number_input crashes if label is not string
                new_value = st.number_input(str(param_desc), value=float(param_default), step=0.1, format="%.2f", key=key, label_visibility="collapsed")
            
            # List (as string)
            elif isinstance(param_default, list) or isinstance(param_default, tuple):
                # [Fix] Handle potential non-string conversion issues
                try:
                    val_str = json.dumps(param_default) if isinstance(param_default, (dict, list, tuple)) else str(param_default)
                except Exception as e:
                    print(f"[Error] Failed to serialize parameter {param_name}: {e}")
                    val_str = str(param_default)

                new_value_str = st.text_input(str(param_desc), value=val_str, key=key, label_visibility="collapsed")
                try:
                    new_value = json.loads(new_value_str)
                except:
                    new_value = param_default
            
            # String/Other
            else:
                # [Fix] Ensure value is always a string for text_input
                val_str = str(param_default) if param_default is not None else ""
                new_value = st.text_input(str(param_desc), value=val_str, key=key, label_visibility="collapsed")
            
            # Update State
            if new_value != param_default:
                st.session_state.pipeline[idx]['parameters'][param_name]['default'] = new_value
                # [Auto-execution] Mark for auto-execution on parameter change
                st.session_state._auto_execute = True
