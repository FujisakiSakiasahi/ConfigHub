import json

import streamlit as st

from src.controllers.config_controller import ConfigController, PIPELINE_STEPS

_ctrl = ConfigController()


# ── status helpers ───────────────────────────────────────────────────────────

def _render_status_row(name: str, passed, detail: str) -> None:
    cols = st.columns([0.09, 0.4, 0.51])
    with cols[0]:
        st.markdown(_ctrl.status_icon(passed), unsafe_allow_html=True)
    with cols[1]:
        color = "#FAFAFA" if passed is not None else "#7C85A2"
        st.markdown(f'<span style="font-size:0.85rem;color:{color};">{name}</span>', unsafe_allow_html=True)
    with cols[2]:
        st.markdown(
            f'<span style="font-size:0.78rem;color:#7C85A2;">{detail}</span>',
            unsafe_allow_html=True,
        )


# ── sections ──────────────────────────────────────────────────────────────────

def _render_setup(models: list[dict], topology_loaded: bool, workload_rows: list) -> None:
    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Generation Setup</p>',
            unsafe_allow_html=True,
        )

        if models:
            labels = [
                f"{m['name']}  ·  in={m['in_channels']}/hidden={m['hidden_channels']}  ·  {m['size_kb']} KB"
                for m in models
            ]
            idx = st.selectbox(
                "Model",
                options=range(len(models)),
                format_func=lambda i: labels[i],
                key="gen_model_idx",
            )
            selected_model = models[idx]
            st.caption(
                f"Architecture: 2-layer GraphSAGE GNN "
                f"({selected_model['in_channels']} input features → "
                f"{selected_model['hidden_channels']} hidden → "
                f"{selected_model['out_channels']} gate-duration fractions)"
            )
        else:
            st.selectbox("Model", options=["No model available"], disabled=True)
            st.warning("No trained model (*.pt) found in inferenceService/models.")
            selected_model = None

        st.markdown("<div style='margin-top:0.75rem'></div>", unsafe_allow_html=True)
        st.markdown(
            '<p style="color:#7C85A2;font-size:0.8rem;font-weight:600;margin:0 0 6px 0;">INPUTS</p>',
            unsafe_allow_html=True,
        )

        total_streams = sum(len(r.get("streams", [])) for r in workload_rows)
        for check in _ctrl.readiness(topology_loaded, workload_rows, bool(models)):
            _render_status_row(check["name"], check["passed"], check["detail"])

        st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
        can_generate = topology_loaded and total_streams > 0 and bool(models)

        if st.button("Generate GCL", type="primary", width='stretch', disabled=not can_generate):
            topo_params = {
                "topology_id": st.session_state.get("topology_id", "TsnIntelStar"),
                "num_talkers": st.session_state.get("num_talkers", 1),
                "num_switches": st.session_state.get("num_switches", 1),
                "num_listeners": st.session_state.get("num_listeners", 1),
                "link_datarate_Mbps": st.session_state.get("link_datarate_Mbps", 1000),
                "device_model": st.session_state.get("device_model", "intel_i226"),
                "num_tx_queues": st.session_state.get("num_tx_queues", 4),
                "gcl_cycle_time_ns": st.session_state.get("gcl_cycle_time_ns", 1_000_000),
                "edges": st.session_state.get("edges", []),
            }
            with st.spinner("Running model inference…"):
                st.session_state["gcl_result"] = _ctrl.generate(
                    topo_params, workload_rows, selected_model["path"]
                )
            st.rerun()

        if not can_generate:
            st.caption("Load a topology with at least one stream, and ensure a model is available, to enable generation.")


def _render_pipeline_status() -> None:
    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Pipeline Status</p>',
            unsafe_allow_html=True,
        )

        result = st.session_state.get("gcl_result")
        if result is None:
            st.markdown(
                '<div style="padding:24px 8px;text-align:center;">'
                '<p style="color:#4A5070;font-size:0.85rem;">Run generation to see step-by-step status.</p>'
                "</div>",
                unsafe_allow_html=True,
            )
            return

        steps_by_name = {s["name"]: s for s in result["steps"]}
        for name in PIPELINE_STEPS:
            step = steps_by_name.get(name)
            if step is None:
                _render_status_row(name, None, "Not reached")
            else:
                _render_status_row(name, step["passed"], step["detail"])

        if result.get("error"):
            st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)
            st.error(result["error"])


def _render_gcl_output(result: dict) -> None:
    gcl = result.get("gcl")
    if not gcl:
        return

    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Generated GCL</p>',
            unsafe_allow_html=True,
        )

        tab_table, tab_json = st.tabs(["Table", "Raw JSON"])
        with tab_table:
            st.dataframe(_ctrl.gcl_to_dataframe(gcl), width='stretch', hide_index=True)
        with tab_json:
            gcl_json = json.dumps(gcl, indent=2)
            st.code(gcl_json, language="json")
            st.download_button(
                "Download gcl.json", data=gcl_json, file_name="gcl.json",
                mime="application/json", width='stretch',
            )


def _render_xml_output(result: dict) -> None:
    xml_str = result.get("xml")
    if not xml_str:
        return

    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">XML Output</p>',
            unsafe_allow_html=True,
        )
        st.code(xml_str, language="xml")
        st.download_button(
            "Download config.xml", data=xml_str, file_name="config.xml",
            mime="application/xml", width='stretch',
        )


# ── main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown(
        '<div class="page-header">'
        '<h1 class="page-title">Configuration Generation</h1>'
        '<p class="page-subtitle">Generate and validate a GCL schedule from the loaded topology and workload</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    topology_loaded = bool(st.session_state.get("topology_loaded"))
    workload_rows = st.session_state.get("workload_rows", [])
    models = _ctrl.list_models()

    left, right = st.columns([1, 1.3], gap="large")
    with left:
        _render_setup(models, topology_loaded, workload_rows)
    with right:
        _render_pipeline_status()

    result = st.session_state.get("gcl_result")
    if result:
        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
        _render_gcl_output(result)
        st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
        _render_xml_output(result)
