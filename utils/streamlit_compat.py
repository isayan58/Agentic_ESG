"""Compatibility helpers for constrained local Streamlit environments."""
import pandas as pd
import streamlit as st


def safe_dataframe(data, use_container_width=True, hide_index=False):
    """Render a dataframe, falling back when pyarrow is unavailable."""
    try:
        st.dataframe(data, use_container_width=use_container_width, hide_index=hide_index)
    except ModuleNotFoundError as exc:
        if exc.name != "pyarrow":
            raise

        df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        st.caption("Interactive table fallback active. Install `pyarrow` for native Streamlit dataframes.")
        st.markdown(df.to_html(index=not hide_index, escape=False), unsafe_allow_html=True)
