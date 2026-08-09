"""Conversions between domain data (lists of dicts) and pandas DataFrames."""

import pandas as pd

from src.layers.helperService import calculations


def streams_to_df(streams: list, link_datarate: float) -> pd.DataFrame:
    rows = []
    for s in streams:
        pkt = s.get("packet_size_bytes", 1500)
        per = s.get("period_ns", 250000)
        bw, lr = calculations.calc_bandwidth(pkt, per, link_datarate)
        rows.append({
            "stream_id": s.get("stream_id", ""),
            "type": s.get("type", "TT7"),
            "pcp": int(s.get("pcp", 7)),
            "gate_id": int(s.get("gate_id", 0)),
            "period_ns": int(per),
            "packet_size_bytes": int(pkt),
            "bandwidth_Mbps": bw,
            "load_ratio": lr,
        })
    if not rows:
        return pd.DataFrame(columns=[
            "stream_id", "type", "pcp", "gate_id", "period_ns",
            "packet_size_bytes", "bandwidth_Mbps", "load_ratio",
        ])
    return pd.DataFrame(rows)


def df_to_streams(df: pd.DataFrame) -> list:
    out = []
    for _, r in df.iterrows():
        stream_id = str(r.get("stream_id", "") or "").strip()
        try:
            pcp = int(r["pcp"]) if pd.notna(r["pcp"]) else 0
        except Exception:
            pcp = 0
        try:
            gate_id = int(r["gate_id"]) if pd.notna(r.get("gate_id")) else 0
        except Exception:
            gate_id = 0
        try:
            period_ns = int(r["period_ns"]) if pd.notna(r["period_ns"]) and r["period_ns"] > 0 else 250000
        except Exception:
            period_ns = 250000
        try:
            pkt = int(r["packet_size_bytes"]) if pd.notna(r["packet_size_bytes"]) and r["packet_size_bytes"] > 0 else 1500
        except Exception:
            pkt = 1500
        stream_type = str(r.get("type", "TT7") or "TT7")
        out.append({
            "stream_id": stream_id,
            "type": stream_type,
            "pcp": pcp,
            "gate_id": gate_id,
            "period_ns": period_ns,
            "packet_size_bytes": pkt,
        })
    return out


def edges_to_df(edges: list) -> pd.DataFrame:
    rows = [
        {"from": e.get("from", ""), "to": e.get("to", ""), "port_id": e.get("port_id", "") or ""}
        for e in edges
    ]
    if not rows:
        return pd.DataFrame(columns=["from", "to", "port_id"])
    return pd.DataFrame(rows)


def df_to_edges(df: pd.DataFrame) -> list:
    out = []
    for _, r in df.iterrows():
        frm = str(r.get("from", "") or "").strip()
        to = str(r.get("to", "") or "").strip()
        if not frm or not to:
            continue
        edge = {"from": frm, "to": to}
        port_id = str(r.get("port_id", "") or "").strip()
        if port_id:
            edge["port_id"] = port_id
        out.append(edge)
    return out


def models_to_df(models: list) -> pd.DataFrame:
    rows = [
        {
            "model_id": m.get("model_id", ""),
            "name": m.get("name", ""),
            "version": m.get("version", ""),
            "description": m.get("description", ""),
        }
        for m in models
    ]
    return pd.DataFrame(rows, columns=["model_id", "name", "version", "description"])


def gcl_to_df(gcl: list) -> pd.DataFrame:
    rows = []
    for entry in gcl:
        for seq in entry["gcl_sequences"]:
            rows.append({
                "parent_id": entry["parent_id"],
                "sequence_index": seq["sequence_index"],
                "gate_bitmask": seq["gate_bitmask"],
                "duration_ns": seq["duration_ns"],
            })
    return pd.DataFrame(rows, columns=["parent_id", "sequence_index", "gate_bitmask", "duration_ns"])
