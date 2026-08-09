# Training the GCL-prediction GNN model

This document describes how to train the GraphSAGE model in
[`inferenceService/gnn_model.py`](../../inferenceService/gnn_model.py) and produce a
`*.pt` checkpoint that the Configuration Generation page can use for inference.

## 1. Prerequisites

Install the training dependencies (not included in the app's `requirements.txt`,
since the Streamlit app only needs them at inference time):

```bash
pip install torch torch_geometric
```

## 2. Prepare training data

Training reads every file matching `*_datasets.json` in a given folder
(see `_load_runs` in `gnn_model.py`). The intended training input is the
quality-filtered dataset, `data_prep/JSON/protoN11-8k-filtered_datasets.json`
— train directly on that single file, not on the whole `data_prep/JSON/`
folder, since the folder also contains earlier/overlapping dataset
generations.

> **Do not include `data_prep/JSON/infeasible_datasets.json` in training.**
> It's the held-out infeasible set produced by `filter_quality.py` for later
> analysis, not training data — `_load_runs` will happily glob it in if it's
> sitting in a folder you point training at.

Each file is a JSON list of **run** objects. A run must contain:

- `topology` — `num_talkers`, `num_switches`, `num_listeners`, `link_datarate_Mbps`,
  `num_tx_queues`, `gcl_cycle_time_ns`, `edges` (list of `{from, to, port_id?}`).
- `workload` — one entry per talker: `talker_id` and its `streams`
  (`type`, `period_ns`, `packet_size_bytes`, `load_ratio`, ...).
- `gcl` — the ground-truth schedule used as the training label: a list of
  `{parent_id, gcl_sequences: [{gate_bitmask, duration_ns}, ...]}` entries, one
  per talker and per switch egress port.

Use the [Data Prep tool](../../../../data_prep/data_manager.py)
(`streamlit run data_prep/data_manager.py`) to inspect, combine, and de-duplicate
run files (by `run_id`) into a single master dataset before training, if desired.
`gnn_model.py` itself will happily load multiple `*_datasets.json` files from the
same folder, so a merged master file is a convenience, not a requirement.

Each run is converted into a `torch_geometric.data.Data` graph by
[`graph_builder.build_graph`](../../inferenceService/graph_builder.py):

- **Nodes**, in deterministic order: talkers → switches → listeners.
- **Node features** (10 floats): total/per-type load ratios, TT7 period/packet-size
  norms, BE period norm, link-datarate norm, TX-queue-count norm.
- **Labels** (4 floats per node): fraction of the cycle each of the 4 gates is open,
  derived from `gcl_sequences` and normalised by `gcl_cycle_time_ns`. Listener
  nodes get an all-zero label and are excluded from the training loss.
- **Edges**: bidirectional, built from `topology.edges`.

## 3. Run training

From `src/layers/inferenceService/`:

```bash
python gnn_model.py train <data_folder | single_datasets.json>
```

Example, from the project root:

```bash
cd src/layers/inferenceService
python gnn_model.py train ../../../data_prep/JSON/protoN11-8k-filtered_datasets.json
```

This will:

1. Load and parse every `*_datasets.json` run in `<data_folder>` and build one
   graph per run.
2. Train a 2-layer `GraphSAGENet` (10 → 64 → 4, softmax output) for 100 epochs
   with Adam (`lr=1e-3`), using per-run full-batch gradient descent and MSE loss
   over non-listener nodes.
3. Print average MSE loss every 10 epochs.
4. Save the trained weights to `model.pt` in the **current working directory**
   (`MODEL_PATH = 'model.pt'` — this is a relative path, so run the command from
   wherever you want the checkpoint to land, or move it afterwards).

To change the number of epochs or learning rate, call `train()` directly instead
of via the CLI, since these aren't exposed as CLI flags:

```bash
python -c "from gnn_model import train; train('../../../data_prep/JSON/protoN11-8k-filtered_datasets.json', epochs=200, lr=5e-4)"
```

## 4. Install the checkpoint for the app

The Configuration Generation page discovers models by scanning
`src/layers/inferenceService/models/*.pt` (see `ConfigController.list_models`).
Move the produced `model.pt` into that folder, giving it a descriptive name
(the existing checkpoint is named `proto311-100.pt`):

```bash
mv model.pt ../inferenceService/models/<name>-<epochs>.pt
```

Restart (or rerun) the Streamlit app — the new checkpoint will appear in the
**Model** dropdown on the Configuration Generation page.

## 5. Sanity-check with prediction

Before relying on a new checkpoint in the app, smoke-test it from the CLI. Since
`predict()` uses the module-level `MODEL_PATH`, point it at your checkpoint first:

```bash
python -c "
import gnn_model, json
gnn_model.MODEL_PATH = '../inferenceService/models/<name>-<epochs>.pt'
with open('<path/to/datasets.json>') as f:
    run = json.load(f)[0]
print(json.dumps(gnn_model.predict(run), indent=2))
"
```

Or, if the checkpoint is already named `model.pt` in the current directory:

```bash
python gnn_model.py predict <path/to/datasets.json>
```

Check that:

- Every expected node (`T1..Tn`, and each switch egress `port_id`) has a GCL entry.
- `gate_bitmask` values are 4-character binary strings.
- `duration_ns` values are positive.
- Per-node schedule durations sum close to `gcl_cycle_time_ns`.

These are the same checks `ConfigController.validate_gcl` runs automatically in
the app's Configuration Generation pipeline.
