# TSN dataset JSON format

This document describes the JSON schema used throughout the project for a single
**run**: `data_prep/JSON/*_datasets.json` files, files produced by the Topology
Manager's "Load from File" import, and the payload built by
[`ConfigController.build_run`](../../../controllers/config_controller.py).

A dataset file is a JSON list of run objects:

```json
[
  { "run_id": 1, "config_id": "...", "topology": { ... }, "workload": [ ... ], "gcl": [ ... ], "performance": [ ... ] },
  { "run_id": 2, "...": "..." }
]
```

Each run has up to four parts:

| Part | Role | Required for |
|---|---|---|
| `topology` | model **input** | training, inference, XML export |
| `workload` | model **input** | training, inference, XML export |
| `gcl` | model **output** / training label | training (label), app output |
| `performance` | **reward** / evaluation signal | dataset inspection, RL-style reward shaping (not consumed by the current GraphSAGE training loop) |

Top-level run fields, alongside the four parts above:

| Field | Type | Notes |
|---|---|---|
| `run_id` | int | Unique within a dataset file; used for de-duplication when merging files in the [Data Prep tool](../../../../data_prep/data_manager.py). |
| `config_id` | string | Human-readable label for the run/scenario, e.g. `"0701_TsnIntelStar_311_F70_G200"`. |

---

## 1. `topology` (input)

Describes the network graph: nodes, links, and hardware parameters. Built from
the Topology Manager form fields (see
[`topology_view.py`](../../../views/topology_manager/topology_view.py))
and consumed by [`graph_builder.build_graph`](../../inferenceService/graph_builder.py)
and [`ConfigController.gcl_to_xml`](../../../controllers/config_controller.py).

