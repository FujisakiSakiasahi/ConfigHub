import streamlit as st
from src.controllers.topology_controller import TopologyController

_ctrl = TopologyController()

_TOPOLOGY_OPTIONS = [
    "single-switch star (talker → switch → listener(s))",
    "line",
    "tree",
    "ring",
    "custom",
]
_STREAM_TYPES = ["TT7", "TT6", "TT5", "BE", "AVB"]


# ── session-state glue ──────────────────────────────────────────────────────────
#
# Streamlit deletes a widget's session_state entry whenever the widget isn't
# instantiated during a script run. Since each "page" here is just a
# conditionally-called render function within one script, switching tabs away
# from Topology Manager wipes any widget whose own `key=` doubles as the
# persisted data key (e.g. loaded values silently reverting to the widget's
# hardcoded default). These wrappers keep the widget's own key private
# (`_w_<data_key>`) and always re-seed `value=` from the separate, never-wiped
# `data_key` entry, so loaded data survives navigating away and back.

def _persisted_number_input(label: str, data_key: str, default, **kwargs):
    value = st.number_input(
        label,
        value=type(default)(st.session_state.get(data_key, default)),
        key=f"_w_{data_key}",
        **kwargs,
    )
    st.session_state[data_key] = value
    return value


def _persisted_text_input(label: str, data_key: str, default: str, **kwargs) -> str:
    value = st.text_input(
        label,
        value=st.session_state.get(data_key, default),
        key=f"_w_{data_key}",
        **kwargs,
    )
    st.session_state[data_key] = value
    return value


def _persisted_selectbox(label: str, data_key: str, options: list, default, **kwargs):
    current = st.session_state.get(data_key, default)
    index = options.index(current) if current in options else 0
    value = st.selectbox(label, options=options, index=index, key=f"_w_{data_key}", **kwargs)
    st.session_state[data_key] = value
    return value


def _ensure_workload_rows() -> None:
    num_talkers = int(st.session_state.get("num_talkers", 1))
    existing = st.session_state.get("workload_rows", [])
    if len(existing) != num_talkers:
        st.session_state["workload_rows"] = _ctrl.default_workload_rows(num_talkers)
        st.session_state["selected_workload_row"] = None


# Data keys managed by the _persisted_* widget helpers above (i.e. ones with
# a shadow "_w_<key>" widget key that also needs updating on file load).
_TOPO_WIDGET_KEYS = [
    "topology_id", "num_switches", "num_talkers", "num_listeners",
    "link_datarate_Mbps", "device_model", "num_tx_queues",
    "topology_pattern", "cycle_time", "cycle_unit",
]


def _apply_topology_data(data: dict) -> None:
    normalized = _ctrl.normalize_topology_payload(data, _TOPOLOGY_OPTIONS)
    st.session_state.update(normalized)
    # A widget only honours a new `value=` the first time its key is created;
    # once instantiated it keeps using its own stored state on every later
    # rerun, even if we pass a different `value=`. Push the freshly loaded
    # values straight into each widget's shadow key too (the officially
    # supported way to update a widget from a callback), so the fields
    # update immediately instead of only after navigating away and back.
    for key in _TOPO_WIDGET_KEYS:
        if key in normalized:
            st.session_state[f"_w_{key}"] = normalized[key]
    st.session_state["selected_workload_row"] = None
    st.session_state["topology_loaded"] = True
    st.session_state["topology_file_error"] = None


def _handle_load_from_file_click() -> None:
    uploaded = st.session_state.get("topology_json_upload")
    if uploaded is None:
        return
    try:
        content = _ctrl.read_json_upload(uploaded)
    except ValueError:
        st.session_state["topology_file_error"] = "Invalid JSON file."
        return

    runs = _ctrl.extract_runs(content)
    if not runs:
        st.session_state["topology_file_error"] = "No topology/workload data found in file."
        _ctrl.log_topology_file_empty()
        return

    idx = st.session_state.get("topology_file_run_idx", 0)
    idx = idx if isinstance(idx, int) and 0 <= idx < len(runs) else 0
    _apply_topology_data(runs[idx])
    _ctrl.log_topology_loaded_from_file(len(runs), idx)


