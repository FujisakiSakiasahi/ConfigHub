import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

JSON_DIR = Path(__file__).parent / "JSON"

st.set_page_config(page_title="Dataset Manager", layout="wide")
st.title("TSN Dataset Manager")

# ── helpers ──────────────────────────────────────────────────────────────────

def list_json_files():
    if not JSON_DIR.exists():
        return []
    return sorted(f.name for f in JSON_DIR.glob("*.json"))


def load_json(filename: str) -> list[dict]:
    with open(JSON_DIR / filename, "r") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def flatten_runs(runs: list[dict]) -> pd.DataFrame:
    rows = []
    for run in runs:
        topo = run.get("topology", {})
        workload = run.get("workload", [])
        perf = run.get("performance", [])

        total_streams = sum(w.get("num_streams", 0) for w in workload)
        total_bw = sum(w.get("total_bandwidth_Mbps", 0) for w in workload)

        all_metrics = [m for p in perf for m in p.get("metrics", [])]
        active = [m for m in all_metrics if m.get("pkts_sent", 0) > 0]

        rows.append({
            "run_id": run.get("run_id"),
            "topology_id": topo.get("topology_id"),
            "num_talkers": topo.get("num_talkers"),
            "num_switches": topo.get("num_switches"),
            "num_listeners": topo.get("num_listeners"),
            "link_datarate_Mbps": topo.get("link_datarate_Mbps"),
            "device_model": topo.get("device_model"),
            "num_tx_queues": topo.get("num_tx_queues"),
            "gcl_cycle_time_ns": topo.get("gcl_cycle_time_ns"),
            "total_streams": total_streams,
            "total_bandwidth_Mbps": round(total_bw, 2),
            "pkts_sent": sum(m.get("pkts_sent", 0) for m in active),
            "pkts_received": sum(m.get("pkts_received", 0) for m in active),
            "pkts_loss": sum(m.get("pkts_loss_count", 0) for m in active),
            "delay_mean_us": round(
                sum(m.get("delay_mean_us", 0) for m in active) / len(active), 4
            ) if active else 0,
            "delay_max_us": max((m.get("delay_max_us", 0) for m in active), default=0),
            "deadline_miss_ratio": round(
                sum(m.get("deadline_miss_ratio", 0) for m in active) / len(active), 6
            ) if active else 0,
            "throughput_Mbps": round(
                sum(m.get("throughput_Mbps", 0) for m in active), 2
            ),
        })
    return pd.DataFrame(rows)


def show_dataset(runs: list[dict], label: str):
    if not runs:
        st.info(f"No data in {label}.")
        return

    df = flatten_runs(runs)
    st.subheader(f"{label} — {len(runs)} run(s)")

    tab_table, tab_perf, tab_bw = st.tabs(["Table", "Performance", "Bandwidth"])

    with tab_table:
        st.dataframe(df, width='stretch', hide_index=True)

    with tab_perf:
        if len(df) > 1:
            st.line_chart(df.set_index("run_id")[["delay_mean_us", "delay_max_us"]])
            st.line_chart(df.set_index("run_id")[["deadline_miss_ratio"]])
        else:
            st.bar_chart(
                df[["delay_mean_us", "delay_max_us", "throughput_Mbps"]].T.rename(
                    columns={0: "value"}
                )
            )

    with tab_bw:
        st.bar_chart(df.set_index("run_id")[["total_bandwidth_Mbps", "throughput_Mbps"]])


def get_next_master_name(total_runs: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"master_{ts}_{total_runs}.json"


# ── sidebar: file selection ───────────────────────────────────────────────────

with st.sidebar:
    st.header("File Selection")
    json_files = list_json_files()

    if not json_files:
        st.error(f"No JSON files found in:\n{JSON_DIR}")
        st.stop()

    master_files = [f for f in json_files if f.startswith("master_")]
    new_files = [f for f in json_files if not f.startswith("master_")]

    if not master_files:
        st.warning("No master JSON files found (names must start with `master_`).")
    if not new_files:
        st.warning("No new-rows JSON files found (non-master files).")

    master_file = st.selectbox("Master JSON file", options=master_files or json_files, key="master")
    new_file = st.selectbox("New rows JSON file", options=new_files or json_files, key="new")
    load_btn = st.button("Load files", type="primary", width='stretch')

# ── state ─────────────────────────────────────────────────────────────────────

if "master_runs" not in st.session_state:
    st.session_state.master_runs = None
if "new_runs" not in st.session_state:
    st.session_state.new_runs = None
if "last_master" not in st.session_state:
    st.session_state.last_master = None
if "last_new" not in st.session_state:
    st.session_state.last_new = None

if load_btn or (
    st.session_state.last_master != master_file
    or st.session_state.last_new != new_file
):
    st.session_state.master_runs = load_json(master_file)
    st.session_state.new_runs = load_json(new_file)
    st.session_state.last_master = master_file
    st.session_state.last_new = new_file

# ── main content ──────────────────────────────────────────────────────────────

if st.session_state.master_runs is None:
    st.info("Select files in the sidebar and click **Load files** to begin.")
    st.stop()

col_left, col_right = st.columns(2)

with col_left:
    show_dataset(st.session_state.master_runs, f"Master  ·  {master_file}")

with col_right:
    show_dataset(st.session_state.new_runs, f"New rows  ·  {new_file}")

st.divider()

# ── merge & save ──────────────────────────────────────────────────────────────

st.subheader("Merge & Save")

master_ids = {r.get("run_id") for r in st.session_state.master_runs}
new_ids = {r.get("run_id") for r in st.session_state.new_runs}
overlap = master_ids & new_ids

if overlap:
    st.warning(
        f"The following run_ids exist in both files and will be **skipped** during merge: {sorted(overlap)}"
    )

unique_new = [r for r in st.session_state.new_runs if r.get("run_id") not in master_ids]
merged = st.session_state.master_runs + unique_new
total_runs = len(merged)

st.write(
    f"Master: **{len(st.session_state.master_runs)}** run(s) · "
    f"New (unique): **{len(unique_new)}** run(s) · "
    f"Merged total: **{total_runs}** run(s)"
)

if st.button("Merge and save new master", type="primary", disabled=len(unique_new) == 0):
    out_name = get_next_master_name(total_runs)
    out_path = JSON_DIR / out_name
    with open(out_path, "w") as fh:
        json.dump(merged, fh, indent=2)
    st.success(f"Saved **{out_name}** ({total_runs} runs) to `{JSON_DIR}`")
    st.balloons()

if len(unique_new) == 0 and not overlap:
    st.info("New file has no runs to add.")
elif len(unique_new) == 0 and overlap:
    st.info("All runs in the new file already exist in the master (by run_id).")