```json
{
  "topology_id": "TsnIntelStar",
  "num_talkers": 3,
  "num_switches": 1,
  "num_listeners": 1,
  "link_datarate_Mbps": 1000,
  "device_model": "intel_i226",
  "num_tx_queues": 4,
  "gcl_cycle_time_ns": 1000000,
  "edges": [
    { "from": "T1", "to": "S1" },
    { "from": "T2", "to": "S1" },
    { "from": "T3", "to": "S1" },
    { "from": "S1", "to": "L1", "port_id": "S1P1" }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `topology_id` | string | Topology shape identifier. Currently only `"TsnIntelStar"` (single-switch star: every talker → S1 → every listener) is supported end-to-end. |
| `num_talkers` | int | Number of talker nodes, named `T1..Tn`. |
| `num_switches` | int | Number of switch nodes, named `S1..Sm`. Only `1` is exercised by the current graph builder / model. |
| `num_listeners` | int | Number of listener nodes, named `L1..Lk`. |
| `link_datarate_Mbps` | number | Link bandwidth, used to derive `bandwidth_Mbps`/`load_ratio` for streams and normalise the `link_dr_norm` node feature. |
| `device_model` | string | NIC/hardware model, e.g. `"intel_i226"`. Informational; not consumed by the model. |
| `num_tx_queues` | int | Number of hardware TX queues / gates per egress port. The model always predicts 4 gate-duration fractions (`_GATE_BITMASKS` in `gnn_model.py`), so this is expected to be `4`. |
| `gcl_cycle_time_ns` | int | GCL schedule cycle length in nanoseconds. Used to normalise/denormalise gate durations and as the `admin-cycle-time` numerator in XML export. |
| `edges` | list of `{from, to, port_id?}` | Directed links between node IDs (`T*`, `S*`, `L*`). A switch→listener edge may carry `port_id` (e.g. `"S1P1"`), which becomes the node name used for that switch's egress schedule in `gcl` and in the trained graph. If omitted, `port_id` defaults to `"<switch_id>P1"`. |

---

## 2. `workload` (input)

One entry per talker, describing the traffic streams it originates. Built from
the Topology Manager's workload editor and consumed by `graph_builder.build_graph`
and `ConfigController.build_run`/`gcl_to_xml`.

```json
[
  {
    "talker_id": "T1",
    "switch_id": "S1",
    "listener_id": "L1",
    "num_streams": 2,
    "streams": [
      {
        "stream_id": "T1STR_01",
        "type": "TT7",
        "pcp": 7,
        "gate_id": 3,
        "period_ns": 100000,
        "packet_size_bytes": 1000,
        "bandwidth_Mbps": 80.0,
        "load_ratio": 0.08
      },
      {
        "stream_id": "T1STR_02",
        "type": "BE",
        "pcp": 0,
        "gate_id": 0,
        "period_ns": 200000,
        "packet_size_bytes": 1500,
        "bandwidth_Mbps": 60.0,
        "load_ratio": 0.06
      }
    ],
    "total_bandwidth_Mbps": 140.0,
    "total_load_ratio": 0.14
  }
]
```

| Field | Type | Notes |
|---|---|---|
| `talker_id` | string | Must match a `T*` node in `topology.edges`. |
| `switch_id` | string | Egress switch for this talker's traffic (currently always `"S1"`). |
| `listener_id` | string | Destination listener (currently always `"L1"`, single-listener scenarios). |
| `num_streams` | int | `len(streams)`, precomputed for convenience by `ConfigController.build_run`. |
| `total_bandwidth_Mbps`, `total_load_ratio` | number | Sums of the per-stream values below, precomputed by `ConfigController.build_run`. |
| `streams` | list | See below. |

Each entry in `streams`:

| Field | Type | Notes |
|---|---|---|
| `stream_id` | string | Free-form identifier, e.g. `"T1STR_01"`. |
| `type` | string | One of `TT7`, `TT6`, `TT5` (scheduled traffic classes, highest→lowest priority) or `BE`/`AVB` (best-effort / audio-video bridging). Only `TT7` and `BE` currently feed distinct node features in `graph_builder.py`; `TT6`/`TT5` are aggregated into `total_load` only. |
| `pcp` | int (0–7) | 802.1Q Priority Code Point. |
| `gate_id` | int (0 to `num_tx_queues - 1`) | Which of the 4 hardware gates this stream is queued behind. |
| `period_ns` | int | Stream period in nanoseconds (must be > 0). |
| `packet_size_bytes` | int (1–9000) | Packet size in bytes (must be > 0). |
| `bandwidth_Mbps` | number | Derived: `packet_size_bytes * 8 / (period_ns * 1e-9) / 1e6`. |
| `load_ratio` | number | Derived: `bandwidth_Mbps / link_datarate_Mbps`. |

---

## 3. `gcl` (output / training label)

The Gate Control List schedule: for each scheduled node (every talker, plus
each switch egress port), the sequence of gate-open windows within one cycle.
This is the model's **prediction target** — `gnn_model.predict()` produces this
shape at inference time, and it is the label (`y`) that `graph_builder.build_graph`
extracts for training.

```json
[
  {
    "parent_id": "T1",
    "gcl_sequences": [
      { "sequence_index": 0, "gate_bitmask": "0001", "duration_ns": 200000 },
      { "sequence_index": 1, "gate_bitmask": "1000", "duration_ns": 800000 }
    ]
  },
  {
    "parent_id": "S1P1",
    "gcl_sequences": [
      { "sequence_index": 0, "gate_bitmask": "0001", "duration_ns": 200000 },
      { "sequence_index": 1, "gate_bitmask": "1000", "duration_ns": 800000 }
    ]
  }
]
```

| Field | Type | Notes |
|---|---|---|
| `parent_id` | string | The scheduled node: `T1..Tn` for talkers, or the switch's egress `port_id` (e.g. `"S1P1"`) for switches. Listener nodes are never scheduled. |
| `gcl_sequences` | list | Ordered list of gate-open windows making up one full cycle. |

Each entry in `gcl_sequences`:

| Field | Type | Notes |
|---|---|---|
| `sequence_index` | int | 0-based position within the cycle (assigned in emission order by `ConfigController.generate`). |
| `gate_bitmask` | string | 4-character binary string `"ABCD"`, one bit per hardware gate (`A`=gate0 … `D`=gate3); `'1'` = open during this window. Exactly one bit is set per window in the current model (`_GATE_BITMASKS = ["1000","0100","0010","0001"]`). |
| `duration_ns` | int | Window length in nanoseconds; must be `> 0`. Durations for a node should sum to within 5% of `topology.gcl_cycle_time_ns` (checked by `ConfigController.validate_gcl`). |

Snapping rule used by the model when generating durations: predicted fractions
are rounded to the nearest `50,000 ns` (`_SNAP_GRANULARITY`), and every window is
floored at the largest single-packet transmission time in the run, so the gate
always stays open long enough to send at least one packet.

---

## 4. `performance` (reward / evaluation)

Per-listener, per-gate measured performance from the network simulation that
produced this run — the ground-truth signal for how "good" the paired
`(topology, workload, gcl)` combination actually was. Not consumed by the
current supervised training loop (`gnn_model.train`), but used by the
[Data Prep tool](../../../../data_prep/data_manager.py) for dataset inspection/charting,
and is the natural source of a reward signal for reward-shaped or RL-based
extensions of training.

```json
[
  {
    "listener_id": "L1",
    "port_id": "S1P1",
    "metrics": [
      {
        "gate_id": 0,
        "pkts_sent": 1503,
        "pkts_received": 1500,
        "pkts_loss_count": 3,
        "delay_max_us": 238.93,
        "delay_stddev_us": 73.2034,
        "delay_mean_us": 93.4202,
        "deadline_ns": 500000,
        "deadline_miss_ratio": 0.001996,
        "throughput_Mbps": 180.0,
        "queue_max_length": 10
      }
    ]
  }
]
```

| Field | Type | Notes |
|---|---|---|
| `listener_id` | string | Destination listener these metrics were measured at. |
| `port_id` | string | Switch egress port feeding this listener (matches a `gcl[].parent_id`). |
| `metrics` | list | One entry per hardware gate (0 to `num_tx_queues - 1`), including gates with no traffic (all-zero entry). |

Each entry in `metrics`:

| Field | Type | Notes |
|---|---|---|
| `gate_id` | int | Hardware gate index (0–3). |
| `pkts_sent` | int | Packets transmitted on this gate during the run. |
| `pkts_received` | int | Packets successfully received. |
| `pkts_loss_count` | int | `pkts_sent - pkts_received` (packets lost/dropped). |
| `delay_max_us` | number | Maximum end-to-end delay observed, in microseconds. |
| `delay_mean_us` | number | Mean end-to-end delay, in microseconds. |
| `delay_stddev_us` | number | Standard deviation of end-to-end delay, in microseconds. |
| `deadline_ns` | int | Deadline budget for this gate/traffic class, in nanoseconds. |
| `deadline_miss_ratio` | number (0–1) | Fraction of packets that missed `deadline_ns`. |
| `throughput_Mbps` | number | Achieved throughput on this gate. |
| `queue_max_length` | int | Maximum observed queue depth (packets) for this gate. |

`data_manager.py` aggregates `metrics` entries with `pkts_sent > 0` ("active"
gates) across all listeners/ports of a run to compute the summary columns shown
in its dataset table (`pkts_sent`, `pkts_received`, `pkts_loss`, mean/max delay,
mean deadline-miss ratio, total throughput).
