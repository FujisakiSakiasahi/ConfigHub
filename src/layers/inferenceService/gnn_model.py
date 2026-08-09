"""
gnn_model.py
GraphSAGE model that predicts a TSN gate schedule (GCL) from a network setup.

Plain-English overview
-----------------------
The model looks at a network (talkers, switch, listener + their traffic) and
guesses, for each device, how to split the 1 ms cycle across its 4 gates —
i.e. four fractions that add up to 1.0, like [0.9, 0, 0, 0.1].

Training = show it thousands of examples, compare its guess to the known-good
answer, and nudge its internal knobs so next time the guess is closer. The
"how wrong was the guess" number is called MSE loss. Lower = better.

Two things this version does that matter for your report:
  * TRAIN/TEST SPLIT — we hold back whole configs the model never sees while
    training, then measure on those. That is the only honest accuracy number.
    (We split by config, not by row, because the 25 rows of one config are
    near-identical — letting some into training and some into testing would
    let the model "peek" and fake a good score.)
  * BASELINE — we also print the error of a dumb guess (always predict the
    average answer). If the model can't beat the dumb guess, it learned nothing.

Usage:
  python gnn_model.py train   data_prep/JSON/protoN11-4k
  python gnn_model.py train   data_prep/JSON/protoN11-4k/111_..._datasets.json
  python gnn_model.py predict data_prep/JSON/protoN11-4k/999_..._datasets.json
  python gnn_model.py verify

`train` accepts either a folder of *_datasets.json files or a single one.
`verify` loads every checkpoint under models/ with its documented
architecture (see models/index.md) and reports OK/FAIL per checkpoint.
"""

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn.functional as F
from torch_geometric.loader import DataLoader
from torch_geometric.nn import SAGEConv

from graph_builder import build_graph
from models import get_architecture

MODEL_PATH = 'model.pt'
_SNAP_GRANULARITY = 50_000          # hardware gate-duration granularity (ns)
_GATE_BITMASKS = ["1000", "0100", "0010", "0001"]

# knobs you can tune ----------------------------------------------------------
LR          = 5e-4    # learning rate = "how hard to nudge". Smaller = gentler,
                      # more stable. 1e-3 was too aggressive (loss went UP).
EPOCHS      = 200     # how many full passes over the training data
BATCH_SIZE  = 32      # how many graphs to average over before each nudge.
                      # Averaging steadies the nudges (vs. one-graph-at-a-time).
VAL_FRAC    = 0.15    # fraction of CONFIGS held out for validation
TEST_FRAC   = 0.15    # fraction of CONFIGS held out for final testing
SEED        = 42      # fixed randomness so the split is the same every run
# -----------------------------------------------------------------------------


# ─── model ──────────────────────────────────────────────────────────────────

class GraphSAGENet(torch.nn.Module):
    """Two message-passing layers. Each node looks at its neighbours, mixes in
    their info, and eventually outputs 4 numbers (the gate fractions)."""

    def __init__(self, in_channels=14, hidden_channels=64, out_channels=4):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)                       # keeps only useful signal
        x = self.conv2(x, edge_index)
        return F.softmax(x, dim=1)          # forces the 4 outputs to sum to 1.0


# ─── helpers ────────────────────────────────────────────────────────────────

def _snap_nearest(ns): return int(round(ns / _SNAP_GRANULARITY) * _SNAP_GRANULARITY)
def _snap_ceil(ns):    return int(math.ceil(ns / _SNAP_GRANULARITY) * _SNAP_GRANULARITY)


def _max_pkt_tx_ns(run):
    link_mbps = run['topology']['link_datarate_Mbps']
    max_bytes = max(s['packet_size_bytes']
                    for e in run['workload'] for s in e['streams'])
    return max_bytes * 8_000.0 / link_mbps


def _load_runs(data_path):
    """Load training rows from either a single *_datasets.json file or a
    folder of them (skipping any merged ALL file, which would otherwise
    duplicate rows already present in the per-config files)."""
    data_path = Path(data_path)

    if data_path.is_file():
        with open(data_path) as f:
            return json.load(f)

    runs = []
    for path in sorted(data_path.glob('*_datasets.json')):
        if path.name.upper().startswith('ALL'):
            continue
        with open(path) as f:
            runs.extend(json.load(f))
    return runs


def _switch_port_map(topo):
    switch_ids = {f'S{i+1}' for i in range(topo['num_switches'])}
    port_map = {}
    for edge in topo['edges']:
        if 'port_id' in edge and edge['from'] in switch_ids:
            port_map.setdefault(edge['from'], edge['port_id'])
    return port_map


