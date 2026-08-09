# ConfigHub — Consistency & Completeness Audit

Scope: entire repository (`app.py`, `src/`, `data_prep/`, docs, `.streamlit/`). No code was changed; every finding below was verified by reading the relevant files and, where noted, by actually executing read-only checks (loading checkpoint tensors, scanning JSON datasets) against the live repo contents.

Legend: **file:line** references are 1-indexed.

---

## Blocker

### B1. 5 of 6 shipped model checkpoints crash on load with the current model architecture

`GraphSAGENet.__init__` ([gnn_model.py:68](src/layers/inferenceService/gnn_model.py#L68)) hard-codes `in_channels=14, hidden_channels=128`, and both `train()` and `predict()` instantiate it with no way to override `hidden_channels` (no CLI flag exists for it either — see S1 below). `predict()` ([gnn_model.py:268-269](src/layers/inferenceService/gnn_model.py#L268-L269)) does a strict `model.load_state_dict(torch.load(MODEL_PATH))`.

I loaded every checkpoint under `src/layers/inferenceService/models/` and compared tensor shapes against this architecture:

| Checkpoint | Actual shape (in→hidden) | Loads with current code? |
|---|---|---|
| `proto311-100.pt` | 10 → 64 | **Fails** (size mismatch on both dims) |
| `protoN11-4k.pt` | 14 → 64 | **Fails** (hidden-dim mismatch) |
| `protoN11-8k-lr1e.pt` | 14 → 64 | **Fails** |
| `protoN11-8k-lr3e.pt` | 14 → 64 | **Fails** |
| `protoN11-8k-lr5e.pt` | 14 → 64 | **Fails** |
| `protoN11-8k-lr5e-hc128.pt` | 14 → 128 | OK (only one that matches) |

Reproduced directly:
```
protoN11-4k.pt FAILS: Error(s) in loading state_dict for GraphSAGENet:
    size mismatch for conv1.lin_l.weight: copying a param with shape torch.Size([64, 14])
    from checkpoint, the shape in current model is torch.Size([128, 14])
proto311-100.pt FAILS: Error(s) in loading state_dict for GraphSAGENet:
    size mismatch for conv1.lin_l.weight: copying a param with shape torch.Size([64, 10]) ...
```

**Why it matters:** picking any model except `protoN11-8k-lr5e-hc128` in the Configuration Generation page's "Model" dropdown will raise an uncaught-shape `RuntimeError` inside `ConfigController._run_model` → `generate()` (caught generically and surfaced as a failed "GCL generation" pipeline step, but generation is completely broken for those 5 checkpoints). This also means the current `GraphSAGENet` default of `hidden_channels=128` is itself out of sync with what `models/index.md` describes as the "default hidden-channel width" for lr1e/lr3e/lr5e (see S6) — the true historical default was 64, and nothing in the current code can reproduce it since `hidden_channels` isn't exposed anywhere (CLI, `train()` call site, or config).

### B2. Duplicate same-type streams per talker are silently dropped when building GNN training features, disagreeing with the value stored in the same run's own JSON

`graph_builder.build_graph()` builds a per-talker lookup with a **dict comprehension keyed by stream `type`**:

```python
# graph_builder.py:133-135
for entry in run['workload']:
    tid = entry['talker_id']
    workload_by_talker[tid] = {s['type']: s for s in entry['streams']}
```

If a talker has two streams of the same `type` (e.g. two `"BE"` streams), the dict keeps only the **last** one — the other is invisible to `_stream_features()`, including the `total_load` sum ([graph_builder.py:55](src/layers/inferenceService/graph_builder.py#L55)), which is computed as `sum(s['load_ratio'] for s in streams_by_type.values())`, i.e. over the already-deduplicated dict, not over `entry['streams']`.

Meanwhile `ConfigController.build_run()` computes the **same conceptual quantity** correctly, summing over every stream with no dedup:
```python
# config_controller.py:89-90
"total_bandwidth_Mbps": round(sum(s["bandwidth_Mbps"] for s in streams), 3),
"total_load_ratio": round(sum(s["load_ratio"] for s in streams), 6),
```

**This is not theoretical** — I scanned every dataset JSON under `data_prep/JSON/`:

| File | Talker-rows with duplicate-type streams |
|---|---|
| `protoN11-4k_datasets.json` | 600 / 10,500 |
| `protoN11-8k_datasets.json` | 600 / 10,500 |
| `protoN11-8k-filtered_datasets.json` | 584 / 16,781 |
| `infeasible_datasets.json` | 616 / 4,219 |
| every per-config file named `BBB_*`/`CCC_*`/`omnetpp_*_B_*`/`omnetpp_*_C_*` | **100%** of rows |

This lines up exactly with `data_prep/Omnett_ini/reference.md`'s documented stream profiles `B = P7, P0, P0` and `C = P7, P7, P0` — i.e. profiles that intentionally put two streams on the same priority/type. These profiles are part of the actual training data for the shipped `protoN11-4k`/`protoN11-8k*` checkpoints.

**Why it matters:** for ~5–6% of training rows, the label the model is asked to fit (`gcl` durations) reflects the true combined traffic of a talker, but the input feature vector (`total_load`, and whichever type's row got overwritten) reflects only one of the two same-type streams. This silently corrupts a meaningful slice of the training signal and would also corrupt live inference if a user builds a topology with two same-type streams per talker in the Topology Manager (streams editor allows unlimited rows with duplicate `type` values, default `type` is `"TT7"`).

---

## Should-fix

### S1. `model_training.md` describes an old, different model and training loop

[`docs/model_training.md`](src/layers/docService/docs/model_training.md) does not match `gnn_model.py`/`graph_builder.py` on almost every concrete number it states:

| Claim in `model_training.md` | Actual code |
|---|---|
| "Node features (10 floats)" (line 47) | 14 floats ([graph_builder.py:12-16](src/layers/inferenceService/graph_builder.py#L12-L16), `graph_builder._stream_features` returns 14 values) |
| "2-layer `GraphSAGENet` (10 → 64 → 4...)" (line 73) | `in_channels=14, hidden_channels=128` ([gnn_model.py:68](src/layers/inferenceService/gnn_model.py#L68)) |
| "100 epochs" (line 73) | `EPOCHS = 200` ([gnn_model.py:53](src/layers/inferenceService/gnn_model.py#L53)) |
| "Adam (`lr=1e-3`)" (line 73) | `LR = 5e-4` ([gnn_model.py:51](src/layers/inferenceService/gnn_model.py#L51)) |
| "Print average MSE loss every 10 epochs" — no mention of train/val/test split or a baseline | Actual `train()` splits by `config_id` into train/val/test (70/15/15 by default), computes a "predict-the-average" baseline, and reports test MSE vs. baseline ([gnn_model.py:121-262](src/layers/inferenceService/gnn_model.py#L121-L262)) |

**Why it matters:** this is the only document telling a future maintainer how to retrain the model; as written it will lead them to expect the wrong input shape, wrong architecture, and wrong epoch/LR defaults, and gives no idea that a train/val/test split or baseline check exists at all.

### S2. Stale "10 input features" claim baked into the running UI

[`config_view.py:43`](src/views/configuration_generation/config_view.py#L43):
```python
st.caption("Architecture: 2-layer GraphSAGE GNN (10 input features → 4 gate-duration fractions)")
```
This is shown to every user of the Configuration Generation page. Actual input is 14 features (`GraphSAGENet(in_channels=14, ...)`, [gnn_model.py:68](src/layers/inferenceService/gnn_model.py#L68); `graph_builder.py`'s 14-float vector). Same root staleness as S1, just duplicated into a hardcoded UI string instead of a doc.

### S3. `data_json.md` misdescribes which stream types get their own model features

[`data_json.md:131`](src/layers/docService/docs/data_json.md#L131) states:

> "Only `TT7` and `BE` currently feed distinct node features in `graph_builder.py`; `TT6`/`TT5` are aggregated into `total_load` only."

Actual `_stream_features()` ([graph_builder.py:50-73](src/layers/inferenceService/graph_builder.py#L50-L73)) gives `TT6` and `TT5` their own `*_load`, `*_period_norm`, and `*_pkt_norm` features — identical treatment to `TT7`. The real asymmetry is that `BE` gets a load + period feature but **no packet-size feature** (there is no `be_pkt_norm` in the 14-float vector), while `TT7`/`TT6`/`TT5` each get all three. The doc's stated rule is backwards from what the code does.

### S4. `"AVB"` is a selectable stream type that the model silently can't see

`topology_view.py`'s stream editor offers `_STREAM_TYPES = ["TT7", "TT6", "TT5", "BE", "AVB"]` ([topology_view.py:13](src/views/topology_manager/topology_view.py#L13)), and `data_json.md:131` describes traffic as "`BE`/`AVB` (best-effort / audio-video bridging)" as if they're handled equivalently. But `graph_builder._stream_features()` only ever does `.get('TT7')`, `.get('TT6')`, `.get('TT5')`, `.get('BE')` — a stream typed `"AVB"` is never looked up by name. It still contributes to `total_load` (which sums over every entry in the per-type dict regardless of key), but gets **zero** dedicated period/packet-size representation, unlike `BE`. A user who builds workload with `AVB` streams is getting materially less signal into the model than the docs imply, with no warning anywhere in the UI.

### S5. `guide.md` and `readme.md` describe Dashboard and Logs as unbuilt placeholders — they are fully implemented

- [`docs/guide.md:15`](src/layers/docService/docs/guide.md#L15): "**Dashboard** — overview of network configuration status. *(Coming soon.)*"
- [`docs/guide.md:24`](src/layers/docService/docs/guide.md#L24): "**Logs** — audit trail and system event history. *(Coming soon.)*"
- [`readme.md:11`](readme.md#L11): "Dashboard / Logs / Documentation — placeholder pages for future network overview, run logs, and user documentation."

In reality:
- `dashboard_view.py` renders a live system-overview (model/topology/workload status cards) and a live, populated model table sourced from `inferenceService/models.py` + `index.md` ([dashboard_view.py:22-84](src/views/dashboard/dashboard_view.py#L22-L84)).
- `logs_view.py` renders a fully working filterable/searchable event log (level/category/search filters, clear button) backed by a real JSONL store (`log_store.py`) that every controller writes to ([logs_view.py:61-149](src/views/logs/logs_view.py#L61-L149)).

**Why it matters:** this is the in-app documentation shown to end users on the Documentation page itself (`guide.md` is rendered live by `docs_view.py`) — it actively tells users a working feature doesn't exist yet.

### S6. `models/index.md` describes checkpoints in terms of an already-changed default, and `docs/models.md` omits a checkpoint that exists

- `models/index.md`'s entries for `protoN11-8k-lr1e/lr3e/lr5e` call out "the default hidden-channel width," and describes `protoN11-8k-lr5e-hc128` as the one "widened to 128." Given B1's finding that the code's *current* default is 128, and the lr1e/lr3e/lr5e checkpoints are actually 64-wide, this description is only accurate against a version of `gnn_model.py` that no longer exists in the repo.
- `docs/models.md` (the user-facing checkpoint changelog) documents `proto311-100.pt`, `protoN11-4k.pt`, and the `lr1e/lr3e/lr5e` trio, but never mentions `protoN11-8k-lr5e-hc128.pt` at all, even though it's present in `models/` and in `models/index.md` (which `models.py` parses for the Dashboard). A reader of `docs/models.md` has no idea this checkpoint exists or how it differs.

### S7. Two different, differently-shaped `list_models()` implementations for the same directory

- `src/layers/inferenceService/models.py::list_models()` scans `models/*.pt` and enriches each with `model_id`/`name`/`version`/`description` parsed from `index.md` ([models.py:44-64](src/layers/inferenceService/models.py#L44-L64)). Used only by `DashboardController.list_models()` ([dashboard_controller.py:12-13](src/controllers/dashboard_controller.py#L12-L13)), and rendered with a `column_config` (`model_id`, `name`, `version`, `description`) that only this schema fills in.
- `ConfigController.list_models()` ([config_controller.py:34-43](src/controllers/config_controller.py#L34-L43)) independently re-scans the same directory but returns only `{"name": p.stem, "path", "size_kb"}` — no `model_id`, `version`, or `description`. This is the one actually used to populate the Configuration Generation page's model dropdown ([config_view.py:168](src/views/configuration_generation/config_view.py#L168)).

**Why it matters:** the version/description metadata that `index.md` was clearly designed to provide (and that IS shown correctly on the Dashboard) never reaches the page where a user actually picks which model to run inference with — they see only a bare filename and file size, so they have no way to tell e.g. `protoN11-8k-lr5e` apart from `protoN11-8k-lr5e-hc128` beyond the name itself, and given B1, most of those names will just error out anyway.

### S8. `gate_id` and `pcp` are collected, stored, and documented, but never consumed by anything downstream

Both fields are: editable in the streams data-editor ([topology_view.py:338-343](src/views/topology_manager/topology_view.py#L338-L343)), round-tripped through `converters.py`/`json_service.py`, and documented in `data_json.md` as meaningful ("`pcp` — 802.1Q Priority Code Point"; "`gate_id` — Which of the 4 hardware gates this stream is queued behind").

Grepping all of `src/` for `gate_id` and `pcp` shows they are read only by UI/conversion code — never by `graph_builder.py`, `gnn_model.py`, or `netconf_yang.py`. The model's gate assignment comes purely from its own softmax output per node, and the exported XML's gate values come from the predicted `gcl_bitmask`, not from any stream's declared `gate_id`/`pcp`.

**Why it matters:** a user who carefully sets `pcp`/`gate_id` per stream (as the UI invites them to) will see zero effect on the generated schedule or exported config — the fields are decorative.

### S9. README's and `model_training.md`'s literal training command mixes in the excluded/known-bad dataset

Both docs give this exact example:
```bash
python gnn_model.py train ../../../data_prep/JSON/
```
(`readme.md:64`, `model_training.md:66`). `_load_runs()` globs `*_datasets.json` **non-recursively** in the given folder ([gnn_model.py:104](src/layers/inferenceService/gnn_model.py#L104)), so pointing it at the top-level `data_prep/JSON/` folder picks up all four of: `infeasible_datasets.json`, `protoN11-4k_datasets.json`, `protoN11-8k_datasets.json`, `protoN11-8k-filtered_datasets.json`.

`infeasible_datasets.json` is exactly the set of runs `filter_quality.py` was built to drop (`is_quality()` rejects runs whose active-gate `deadline_miss_ratio` exceeds `MISS_THRESHOLD`). Running the documented command as written trains on the known-bad runs alongside the good ones, and also on multiple overlapping/duplicated dataset generations (`protoN11-4k` vs `protoN11-8k` cover overlapping config populations, e.g. `omnetpp_111_3_gcl_111_F750_G226_...` appears with different row counts in more than one of these files) — `_load_runs()` has no run_id dedup (that logic only exists in `data_prep/data_manager.py`, a separate tool the README doesn't say to run first here).

### S10. Dead/unreachable "skip merged file" guard in `_load_runs()`

```python
# gnn_model.py:104-106
for path in sorted(data_path.glob('*_datasets.json')):
    if path.name.upper().startswith('ALL'):
        continue
```
No file anywhere in `data_prep/JSON` (checked recursively) starts with `ALL`. The actual merge tool, `data_prep/data_manager.py::get_next_master_name()`, names merged output `master_<timestamp>_<n>.json` ([data_manager.py:98-100](data_prep/data_manager.py#L98-L100)) — which also wouldn't match the `*_datasets.json` glob in the first place. This guard appears to be leftover from an earlier naming convention and is currently unreachable dead code.

---

## Minor

### M1. Inconsistent package structure under `src/layers/`
`src/controllers/` and every `src/views/*` subpackage has an `__init__.py`; none of `src/layers/commonService`, `docService`, `helperService`, `ieeeService`, `inferenceService`, or `logService` do (only `src/layers/__init__.py` itself exists). This works today only because Python 3 falls back to implicit namespace packages — confirmed all modules still import cleanly — but it's an inconsistent convention within the same codebase.

### M2. Switch-port-mapping logic duplicated between `gnn_model.py` and `graph_builder.py`
`gnn_model.py::_switch_port_map()` ([gnn_model.py:112-118](src/layers/inferenceService/gnn_model.py#L112-L118)) and the inline block in `graph_builder.py::build_graph()` ([graph_builder.py:181-185](src/layers/inferenceService/graph_builder.py#L181-L185)) independently re-implement the identical "derive a switch's egress `port_id` from `topology.edges`, falling back to `f'{sid}P1'`" logic. They currently agree, but there's no shared source of truth, so a future edit to one is likely to silently diverge from the other.

### M3. Inconsistent fallback default for `pcp` on parse failure
`converters.streams_to_df()` and `json_service.normalize_topology_payload()` both default a missing `pcp` to `7` (matching the default `type="TT7"`). But `converters.df_to_streams()`'s exception-fallback path defaults to `0` instead ([converters.py:36-39](src/layers/helperService/converters.py#L36-L39)):
```python
try:
    pcp = int(r["pcp"]) if pd.notna(r["pcp"]) else 0
except Exception:
    pcp = 0
```
Minor because it only triggers on a NaN/parse-failure edge case in the data editor, but it's a different magic default for the same field within the same module.

### M4. Dead topology-pattern options in the UI
`_TOPOLOGY_OPTIONS` in `topology_view.py` lists `"line"`, `"tree"`, `"ring"`, `"custom"` alongside the star pattern, but the selectbox is rendered with `disabled=True` ([topology_view.py:414-416](src/views/topology_manager/topology_view.py#L414-L416)) and no code path builds edges for anything but the star shape (`topology_defaults.default_edges()` always builds talker→S1→listener). These four options can never actually be selected through the UI.

### M5. Arbitrary, undocumented UI cap on `num_listeners`
`topology_view.py:410` caps "Number of listeners" at `max_value=3` — not documented anywhere (`data_json.md` just says `int`, no range), and not enforced by any other layer (an imported JSON file with more than 3 listeners would be accepted fine via `normalize_topology_payload`).

---

## Summary

| Severity | Count |
|---|---|
| Blocker | 2 |
| Should-fix | 10 |
| Minor | 5 |

The two Blockers both trace back to the same root cause pattern: the model architecture and the feature-vector-building code evolved (10→14 features, hidden width 64→128, epochs/LR/split logic) without the checkpoints, the docs, or in one case the training-data pipeline itself being kept in lockstep. Fixing B1 requires either re-training all checkpoints at the current architecture or making `hidden_channels`/`in_channels` a per-checkpoint, discoverable parameter (e.g. stored in `index.md` and passed to `GraphSAGENet` at load time) rather than a hard-coded default. B2 requires deciding whether same-type multi-stream talkers are a supported scenario; if so, `workload_by_talker` needs to key on something other than bare `type` (e.g. `stream_id`) and `_stream_features` needs an aggregation rule for same-type streams.
