import html
import json as json_lib

import streamlit as st

from src.controllers.logs_controller import LogsController

_ctrl = LogsController()

_LEVEL_COLORS = {
    "DEBUG":   "#6B7280",
    "INFO":    "#4F9CF9",
    "SUCCESS": "#4CAF50",
    "WARNING": "#F5A623",
    "ERROR":   "#EF4444",
}


def _stat_card(label: str, value: int, color: str) -> str:
    return (
        '<div style="background:#1A1E2E;border:1px solid #2D3250;border-radius:8px;'
        'padding:14px 16px;flex:1;">'
        f'<p style="color:#7C85A2;font-size:0.75rem;margin:0 0 4px 0;">{label}</p>'
        f'<p style="color:{color};font-size:1.4rem;font-weight:700;margin:0;">{value}</p>'
        '</div>'
    )


def _row_html(e: dict) -> str:
    color = _LEVEL_COLORS.get(e.get("level"), "#7C85A2")
    ts = html.escape(e.get("timestamp", "").replace("T", " "))
    level = html.escape(e.get("level", ""))
    category = html.escape(e.get("category", ""))
    event = html.escape(e.get("event", ""))
    message = html.escape(e.get("message", ""))

    details = e.get("details") or {}
    details_html = ""
    if details:
        details_json = html.escape(json_lib.dumps(details, indent=2, default=str))
        details_html = (
            '<details style="margin-top:4px;">'
            '<summary style="color:#4F9CF9;font-size:0.72rem;cursor:pointer;">details</summary>'
            f'<pre style="background:#111827;border-radius:6px;padding:8px 10px;margin:6px 0 0 0;'
            f'color:#B9C0D4;font-size:0.72rem;white-space:pre-wrap;">{details_json}</pre>'
            '</details>'
        )

    return (
        '<tr style="border-bottom:1px solid #2D3250;">'
        f'<td style="padding:8px 10px;color:#7C85A2;font-size:0.78rem;white-space:nowrap;vertical-align:top;">{ts}</td>'
        f'<td style="padding:8px 10px;vertical-align:top;">'
        f'<span style="color:{color};font-weight:700;font-size:0.78rem;">{level}</span></td>'
        f'<td style="padding:8px 10px;color:#9AA3C0;font-size:0.78rem;vertical-align:top;white-space:nowrap;">{category}</td>'
        f'<td style="padding:8px 10px;color:#9AA3C0;font-size:0.78rem;vertical-align:top;white-space:nowrap;">{event}</td>'
        f'<td style="padding:8px 10px;color:#FAFAFA;font-size:0.82rem;vertical-align:top;">{message}{details_html}</td>'
        '</tr>'
    )


def render() -> None:
    st.markdown(
        '<div class="page-header">'
        '<h1 class="page-title">Logs</h1>'
        '<p class="page-subtitle">Audit trail and system event logs</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    counts = _ctrl.counts_by_level()
    stat_cols = st.columns(5)
    for col, level in zip(stat_cols, _ctrl.levels()):
        with col:
            st.markdown(_stat_card(level.title(), counts.get(level, 0), _LEVEL_COLORS[level]), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1.25rem'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Filters</p>',
            unsafe_allow_html=True,
        )

        f1, f2, f3, f4 = st.columns([1.3, 1.3, 2, 1])
        with f1:
            level_filter = st.multiselect("Level", options=_ctrl.levels(), default=[], key="log_level_filter")
        with f2:
            category_filter = st.multiselect("Category", options=_ctrl.categories(), default=[], key="log_category_filter")
        with f3:
            search = st.text_input("Search message / event", key="log_search")
        with f4:
            limit = st.number_input("Max rows", min_value=10, max_value=2000, value=200, step=10, key="log_limit")

        btn_c1, btn_c2, _ = st.columns([1, 1, 4])
        with btn_c1:
            if st.button("Refresh", width='stretch'):
                st.rerun()
        with btn_c2:
            if st.button("Clear Logs", width='stretch'):
                _ctrl.clear_logs()
                st.rerun()

    st.markdown("<div style='margin-top:1.25rem'></div>", unsafe_allow_html=True)

    entries = _ctrl.get_logs(
        limit=int(limit),
        level=level_filter[0] if len(level_filter) == 1 else None,
        category=category_filter[0] if len(category_filter) == 1 else None,
        search=search or None,
    )
    if level_filter and len(level_filter) > 1:
        entries = [e for e in entries if e.get("level") in level_filter]
    if category_filter and len(category_filter) > 1:
        entries = [e for e in entries if e.get("category") in category_filter]

    with st.container(border=True):
        st.markdown(
            f'<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">'
            f'Events ({len(entries)})</p>',
            unsafe_allow_html=True,
        )

        if not entries:
            st.markdown(
                '<div class="empty-state">'
                '<div class="empty-state-icon">&#128203;</div>'
                '<h3 class="empty-state-title">No log entries</h3>'
                '<p class="empty-state-desc">Events from Topology Manager and Configuration Generation '
                '(loads, model runs, validation, exports, errors) will appear here as you use the app.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        table_html = (
            '<div style="overflow-x:auto;max-height:640px;overflow-y:auto;">'
            '<table style="width:100%;border-collapse:collapse;">'
            '<thead><tr style="border-bottom:1px solid #2D3250;position:sticky;top:0;background:#1A1E2E;">'
            '<th style="text-align:left;padding:6px 10px;color:#7C85A2;font-size:0.72rem;font-weight:600;">TIME</th>'
            '<th style="text-align:left;padding:6px 10px;color:#7C85A2;font-size:0.72rem;font-weight:600;">LEVEL</th>'
            '<th style="text-align:left;padding:6px 10px;color:#7C85A2;font-size:0.72rem;font-weight:600;">CATEGORY</th>'
            '<th style="text-align:left;padding:6px 10px;color:#7C85A2;font-size:0.72rem;font-weight:600;">EVENT</th>'
            '<th style="text-align:left;padding:6px 10px;color:#7C85A2;font-size:0.72rem;font-weight:600;">MESSAGE</th>'
            '</tr></thead><tbody>'
            + "".join(_row_html(e) for e in entries)
            + '</tbody></table></div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)
