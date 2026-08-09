"""
graph_builder.py
Converts one TSN simulation run (from datasets.json) into a
torch_geometric.data.Data object ready for GNN training / inference.

Note: torch-scatter / torch-sparse are optional PyG extensions.
      torch-geometric 2.x works without them for the operations used here.

Node ordering (deterministic):
    talkers (T1, T2, …, Tn)  →  switches (S1, …, Sm)  →  listeners (L1, …, Lk)

Feature vector per node (14 floats):
    [total_load_ratio, tt7_load, tt6_load, tt5_load, be_load,
     tt7_period_ns_norm, tt7_pkt_bytes_norm, tt6_period_ns_norm, tt6_pkt_bytes_norm,
     tt5_period_ns_norm, tt5_pkt_bytes_norm, be_period_ns_norm,
     link_datarate_norm, num_tx_queues_norm]

Label vector per node (4 floats, normalised by gcl_cycle_time_ns):
    [dur_gate0, dur_gate1, dur_gate2, dur_gate3]
    Listener nodes → [0, 0, 0, 0]  (no GCL)

Graph-level attribute:
    gcl_cycle_time_ns  — raw cycle time (int), used to denormalise predictions
"""

import json
import sys

import torch
from torch_geometric.data import Data


# ─── internal helpers ─────────────────────────────────────────────────────────

def _stream_features(
    streams_by_type: dict,
    cycle_ns: float,
    link_dr_norm: float,
    num_q_norm: float,
) -> list:
    """
    Build the 14-element feature vector for a node.

    streams_by_type maps stream-type string → stream dict, e.g.
        {'TT7': {'period_ns': 100000, 'packet_size_bytes': 1000,
                 'load_ratio': 0.08, ...},
         'BE':  {...}}
    For the switch node the load values are pre-summed across talkers.
    """
    tt7 = streams_by_type.get('TT7')
    tt6 = streams_by_type.get('TT6')
    tt5 = streams_by_type.get('TT5')
    be  = streams_by_type.get('BE')

    total_load      = sum(s['load_ratio'] for s in streams_by_type.values())
    tt7_load        = tt7['load_ratio']           if tt7 else 0.0
    tt6_load        = tt6['load_ratio']           if tt6 else 0.0
    tt5_load        = tt5['load_ratio']           if tt5 else 0.0
    be_load         = be['load_ratio']            if be  else 0.0
    tt7_period_norm = tt7['period_ns'] / cycle_ns if tt7 else 0.0
    tt7_pkt_norm    = tt7['packet_size_bytes'] / 1500.0 if tt7 else 0.0
    tt6_period_norm = tt6['period_ns'] / cycle_ns if tt6 else 0.0
    tt6_pkt_norm    = tt6['packet_size_bytes'] / 1500.0 if tt6 else 0.0
    tt5_period_norm = tt5['period_ns'] / cycle_ns if tt5 else 0.0
    tt5_pkt_norm    = tt5['packet_size_bytes'] / 1500.0 if tt5 else 0.0
    be_period_norm  = be['period_ns'] / cycle_ns  if be  else 0.0

    return [
        total_load, tt7_load, tt6_load, tt5_load, be_load,
        tt7_period_norm, tt7_pkt_norm, tt6_period_norm, tt6_pkt_norm,
        tt5_period_norm, tt5_pkt_norm, be_period_norm,
        link_dr_norm, num_q_norm,
    ]


def _gcl_durations_norm(gcl_sequences: list, cycle_ns: float) -> list:
    """
    Sum open-window durations per gate from a list of GCL sequences.

    gate_bitmask encoding: 'ABCD' where A=gate0, B=gate1, C=gate2, D=gate3.
    A character value of '1' means the gate is open during that interval.

    Returns [dur_gate0, dur_gate1, dur_gate2, dur_gate3] / cycle_ns.
    """
    durations = [0.0, 0.0, 0.0, 0.0]
    for seq in gcl_sequences:
        bitmask = seq['gate_bitmask']   # e.g. "0001" → only gate3 open
        dur     = seq['duration_ns']
        for gate_idx in range(4):
            if bitmask[gate_idx] == '1':
                durations[gate_idx] += dur
    return [d / cycle_ns for d in durations]


# ─── public API ───────────────────────────────────────────────────────────────

