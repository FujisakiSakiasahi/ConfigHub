"""Default-value generators for topology edges and workload rows."""


def default_edges(n_talkers: int, n_listeners: int) -> list:
    """Single-switch star wiring: every talker feeds S1, S1 egresses to each listener."""
    edges = [{"from": f"T{i + 1}", "to": "S1"} for i in range(n_talkers)]
    edges += [
        {"from": "S1", "to": f"L{j + 1}", "port_id": f"S1P{j + 1}"}
        for j in range(n_listeners)
    ]
    return edges


def default_workload_rows(num_talkers: int) -> list:
    return [
        {"talker_id": f"T{t + 1}", "switch_id": "S1", "listener_id": "L1", "streams": []}
        for t in range(num_talkers)
    ]