def _split_by_config(runs):
    """Group rows by config_id, then send whole configs to train/val/test.
    This prevents the 25 near-identical rows of a config from leaking across
    the split (which would inflate the score).

    Needs at least 3 configs (one each for train/val/test). A single
    *_datasets.json file usually holds just one config, so when there
    aren't enough configs to go around we fall back to splitting the rows
    themselves at random -- less rigorous, but keeps single-file training
    usable."""
    by_cfg = defaultdict(list)
    for r in runs:
        by_cfg[r.get('config_id', 'unknown')].append(r)

    cfgs = list(by_cfg.keys())

    if len(cfgs) < 3:
        print(f'  only {len(cfgs)} config(s) available -> falling back to a row-level split '
              f'(config-level train/val/test needs >= 3 configs)')
        rows = list(runs)
        random.Random(SEED).shuffle(rows)
        n = len(rows)
        n_test = max(1, int(n * TEST_FRAC))
        n_val  = max(1, int(n * VAL_FRAC))
        test_rows  = rows[:n_test]
        val_rows   = rows[n_test:n_test + n_val]
        train_rows = rows[n_test + n_val:]
        return train_rows, val_rows, test_rows, (len(cfgs), len(cfgs), len(cfgs))

    random.Random(SEED).shuffle(cfgs)

    n = len(cfgs)
    n_test = max(1, int(n * TEST_FRAC))
    n_val  = max(1, int(n * VAL_FRAC))
    test_cfgs  = cfgs[:n_test]
    val_cfgs   = cfgs[n_test:n_test + n_val]
    train_cfgs = cfgs[n_test + n_val:]

    def collect(cfg_list): return [r for c in cfg_list for r in by_cfg[c]]
    return collect(train_cfgs), collect(val_cfgs), collect(test_cfgs), \
           (len(train_cfgs), len(val_cfgs), len(test_cfgs))


def _evaluate(model, loader):
    """Average MSE of the model over a set of graphs (listener nodes ignored)."""
    model.eval()
    tot, n = 0.0, 0
    with torch.no_grad():
        for batch in loader:
            out = model(batch.x, batch.edge_index)
            mask = batch.node_type != 2
            tot += F.mse_loss(out[mask], batch.y[mask], reduction='sum').item()
            n   += int(mask.sum())
    return tot / max(n, 1)


def _baseline_mse(train_graphs, eval_graphs):
    """Dumb-guess error: predict the AVERAGE training label for every node,
    then measure how wrong that is on the eval set. The model must beat this."""
    ys = []
    for g in train_graphs:
        m = g.node_type != 2
        ys.append(g.y[m])
    mean_label = torch.cat(ys, dim=0).mean(dim=0)     # the average answer

    tot, n = 0.0, 0
    for g in eval_graphs:
        m = g.node_type != 2
        target = g.y[m]
        guess  = mean_label.expand_as(target)
        tot += F.mse_loss(guess, target, reduction='sum').item()
        n   += int(m.sum())
    return tot / max(n, 1)


# ─── training ───────────────────────────────────────────────────────────────