# ── SVG visualisation ──────────────────────────────────────────────────────────

def _star_svg(n_talkers: int, n_listeners: int) -> str:
    rows = max(n_talkers, n_listeners)
    W = 500
    H = max(260, rows * 90 + 80)
    cx, cy = W // 2, H // 2
    r_node = 26
    sw_half = 32

    talker_ys = [cy + (i - (n_talkers - 1) / 2) * 90 for i in range(n_talkers)]
    listener_ys = [cy + (i - (n_listeners - 1) / 2) * 90 for i in range(n_listeners)]
    tx, lx = 90, W - 90

    defs = (
        '<defs><marker id="arr-right" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#4F9CF9" opacity="0.8"/></marker></defs>'
    )
    lines, nodes = [], []
    for y in talker_ys:
        lines.append(
            f'<line x1="{tx + r_node}" y1="{y}" x2="{cx - sw_half - 4}" y2="{cy}"'
            f' stroke="#4F9CF9" stroke-width="1.8" stroke-opacity="0.6" marker-end="url(#arr-right)"/>'
        )
    for y in listener_ys:
        lines.append(
            f'<line x1="{cx + sw_half + 4}" y1="{cy}" x2="{lx - r_node - 4}" y2="{y}"'
            f' stroke="#4F9CF9" stroke-width="1.8" stroke-opacity="0.6" marker-end="url(#arr-right)"/>'
        )
    for i, y in enumerate(talker_ys):
        nodes += [
            f'<circle cx="{tx}" cy="{y}" r="{r_node}" fill="#1E3A5F" stroke="#4F9CF9" stroke-width="2"/>',
            f'<text x="{tx}" y="{y}" text-anchor="middle" dominant-baseline="central" fill="#FAFAFA" font-size="11" font-family="sans-serif" font-weight="600">T{i+1}</text>',
            f'<text x="{tx}" y="{y+r_node+13}" text-anchor="middle" fill="#7C85A2" font-size="9" font-family="sans-serif">Talker {i+1}</text>',
        ]
    nodes += [
        f'<rect x="{cx-sw_half}" y="{cy-sw_half}" width="{sw_half*2}" height="{sw_half*2}" rx="8" fill="#1A3520" stroke="#4CAF50" stroke-width="2"/>',
        f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central" fill="#FAFAFA" font-size="11" font-family="sans-serif" font-weight="600">SW1</text>',
        f'<text x="{cx}" y="{cy+sw_half+13}" text-anchor="middle" fill="#7C85A2" font-size="9" font-family="sans-serif">Switch 1</text>',
    ]
    for i, y in enumerate(listener_ys):
        nodes += [
            f'<circle cx="{lx}" cy="{y}" r="{r_node}" fill="#3A1E5F" stroke="#9C6FD9" stroke-width="2"/>',
            f'<text x="{lx}" y="{y}" text-anchor="middle" dominant-baseline="central" fill="#FAFAFA" font-size="11" font-family="sans-serif" font-weight="600">L{i+1}</text>',
            f'<text x="{lx}" y="{y+r_node+13}" text-anchor="middle" fill="#7C85A2" font-size="9" font-family="sans-serif">Listener {i+1}</text>',
        ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}"'
        f' style="background:#111827;border-radius:8px;display:block;">'
        f'{defs}{"".join(lines)}{"".join(nodes)}</svg>'
    )


# ── edges section ──────────────────────────────────────────────────────────────

