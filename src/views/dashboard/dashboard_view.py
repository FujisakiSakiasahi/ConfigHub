import streamlit as st

from src.controllers.dashboard_controller import DashboardController

_ctrl = DashboardController()

_OK_COLOR = "#4CAF50"
_MISSING_COLOR = "#EF4444"


def _overview_card(name: str, detail: str, status: str, ok: bool) -> str:
    color = _OK_COLOR if ok else _MISSING_COLOR
    return (
        '<div class="card overview-card">'
        f'<p class="card-title">{name}</p>'
        f'<p class="overview-card-detail">{detail}</p>'
        f'<span class="overview-card-status" style="color:{color};">{status}</span>'
        '</div>'
    )


def _render_overview(summary: dict) -> None:
    model_count = summary["model_count"]
    topology_loaded = summary["topology_loaded"]
    workload_loaded = summary["workload_loaded"]

    cards = [
        (
            "Models",
            f"{model_count} model checkpoint(s) detected in inferenceService",
            f"{model_count} loaded" if model_count else "None found",
            model_count > 0,
        ),
        (
            "Topology",
            "Network topology configured on Topology Manager",
            "Loaded" if topology_loaded else "Not loaded",
            topology_loaded,
        ),
        (
            "Workload",
            "Talker traffic streams configured on Topology Manager",
            "Loaded" if workload_loaded else "Not loaded",
            workload_loaded,
        ),
    ]

    cols = st.columns(3, gap="medium")
    for col, (name, detail, status, ok) in zip(cols, cards):
        with col:
            st.markdown(_overview_card(name, detail, status, ok), unsafe_allow_html=True)


def _render_loaded_models(summary: dict) -> None:
    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Loaded Models</p>',
            unsafe_allow_html=True,
        )

        models = summary["models"]
        if not models:
            st.markdown(
                '<div class="empty-state" style="padding:40px 24px;">'
                '<div class="empty-state-icon" style="font-size:2rem;opacity:0.4;">&#129302;</div>'
                '<p class="empty-state-desc" style="margin-top:8px;">'
                'No model checkpoints (*.pt) were detected in inferenceService/models.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        st.dataframe(
            _ctrl.models_to_dataframe(models),
            width='stretch',
            hide_index=True,
            column_config={
                "model_id": st.column_config.TextColumn("Model ID", width="medium"),
                "name": st.column_config.TextColumn("Name", width="medium"),
                "version": st.column_config.TextColumn("Version", width="small"),
                "description": st.column_config.TextColumn("Description", width="large"),
            },
        )


def render() -> None:
    st.markdown(
        '<div class="page-header">'
        '<h1 class="page-title">Dashboard</h1>'
        '<p class="page-subtitle">Overview of your network configuration status</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    topology_loaded = bool(st.session_state.get("topology_loaded"))
    workload_rows = st.session_state.get("workload_rows", [])
    total_streams = sum(len(r.get("streams", [])) for r in workload_rows)
    workload_loaded = topology_loaded and total_streams > 0

    summary = _ctrl.get_summary(topology_loaded, workload_loaded)

    st.markdown(
        '<p style="color:#7C85A2;font-size:0.8rem;font-weight:600;margin:0 0 0.75rem 0;">'
        'SYSTEM OVERVIEW</p>',
        unsafe_allow_html=True,
    )
    _render_overview(summary)
    _render_loaded_models(summary)
