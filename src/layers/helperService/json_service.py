"""JSON parsing / normalisation helpers for imported topology + workload files."""

from src.layers.helperService import topology_defaults


def extract_runs(content) -> list:
    """Normalise uploaded JSON content into a list of run dicts with topology/workload."""
    raw = content if isinstance(content, list) else [content]
    return [r for r in raw if isinstance(r, dict) and ("topology" in r or "workload" in r)]


def normalize_topology_payload(data: dict, allowed_patterns: list) -> dict:
    """Map a raw {"topology": ..., "workload": ...} run dict into flat session-state fields."""
    topo = data.get("topology", {}) or {}
    workload = data.get("workload", []) or []

    result = {
        "topology_id": topo.get("topology_id", "TsnIntelStar"),
        "num_switches": int(topo.get("num_switches", 1)),
        "num_talkers": int(topo.get("num_talkers", 1)),
        "num_listeners": int(topo.get("num_listeners", 1)),
        "link_datarate_Mbps": int(topo.get("link_datarate_Mbps", 1000)),
        "device_model": topo.get("device_model", "intel_i226"),
        "num_tx_queues": int(topo.get("num_tx_queues", 4)),
    }

    cycle_ns = int(topo.get("gcl_cycle_time_ns", 1_000_000))
    if cycle_ns > 0 and cycle_ns % 1_000_000 == 0:
        result["cycle_time"] = cycle_ns // 1_000_000
        result["cycle_unit"] = "ms"
    else:
        result["cycle_time"] = cycle_ns
        result["cycle_unit"] = "ns"
    result["gcl_cycle_time_ns"] = cycle_ns

    pattern = topo.get("topology_pattern")
    if pattern in allowed_patterns:
        result["topology_pattern"] = pattern

    result["edges"] = topo.get("edges") or topology_defaults.default_edges(
        result["num_talkers"], result["num_listeners"]
    )

    rows = []
    for w in workload:
        rows.append({
            "talker_id": w.get("talker_id", ""),
            "switch_id": w.get("switch_id", "S1"),
            "listener_id": w.get("listener_id", "L1"),
            "streams": [
                {
                    "stream_id": s.get("stream_id", ""),
                    "type": s.get("type", "TT7"),
                    "pcp": int(s.get("pcp", 7)),
                    "gate_id": int(s.get("gate_id", 0)),
                    "period_ns": int(s.get("period_ns", 250000)),
                    "packet_size_bytes": int(s.get("packet_size_bytes", 1500)),
                }
                for s in w.get("streams", []) or []
            ],
        })
    result["workload_rows"] = rows

    return result