def _render_edges() -> None:
    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Edges</p>',
            unsafe_allow_html=True,
        )

        if not st.session_state.get("topology_loaded"):
            st.markdown(
                '<div class="empty-state" style="padding:40px 24px;">'
                '<div class="empty-state-icon" style="font-size:2rem;opacity:0.4;">⚠</div>'
                '<p class="empty-state-desc" style="margin-top:8px;">'
                'Please load a network before configuring edges.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        df = _ctrl.edges_to_df(st.session_state.get("edges", []))
        edited_df = st.data_editor(
            df,
            key="edges_ed",
            num_rows="dynamic",
            width='stretch',
            hide_index=True,
            column_config={
                "from": st.column_config.TextColumn("From", width="small"),
                "to": st.column_config.TextColumn("To", width="small"),
                "port_id": st.column_config.TextColumn("Port ID (optional)", width="medium"),
            },
        )
        st.session_state["edges"] = _ctrl.df_to_edges(edited_df)


# ── workload section ───────────────────────────────────────────────────────────

def _render_workload() -> None:
    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Workload</p>',
            unsafe_allow_html=True,
        )

        if not st.session_state.get("topology_loaded"):
            st.markdown(
                '<div class="empty-state" style="padding:40px 24px;">'
                '<div class="empty-state-icon" style="font-size:2rem;opacity:0.4;">⚠</div>'
                '<p class="empty-state-desc" style="margin-top:8px;">'
                'Please load a network before configuring workload.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        _ensure_workload_rows()
        rows: list = st.session_state["workload_rows"]
        selected: int | None = st.session_state.get("selected_workload_row")
        link_datarate = float(st.session_state.get("link_datarate_Mbps", 1000))

        wl_left, wl_right = st.columns([1, 1.6], gap="large")

        # ── left panel: workload summary table ────────────────────────────────
        with wl_left:
            st.markdown(
                '<p style="color:#7C85A2;font-size:0.8rem;font-weight:600;margin:0 0 6px 0;">'
                'TALKER WORKLOAD</p>',
                unsafe_allow_html=True,
            )

            # header row
            hcols = st.columns([0.35, 0.7, 0.7, 0.8, 0.55, 0.4])
            for col, label in zip(hcols, ["", "Talker", "Switch", "Listener", "Streams", "Status"]):
                col.markdown(
                    f'<span style="color:#7C85A2;font-size:0.78rem;font-weight:600;">{label}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                '<hr style="border:none;border-top:1px solid #2D3250;margin:4px 0 6px 0;">',
                unsafe_allow_html=True,
            )

            for i, row in enumerate(rows):
                streams = row["streams"]
                status_html, _ = _ctrl.stream_status(streams)
                is_sel = selected == i
                row_bg = "background:#1E3A5F;border-radius:5px;" if is_sel else ""

                rcols = st.columns([0.35, 0.7, 0.7, 0.8, 0.55, 0.4])
                with rcols[0]:
                    if st.button("▶", key=f"sel_wl_{i}", help=f"Select {row['talker_id']}"):
                        st.session_state["selected_workload_row"] = i
                        st.rerun()
                with rcols[1]:
                    st.markdown(
                        f'<span style="font-size:0.85rem;color:#FAFAFA;{row_bg}">{row["talker_id"]}</span>',
                        unsafe_allow_html=True,
                    )
                with rcols[2]:
                    st.markdown(
                        f'<span style="font-size:0.85rem;color:#FAFAFA;">{row["switch_id"]}</span>',
                        unsafe_allow_html=True,
                    )
                with rcols[3]:
                    st.markdown(
                        f'<span style="font-size:0.85rem;color:#FAFAFA;">{row["listener_id"]}</span>',
                        unsafe_allow_html=True,
                    )
                with rcols[4]:
                    st.markdown(
                        f'<span style="font-size:0.85rem;color:#FAFAFA;">{len(streams)}</span>',
                        unsafe_allow_html=True,
                    )
                with rcols[5]:
                    st.markdown(status_html, unsafe_allow_html=True)

        # ── right panel: stream editor ─────────────────────────────────────────
        with wl_right:
            if selected is None:
                st.markdown(
                    '<div style="padding:50px 16px;text-align:center;">'
                    '<p style="color:#4A5070;font-size:0.9rem;">Select a row on the left to configure its streams.</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                row = rows[selected]
                st.markdown(
                    f'<p style="color:#FAFAFA;font-weight:600;margin:0 0 0.75rem 0;">'
                    f'{row["talker_id"]} → {row["switch_id"]} → {row["listener_id"]}</p>',
                    unsafe_allow_html=True,
                )

                n_sw = int(st.session_state.get("num_switches", 1))
                n_li = int(st.session_state.get("num_listeners", 1))
                switch_options = [f"S{i+1}" for i in range(n_sw)]
                listener_options = [f"L{i+1}" for i in range(n_li)]

                info_c1, info_c2 = st.columns(2)
                with info_c1:
                    sw_idx = switch_options.index(row["switch_id"]) if row["switch_id"] in switch_options else 0
                    new_sw = st.selectbox("Switch", options=switch_options, index=sw_idx, key=f"sw_{selected}")
                    st.session_state["workload_rows"][selected]["switch_id"] = new_sw
                with info_c2:
                    li_idx = listener_options.index(row["listener_id"]) if row["listener_id"] in listener_options else 0
                    new_li = st.selectbox("Listener", options=listener_options, index=li_idx, key=f"li_{selected}")
                    st.session_state["workload_rows"][selected]["listener_id"] = new_li

                st.markdown(
                    '<p style="color:#7C85A2;font-size:0.8rem;font-weight:600;margin:0.75rem 0 4px 0;">STREAMS</p>',
                    unsafe_allow_html=True,
                )

                df = _ctrl.streams_to_df(row["streams"], link_datarate)
                num_tx_queues = int(st.session_state.get("num_tx_queues", 4))

                edited_df = st.data_editor(
                    df,
                    key=f"streams_ed_{selected}",
                    num_rows="dynamic",
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "stream_id": st.column_config.TextColumn("Stream ID", width="medium"),
                        "type": st.column_config.SelectboxColumn(
                            "Type", options=_STREAM_TYPES, width="small"
                        ),
                        "pcp": st.column_config.NumberColumn(
                            "PCP", min_value=0, max_value=7, step=1, width="small"
                        ),
                        "gate_id": st.column_config.NumberColumn(
                            "Gate ID", min_value=0, max_value=num_tx_queues - 1, step=1, width="small"
                        ),
                        "period_ns": st.column_config.NumberColumn(
                            "Period (ns)", min_value=1, width="medium"
                        ),
                        "packet_size_bytes": st.column_config.NumberColumn(
                            "Pkt Size (B)", min_value=1, max_value=9000, width="medium"
                        ),
                        "bandwidth_Mbps": st.column_config.NumberColumn(
                            "BW (Mbps)", disabled=True, format="%.3f", width="medium"
                        ),
                        "load_ratio": st.column_config.NumberColumn(
                            "Load Ratio", disabled=True, format="%.6f", width="medium"
                        ),
                    },
                )

                # Save edited streams back to session state
                new_streams = _ctrl.df_to_streams(edited_df)
                st.session_state["workload_rows"][selected]["streams"] = new_streams

                # Compute and display totals
                total_bw, total_lr = _ctrl.total_bandwidth(new_streams, link_datarate)

                st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)
                tot_c1, tot_c2 = st.columns(2)
                with tot_c1:
                    st.markdown(
                        f'<div style="background:#1A1E2E;border:1px solid #2D3250;border-radius:8px;padding:10px 14px;">'
                        f'<p style="color:#7C85A2;font-size:0.75rem;margin:0 0 2px 0;">Total Bandwidth</p>'
                        f'<p style="color:#FAFAFA;font-size:1.1rem;font-weight:600;margin:0;">'
                        f'{total_bw:.3f} <span style="color:#7C85A2;font-size:0.8rem;">Mbps</span></p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with tot_c2:
                    st.markdown(
                        f'<div style="background:#1A1E2E;border:1px solid #2D3250;border-radius:8px;padding:10px 14px;">'
                        f'<p style="color:#7C85A2;font-size:0.75rem;margin:0 0 2px 0;">Total Load Ratio</p>'
                        f'<p style="color:#FAFAFA;font-size:1.1rem;font-weight:600;margin:0;">'
                        f'{total_lr:.6f}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


# ── main render ────────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown(
        '<div class="page-header">'
        '<h1 class="page-title">Topology Manager</h1>'
        '<p class="page-subtitle">Visualise and manage your network topology</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1.3], gap="large")

    with left:
        with st.container(border=True):
            st.markdown(
                '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Network Topology</p>',
                unsafe_allow_html=True,
            )
            _persisted_text_input("Topology ID", "topology_id", "TsnIntelStar", disabled=True)
            _persisted_number_input("Number of switches", "num_switches", 1, min_value=1, disabled=True)
            _persisted_number_input("Number of talkers", "num_talkers", 1, min_value=1)
            _persisted_number_input("Number of listeners", "num_listeners", 1, min_value=1, max_value=3, step=1)
            _persisted_number_input("Link datarate (Mbps)", "link_datarate_Mbps", 1000, min_value=1)
            _persisted_text_input("Device model", "device_model", "intel_i226", disabled=True)
            _persisted_number_input("Number of TX queues", "num_tx_queues", 4, min_value=1, disabled=True)
            _persisted_selectbox(
                "Topology pattern", "topology_pattern", _TOPOLOGY_OPTIONS, _TOPOLOGY_OPTIONS[0], disabled=True
            )

            cyc_col, unit_col = st.columns([2, 1])
            with cyc_col:
                cycle_time = _persisted_number_input("Cycle time", "cycle_time", 1, min_value=1)
            with unit_col:
                cycle_unit = _persisted_selectbox("Unit", "cycle_unit", ["ms", "ns"], "ms")
            st.session_state["gcl_cycle_time_ns"] = (
                int(round(cycle_time * 1_000_000)) if cycle_unit == "ms" else int(round(cycle_time))
            )

            st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)
            if st.button("Load Network", type="primary", width='stretch'):
                st.session_state["topology_loaded"] = True
                # Reset workload so rows are regenerated for new topology
                st.session_state.pop("workload_rows", None)
                st.session_state["selected_workload_row"] = None
                st.session_state["edges"] = _ctrl.default_edges(
                    int(st.session_state.get("num_talkers", 1)),
                    int(st.session_state.get("num_listeners", 1)),
                )
                _ctrl.log_topology_loaded(
                    int(st.session_state.get("num_talkers", 1)),
                    int(st.session_state.get("num_switches", 1)),
                    int(st.session_state.get("num_listeners", 1)),
                )

    with right:
        _render_edges()
        _render_workload()

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Load from File</p>',
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Import topology + workload (JSON)", type=["json"], key="topology_json_upload"
        )

        runs_preview: list = []
        if uploaded_file is not None:
            try:
                content = _ctrl.read_json_upload(uploaded_file)
                runs_preview = _ctrl.extract_runs(content)
                if not runs_preview:
                    st.error("No topology/workload data found in file.")
            except ValueError:
                st.error("Invalid JSON file.")

        if len(runs_preview) > 1:
            labels = [
                f"[{i}] {r.get('config_id') or 'run'} (run_id={r.get('run_id', i)})"
                for i, r in enumerate(runs_preview)
            ]
            st.selectbox(
                "Select configuration",
                options=list(range(len(runs_preview))),
                format_func=lambda i: labels[i],
                key="topology_file_run_idx",
            )

        st.button(
            "Load from File",
            type="secondary",
            width='stretch',
            disabled=not runs_preview,
            on_click=_handle_load_from_file_click,
        )
        if st.session_state.get("topology_file_error"):
            st.error(st.session_state["topology_file_error"])

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            '<p class="card-title" style="margin:0 0 1rem 0;font-size:0.95rem;">Network Overview</p>',
            unsafe_allow_html=True,
        )
        if st.session_state.get("topology_loaded"):
            pattern = st.session_state.get("topology_pattern", _TOPOLOGY_OPTIONS[0])
            n_talk = int(st.session_state.get("num_talkers", 1))
            n_list = int(st.session_state.get("num_listeners", 1))
            if "single-switch star" in pattern:
                st.markdown(_star_svg(n_talk, n_list), unsafe_allow_html=True)
            else:
                st.info("Visualisation for this topology pattern is coming soon.")
        else:
            st.markdown(
                '<div class="empty-state" style="padding:60px 24px;">'
                '<div class="empty-state-icon">&#128279;</div>'
                '<p class="empty-state-desc">Configure the parameters on the left and click'
                " <strong>Load Network</strong> to visualise the topology.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