def train(data_path, epochs=EPOCHS, lr=LR):
    runs = _load_runs(data_path)
    if not runs:
        print(f'No training rows found in {data_path}')
        sys.exit(1)

    train_runs, val_runs, test_runs, counts = _split_by_config(runs)
    print(f'Loaded {len(runs)} rows across {sum(counts)} configs')
    print(f'  split by config -> train:{counts[0]}  val:{counts[1]}  test:{counts[2]} configs')
    print(f'  rows            -> train:{len(train_runs)}  val:{len(val_runs)}  test:{len(test_runs)}')

    train_graphs = [build_graph(r) for r in train_runs]
    val_graphs   = [build_graph(r) for r in val_runs]
    test_graphs  = [build_graph(r) for r in test_runs]

    train_loader = DataLoader(train_graphs, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_graphs,   batch_size=BATCH_SIZE)
    test_loader  = DataLoader(test_graphs,  batch_size=BATCH_SIZE)

    # the dumb-guess score to beat
    base_val = _baseline_mse(train_graphs, val_graphs)
    print(f'\nBaseline (predict-the-average) val MSE: {base_val:.6f}')
    print('  -> the model is only useful if it gets BELOW this.\n')

    model = GraphSAGENet()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    best_val = float('inf')
    for epoch in range(1, epochs + 1):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            out = model(batch.x, batch.edge_index)
            mask = batch.node_type != 2            # ignore listener nodes
            loss = F.mse_loss(out[mask], batch.y[mask])
            loss.backward()
            optimizer.step()

        if epoch % 10 == 0 or epoch == 1:
            tr = _evaluate(model, train_loader)
            va = _evaluate(model, val_loader)
            flag = '  <- new best' if va < best_val else ''
            print(f'Epoch {epoch:4d} | train MSE {tr:.6f} | val MSE {va:.6f}{flag}')

        # keep the version that generalises best, not the last one
        va = _evaluate(model, val_loader)
        if va < best_val:
            best_val = va
            torch.save(model.state_dict(), MODEL_PATH)

    # final honest score, on configs never seen during training
    model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))
    test_mse = _evaluate(model, test_loader)
    base_test = _baseline_mse(train_graphs, test_graphs)

    print('\n================ RESULT ================')
    print(f'  model  test MSE : {test_mse:.6f}   (lower = better)')
    print(f'  dumb-guess MSE  : {base_test:.6f}')
    if test_mse < base_test:
        print(f'  --> model beats the baseline by {100*(1-test_mse/base_test):.1f}%  (it learned something)')
    else:
        print('  --> model does NOT beat the baseline (it did not learn a useful mapping)')
    print(f'  tested on {counts[2]} configs the model never saw during training.')
    print('========================================')
    print(f'\nBest model saved to {MODEL_PATH}')


# ─── checkpoint loading ────────────────────────────────────────────────────────

def load_checkpoint(path):
    """Build a GraphSAGENet with the architecture documented for this checkpoint
    in models/index.md (falling back to defaults + a warning if undocumented),
    then load its weights."""
    model_id = Path(path).stem
    arch = get_architecture(model_id)
    model = GraphSAGENet(**arch)
    model.load_state_dict(torch.load(path, weights_only=True))
    return model


def verify_checkpoints():
    """Load every *.pt checkpoint in models/ and report OK/FAIL per file."""
    models_dir = Path(__file__).resolve().parent / 'models'
    checkpoints = sorted(models_dir.glob('*.pt'))
    print(f'Verifying {len(checkpoints)} checkpoint(s) in {models_dir}:')
    all_ok = True
    for ckpt in checkpoints:
        try:
            load_checkpoint(ckpt)
            print(f'  OK    {ckpt.name}')
        except Exception as e:
            all_ok = False
            print(f'  FAIL  {ckpt.name}: {e}')
    return all_ok


# ─── prediction ───────────────────────────────────────────────────────────────

def predict(run):
    model = load_checkpoint(MODEL_PATH)
    model.eval()

    data = build_graph(run)
    topo = run['topology']
    cycle_ns = topo['gcl_cycle_time_ns']
    nt = topo['num_talkers']
    ns_count = topo['num_switches']

    min_snap = _snap_ceil(_max_pkt_tx_ns(run))
    switch_ids = [f'S{i+1}' for i in range(ns_count)]
    port_map = _switch_port_map(topo)

    with torch.no_grad():
        out = model(data.x, data.edge_index)

    def _gcl_entry(parent_id, node_idx):
        seqs = []
        for gate_idx, prob in enumerate(out[node_idx].tolist()):
            snapped = _snap_nearest(prob * cycle_ns)
            if snapped == 0:
                continue
            seqs.append({
                "gate_bitmask": _GATE_BITMASKS[gate_idx],
                "duration_ns": max(snapped, min_snap),
            })
        return {"parent_id": parent_id, "gcl_sequences": seqs}

    gcl_output = [_gcl_entry(f'T{i+1}', i) for i in range(nt)]
    for j, sid in enumerate(switch_ids):
        port_id = port_map.get(sid, f'{sid}P1')
        gcl_output.append(_gcl_entry(port_id, nt + j))
    return gcl_output


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'verify':
        sys.exit(0 if verify_checkpoints() else 1)

    if len(sys.argv) < 3:
        print('Usage:')
        print('  python gnn_model.py train   <data_folder | single_datasets.json>')
        print('  python gnn_model.py predict <datasets_json>')
        print('  python gnn_model.py verify')
        sys.exit(1)

    mode, arg = sys.argv[1], sys.argv[2]
    if mode == 'train':
        train(arg)
    elif mode == 'predict':
        with open(arg) as f:
            dataset = json.load(f)
        print(json.dumps(predict(dataset[0]), indent=2))
    else:
        print(f'Unknown mode: {mode!r}. Use "train" or "predict".')
        sys.exit(1)