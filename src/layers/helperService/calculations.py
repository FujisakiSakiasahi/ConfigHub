"""Bandwidth / load-ratio calculations for topology & workload streams."""


def calc_bandwidth(packet_size_bytes, period_ns, link_datarate_Mbps: float) -> tuple[float, float]:
    """Return (bandwidth_Mbps, load_ratio) for a single periodic stream."""
    try:
        pkt = float(packet_size_bytes)
        per = float(period_ns)
        if per <= 0 or pkt <= 0:
            return 0.0, 0.0
        bw = (pkt * 8) / (per * 1e-9) / 1e6
        lr = bw / link_datarate_Mbps if link_datarate_Mbps > 0 else 0.0
        return round(bw, 3), round(lr, 6)
    except Exception:
        return 0.0, 0.0


def total_bandwidth(streams: list, link_datarate_Mbps: float) -> tuple[float, float]:
    """Return (total_bandwidth_Mbps, total_load_ratio) across a list of streams."""
    total_bw = sum(
        calc_bandwidth(s["packet_size_bytes"], s["period_ns"], link_datarate_Mbps)[0]
        for s in streams
    )
    total_lr = sum(
        calc_bandwidth(s["packet_size_bytes"], s["period_ns"], link_datarate_Mbps)[1]
        for s in streams
    )
    return total_bw, total_lr
