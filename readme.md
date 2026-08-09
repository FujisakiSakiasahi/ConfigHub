# ConfigHub

A Streamlit application for designing Time-Sensitive Networking (TSN) topologies and generating IEEE 802.1Qbv Gate Control List (GCL) schedules using a Graph Neural Network (GNN) model.

## Overview

ConfigHub lets you:

- **Topology Manager** — define a network topology (talkers, switches, listeners, link datarate, TX queues, cycle time) and its traffic workload (per-talker streams with type, PCP, gate ID, period, and packet size), either manually or by importing a topology/workload JSON file.
- **Configuration Generation** — run a trained GraphSAGE GNN model against the topology and workload to predict a GCL schedule, validate it (node coverage, gate bitmask format, positive durations, cycle-time coverage), and export it as `gcl.json` or as IEEE 802.1Q-Sched XML (`config.xml`).
- **Dashboard / Logs / Documentation** — placeholder pages for future network overview, run logs, and user documentation.
- **Data Prep** (`data_prep/data_manager.py`) — a standalone Streamlit tool for inspecting, comparing, and merging TSN simulation dataset JSON files (`data_prep/JSON/`) into a master dataset used for model training.

### Architecture

- `app.py` — Streamlit entry point; wires up page navigation.
- `src/views/` — page UI (dashboard, topology manager, configuration generation, logs, documentation).
- `src/controllers/` — bridge logic between views and the inference/service layers (e.g. `ConfigController` builds run payloads, invokes the model, validates output, and converts to XML).
- `src/layers/inferenceService/` — GNN model definition and training/inference code:
  - `gnn_model.py` — 2-layer GraphSAGE model, training loop, and `predict()` used at inference time.
  - `graph_builder.py` — converts a topology/workload run into a `torch_geometric` graph.
  - `models/` — trained model checkpoints (`*.pt`).
- `data_prep/` — dataset preparation tooling and raw JSON simulation data.

## Requirements

- Python 3.10+
- [Streamlit](https://streamlit.io/) (see `requirements.txt`)
- [PyTorch](https://pytorch.org/) and [PyTorch Geometric](https://pytorch-geometric.readthedocs.io/) — required to run model inference/training in `src/layers/inferenceService/` (not pinned in `requirements.txt`; install a version matching your Python/CUDA setup)
- pandas

Install the base dependencies with:

```bash
pip install -r requirements.txt
pip install pandas torch torch_geometric
```

## How to Run

### Main application (ConfigHub)

From the project root:

```bash
streamlit run app.py
```

This opens the app in your browser (default: http://localhost:8501), with pages for the Dashboard, Topology Manager, Configuration Generation, Logs, and Documentation.

### Data prep tool

To inspect and merge TSN dataset JSON files:

```bash
streamlit run data_prep/data_manager.py
```

### Training / running the GNN model directly

From `src/layers/inferenceService/`:

```bash
python gnn_model.py train ../../../data_prep/JSON/protoN11-8k-filtered_datasets.json
python gnn_model.py predict <path/to/datasets.json>
```

### The latest checkpoint model / suggested model
protoN11-8k-lr5e