def build_graph(run: dict) -> Data:
    """
    Convert one run dict into a torch_geometric Data object.

    Parameters
    ----------
    run : dict
        A single element from a datasets.json list.

    Returns
    -------
    torch_geometric.data.Data with attributes:
        x               FloatTensor  [num_nodes, 14]
        edge_index      LongTensor   [2, num_edges*2]  (bidirectional)
        y               FloatTensor  [num_nodes, 4]
        node_type       LongTensor   [num_nodes]  0=talker 1=switch 2=listener
        gcl_cycle_time_ns  int
    """
    topo     = run['topology']
    cycle_ns = topo['gcl_cycle_time_ns']
    link_dr_norm = topo['link_datarate_Mbps'] / 1000.0
    num_q_norm   = topo['num_tx_queues'] / 8.0

    # ── 1. Deterministic node list ────────────────────────────────────────────
    nt = topo['num_talkers']
    ns = topo['num_switches']
    nl = topo['num_listeners']

    talker_ids   = [f'T{i+1}' for i in range(nt)]
    switch_ids   = [f'S{i+1}' for i in range(ns)]
    listener_ids = [f'L{i+1}' for i in range(nl)]
    all_nodes    = talker_ids + switch_ids + listener_ids
    node_to_idx  = {name: idx for idx, name in enumerate(all_nodes)}

    # ── 2. Workload lookup: talker_id → {stream_type: stream_dict} ───────────
    workload_by_talker: dict[str, dict] = {}
    for entry in run['workload']:
        tid = entry['talker_id']
        workload_by_talker[tid] = {s['type']: s for s in entry['streams']}

    # ── 3. Node features ──────────────────────────────────────────────────────
    node_features: list[list] = []

    # Talkers — own workload only
    for tid in talker_ids:
        node_features.append(
            _stream_features(
                workload_by_talker[tid], cycle_ns, link_dr_norm, num_q_norm
            )
        )

    # Switch(es) — aggregate loads across all talkers;
    # period / packet-size are taken from the first talker that has each type
    # (they are identical across talkers for a given stream class).
    agg: dict[str, dict] = {}
    for tid in talker_ids:
        for stype, s in workload_by_talker[tid].items():
            if stype not in agg:
                agg[stype] = {**s, 'load_ratio': 0.0}   # copy period/pkt once
            agg[stype]['load_ratio'] += s['load_ratio']  # accumulate load

    for _ in switch_ids:
        node_features.append(
            _stream_features(agg, cycle_ns, link_dr_norm, num_q_norm)
        )

    # Listener(s) — zero stream features, keep link / queue norms
    for _ in listener_ids:
        node_features.append([0.0] * 12 + [link_dr_norm, num_q_norm])

    # ── 4. GCL label lookup: parent_id → [dur_g0, dur_g1, dur_g2, dur_g3] ───
    gcl_lookup: dict[str, list] = {}
    for entry in run['gcl']:
        gcl_lookup[entry['parent_id']] = _gcl_durations_norm(
            entry['gcl_sequences'], cycle_ns
        )

    labels: list[list] = []

    for tid in talker_ids:
        labels.append(gcl_lookup.get(tid, [0.0, 0.0, 0.0, 0.0]))

    # Switch output port: derive port_id from topology edges (e.g. S1 → S1P1)
    # Build a map from switch_id → its egress port_id on the listener side.
    switch_port: dict[str, str] = {}
    for edge in topo['edges']:
        if 'port_id' in edge and edge['from'] in switch_ids:
            # record one port per switch (current scope: one port per switch)
            switch_port.setdefault(edge['from'], edge['port_id'])

    for sid in switch_ids:
        port_id = switch_port.get(sid, f'{sid}P1')   # fallback: S1P1
        labels.append(gcl_lookup.get(port_id, [0.0, 0.0, 0.0, 0.0]))

    for _ in listener_ids:
        labels.append([0.0, 0.0, 0.0, 0.0])

    # ── 5. Bidirectional edge index ───────────────────────────────────────────
    src_list: list[int] = []
    dst_list: list[int] = []
    for edge in topo['edges']:
        s = node_to_idx[edge['from']]
        d = node_to_idx[edge['to']]
        src_list += [s, d]   # forward edge + reverse edge
        dst_list += [d, s]

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)

    # ── 6. Assemble Data object ───────────────────────────────────────────────
    x         = torch.tensor(node_features, dtype=torch.float)
    y         = torch.tensor(labels,        dtype=torch.float)
    node_type = torch.tensor(
        [0] * nt + [1] * ns + [2] * nl, dtype=torch.long
    )

    data = Data(x=x, edge_index=edge_index, y=y)
    data.node_type         = node_type
    data.gcl_cycle_time_ns = cycle_ns   # raw int, for denormalising outputs

    return data


# ─── test block ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python graph_builder.py <path/to/datasets.json>')
        sys.exit(1)

    with open(sys.argv[1], 'r') as fh:
        dataset = json.load(fh)

    run  = dataset[0]
    data = build_graph(run)

    topo = run['topology']
    nt, ns, nl = topo['num_talkers'], topo['num_switches'], topo['num_listeners']
    node_names = (
        [f'T{i+1}' for i in range(nt)] +
        [f'S{i+1}' for i in range(ns)] +
        [f'L{i+1}' for i in range(nl)]
    )
    type_label = {0: 'talker', 1: 'switch', 2: 'listener'}
    feat_names = [
        'total_load', 'tt7_load', 'tt6_load', 'tt5_load', 'be_load',
        'tt7_period_norm', 'tt7_pkt_norm', 'tt6_period_norm', 'tt6_pkt_norm',
        'tt5_period_norm', 'tt5_pkt_norm', 'be_period_norm',
        'link_dr_norm', 'num_q_norm',
    ]

    print(f"\n=== Graph for run_id={run['run_id']} "
          f"({run.get('config_id', '')}) ===")
    print(f"gcl_cycle_time_ns : {data.gcl_cycle_time_ns}")
    print(f"x shape           : {list(data.x.shape)}")
    print(f"y shape           : {list(data.y.shape)}")
    print(f"edge_index shape  : {list(data.edge_index.shape)}")

    print('\n--- Node Features ---')
    for i, name in enumerate(node_names):
        ntype = type_label[data.node_type[i].item()]
        feats = data.x[i].tolist()
        pairs = ', '.join(f'{n}={v:.4f}' for n, v in zip(feat_names, feats))
        print(f'  [{i}] {name:3s} ({ntype:8s}): {pairs}')

    print('\n--- Edge Index ---')
    src = data.edge_index[0].tolist()
    dst = data.edge_index[1].tolist()
    for s, d in zip(src, dst):
        print(f'  {node_names[s]}({s}) -> {node_names[d]}({d})')

    print('\n--- Labels (normalised GCL durations) ---')
    gate_names = ['gate0', 'gate1', 'gate2', 'gate3']
    for i, name in enumerate(node_names):
        lbl = data.y[i].tolist()
        pairs = ', '.join(f'{g}={v:.4f}' for g, v in zip(gate_names, lbl))
        print(f'  [{i}] {name:3s}: {pairs}')
