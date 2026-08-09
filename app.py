import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.views.shared.navbar import render_navbar
from src.views.dashboard.dashboard_view import render as render_dashboard
from src.views.topology_manager.topology_view import render as render_topology
from src.views.configuration_generation.config_view import render as render_config
from src.views.logs.logs_view import render as render_logs
from src.views.documentation.docs_view import render as render_docs

st.set_page_config(
    page_title="ConfigHub",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

active = render_navbar()

_PAGES = {
    "dashboard": render_dashboard,
    "topology":  render_topology,
    "config":    render_config,
    "logs":      render_logs,
    "docs":      render_docs,
}

_PAGES.get(active, render_dashboard)()
