from __future__ import annotations

import streamlit as st

from data import load_free_tier_tables


@st.cache_data(show_spinner="Loading Maycee public data...")
def load_cached_free_tier_tables() -> dict:
    return load_free_tier_tables()
