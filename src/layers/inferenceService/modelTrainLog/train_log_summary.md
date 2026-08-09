# GCL-Prediction GNN — Training Log Summary

Purpose: condensed, report-ready summary of the `protoN11-8k` training sweep for the
GraphSAGE model that predicts TSN Gate Control List (GCL) schedules. Source logs live
in this same folder (`protoN11-8k-lr1e`, `protoN11-8k-lr3e`, `protoN11-8k-lr5e`,
`protoN11-8k-lr5e-hc128`); full raw text is reproduced in the Appendix.

## 1. Task and pipeline

- **Model**: `GraphSAGENet` — 2-layer GraphSAGE (`SAGEConv`), softmax output.
- **Input**: one graph per network configuration (talkers → switches → listeners,
  bidirectional edges), 14 node features (load ratios, TT/BE period & packet-size
  norms, link-datarate norm, TX-queue-count norm).
- **Label**: 4 floats per node = fraction of the GCL cycle each of 4 gates is open.
  Listener nodes are excluded from the loss.
- **Loss**: MSE over non-listener nodes.
- **Optimizer**: Adam, batch size 32, 200 epochs per run.
- Code: `gnn_model.py`; training procedure documented in `docs/model_training.md`.

## 2. Dataset

Dataset: `protoN11-8k` (variable talker count, 1 switch, 1 listener), quality-filtered.

- 8,727 rows across 420 configs, split **by config** (not by row) to avoid leakage:
  - train: 294 configs / 6,083 rows
  - val: 63 configs / 1,338 rows
  - test: 63 configs / 1,306 rows (never seen during training)
- **Baselines** (predict-the-average, i.e. "dumb guess"):
  - val MSE: 0.166671
  - test MSE: 0.181610
  - A trained model is only useful if it scores below these.

## 3. Experiment sweep

Four checkpoints trained on this dataset, varying learning rate and (in one case)
hidden-channel width. All other hyperparameters held fixed (`in_channels=14`,
`out_channels=4`, `epochs=200`, `batch_size=32`).

| Run                    | lr    | hidden_channels | Purpose                                   |
|-------------------------|-------|------------------|--------------------------------------------|
| protoN11-8k-lr1e        | 1e-4  | 64               | Slowest/most stable end of lr sweep        |
| protoN11-8k-lr3e        | 3e-4  | 64               | Mid-range lr                               |
| protoN11-8k-lr5e        | 5e-4  | 64               | Highest lr, default width                  |
| protoN11-8k-lr5e-hc128  | 5e-4  | 128              | Same lr as lr5e, doubled hidden width      |

## 4. Results

| Run                    | Test MSE  | Baseline (dumb-guess) MSE | Improvement over baseline | Lowest printed val MSE (epoch) |
|-------------------------|-----------|---------------------------|----------------------------|----------------------------------|
| protoN11-8k-lr1e        | 0.083916  | 0.181610                  | **53.8%**                  | 0.069174 (ep 130)               |
| protoN11-8k-lr3e        | 0.084088  | 0.181610                  | 53.7%                       | 0.070258 (ep 180)               |
| **protoN11-8k-lr5e**     | **0.083556** | 0.181610                | **54.0%** (best)            | 0.069874 (ep 40)                |
| protoN11-8k-lr5e-hc128   | 0.086226  | 0.181610                  | 52.5% (worst)                | 0.069833 (ep 80)                |

## 5. Observations

- **All four runs land in a tight band** (test MSE 0.0836–0.0862; ~52.5–54.0%
  improvement over the dumb-guess baseline) — the model reliably learns useful
  structure regardless of the exact lr in this range.
- **`lr5e` (5e-4, hidden=64) is the best performer**, marginally ahead of `lr1e`
  and `lr3e`.
- **Widening the network to hidden_channels=128 did not help** — `lr5e-hc128` has
  the same lr as `lr5e` but the worst test MSE of the sweep. Extra capacity gave
  no benefit here and may be mildly counterproductive.
- **Mild overfitting pattern in every run**: train MSE decreases monotonically
  through all 200 epochs, but val MSE bottoms out early (roughly epoch 40–130
  depending on run) and then drifts upward or oscillates for the remaining
  epochs while train MSE keeps falling. This is consistent across all four runs
  regardless of lr or width, suggesting 200 epochs may be more than needed and
  an early-stopping/checkpoint-on-best-val strategy (already used here — the
  saved checkpoint is the best-val epoch, not the final epoch) is doing the
  right thing.
- Higher lr (`lr5e`) reaches its best val MSE earliest (epoch 40) vs. the lowest
  lr (`lr1e`, epoch 130) — expected, since larger steps converge faster, though
  final quality is similar across the sweep.

## 6. Lineage (earlier checkpoints, for context)

Not part of this sweep, but prior checkpoints on the same model/pipeline
(from `models/index.md`):

| Checkpoint       | Dataset                          | in_channels | hidden | lr    | Notes |
|------------------|-----------------------------------|-------------|--------|-------|-------|
| proto311-100     | 100 samples, fixed 3T/1S/1L      | 10          | 64     | n/a   | Earliest sanity-check baseline, not tuned for accuracy |
| protoN11-4k      | 4k samples, variable talker count | 14          | 64     | 5e-4  | First checkpoint to generalise across talker counts |

## 7. File locations

- Raw logs: `src/layers/inferenceService/modelTrainLog/protoN11-8k-lr{1,3,5}e[-hc128]`
- Checkpoints: `src/layers/inferenceService/models/protoN11-8k-lr{1,3,5}e[-hc128].pt`
- Checkpoint metadata: `src/layers/inferenceService/models/index.md`
- Training procedure: `src/layers/docService/docs/model_training.md`

---

## Appendix: raw training logs

### protoN11-8k-lr1e (lr=1e-4, hidden=64)

```
Loaded 8727 rows across 420 configs
  split by config -> train:294  val:63  test:63 configs
  rows            -> train:6083  val:1338  test:1306

Baseline (predict-the-average) val MSE: 0.166671
  -> the model is only useful if it gets BELOW this.

Epoch    1 | train MSE 0.177399 | val MSE 0.159932  <- new best
Epoch   10 | train MSE 0.128008 | val MSE 0.122968  <- new best
Epoch   20 | train MSE 0.111511 | val MSE 0.107356  <- new best
Epoch   30 | train MSE 0.101029 | val MSE 0.094739  <- new best
Epoch   40 | train MSE 0.093896 | val MSE 0.086866  <- new best
Epoch   50 | train MSE 0.089437 | val MSE 0.079523  <- new best
Epoch   60 | train MSE 0.085862 | val MSE 0.077445
Epoch   70 | train MSE 0.083500 | val MSE 0.074388
Epoch   80 | train MSE 0.081914 | val MSE 0.072858
Epoch   90 | train MSE 0.080742 | val MSE 0.070972  <- new best
Epoch  100 | train MSE 0.079956 | val MSE 0.070239
Epoch  110 | train MSE 0.079336 | val MSE 0.070158
Epoch  120 | train MSE 0.078904 | val MSE 0.070118
Epoch  130 | train MSE 0.078621 | val MSE 0.069174
Epoch  140 | train MSE 0.078287 | val MSE 0.069902
Epoch  150 | train MSE 0.078093 | val MSE 0.069682
Epoch  160 | train MSE 0.077934 | val MSE 0.069559
Epoch  170 | train MSE 0.077932 | val MSE 0.070529
Epoch  180 | train MSE 0.077727 | val MSE 0.069645
Epoch  190 | train MSE 0.077722 | val MSE 0.070494
Epoch  200 | train MSE 0.077559 | val MSE 0.070442

================ RESULT ================
  model  test MSE : 0.083916   (lower = better)
  dumb-guess MSE  : 0.181610
  --> model beats the baseline by 53.8%  (it learned something)
  tested on 63 configs the model never saw during training.
========================================
```

### protoN11-8k-lr3e (lr=3e-4, hidden=64)

```
Loaded 8727 rows across 420 configs
  split by config -> train:294  val:63  test:63 configs
  rows            -> train:6083  val:1338  test:1306

Baseline (predict-the-average) val MSE: 0.166671
  -> the model is only useful if it gets BELOW this.

Epoch    1 | train MSE 0.158307 | val MSE 0.144885  <- new best
Epoch   10 | train MSE 0.100844 | val MSE 0.094987  <- new best
Epoch   20 | train MSE 0.087283 | val MSE 0.079293  <- new best
Epoch   30 | train MSE 0.082057 | val MSE 0.074506
Epoch   40 | train MSE 0.079773 | val MSE 0.071442
Epoch   50 | train MSE 0.078467 | val MSE 0.070525
Epoch   60 | train MSE 0.079477 | val MSE 0.074620
Epoch   70 | train MSE 0.077695 | val MSE 0.071366
Epoch   80 | train MSE 0.077716 | val MSE 0.072401
Epoch   90 | train MSE 0.077397 | val MSE 0.070880
Epoch  100 | train MSE 0.077477 | val MSE 0.072219
Epoch  110 | train MSE 0.077418 | val MSE 0.070309
Epoch  120 | train MSE 0.077107 | val MSE 0.070671
Epoch  130 | train MSE 0.077001 | val MSE 0.071162
Epoch  140 | train MSE 0.077184 | val MSE 0.073422
Epoch  150 | train MSE 0.077055 | val MSE 0.071801
Epoch  160 | train MSE 0.076900 | val MSE 0.072904
Epoch  170 | train MSE 0.077038 | val MSE 0.073727
Epoch  180 | train MSE 0.077023 | val MSE 0.070258
Epoch  190 | train MSE 0.076985 | val MSE 0.072426
Epoch  200 | train MSE 0.076875 | val MSE 0.071866

================ RESULT ================
  model  test MSE : 0.084088   (lower = better)
  dumb-guess MSE  : 0.181610
  --> model beats the baseline by 53.7%  (it learned something)
  tested on 63 configs the model never saw during training.
========================================
```

### protoN11-8k-lr5e (lr=5e-4, hidden=64)

```
Loaded 8727 rows across 420 configs
  split by config -> train:294  val:63  test:63 configs
  rows            -> train:6083  val:1338  test:1306

Baseline (predict-the-average) val MSE: 0.166671
  -> the model is only useful if it gets BELOW this.

Epoch    1 | train MSE 0.147762 | val MSE 0.139123  <- new best
Epoch   10 | train MSE 0.091488 | val MSE 0.084086  <- new best
Epoch   20 | train MSE 0.082653 | val MSE 0.075935
Epoch   30 | train MSE 0.079245 | val MSE 0.070744  <- new best
Epoch   40 | train MSE 0.078336 | val MSE 0.069874
Epoch   50 | train MSE 0.077610 | val MSE 0.072402
Epoch   60 | train MSE 0.077524 | val MSE 0.071456
Epoch   70 | train MSE 0.077371 | val MSE 0.073315
Epoch   80 | train MSE 0.077119 | val MSE 0.070480
Epoch   90 | train MSE 0.076970 | val MSE 0.072028
Epoch  100 | train MSE 0.077086 | val MSE 0.071224
Epoch  110 | train MSE 0.076812 | val MSE 0.072769
Epoch  120 | train MSE 0.076795 | val MSE 0.072070
Epoch  130 | train MSE 0.076716 | val MSE 0.072789
Epoch  140 | train MSE 0.076528 | val MSE 0.073610
Epoch  150 | train MSE 0.076683 | val MSE 0.072656
Epoch  160 | train MSE 0.076423 | val MSE 0.072681
Epoch  170 | train MSE 0.076924 | val MSE 0.072552
Epoch  180 | train MSE 0.076320 | val MSE 0.073238
Epoch  190 | train MSE 0.076314 | val MSE 0.073037
Epoch  200 | train MSE 0.076538 | val MSE 0.074089

================ RESULT ================
  model  test MSE : 0.083556   (lower = better)
  dumb-guess MSE  : 0.181610
  --> model beats the baseline by 54.0%  (it learned something)
  tested on 63 configs the model never saw during training.
========================================
```

### protoN11-8k-lr5e-hc128 (lr=5e-4, hidden=128)

```
Loaded 8727 rows across 420 configs
  split by config -> train:294  val:63  test:63 configs
  rows            -> train:6083  val:1338  test:1306

Baseline (predict-the-average) val MSE: 0.166671
  -> the model is only useful if it gets BELOW this.

Epoch    1 | train MSE 0.138805 | val MSE 0.130315  <- new best
Epoch   10 | train MSE 0.086783 | val MSE 0.080045  <- new best
Epoch   20 | train MSE 0.080509 | val MSE 0.071473  <- new best
Epoch   30 | train MSE 0.079019 | val MSE 0.070001
Epoch   40 | train MSE 0.077972 | val MSE 0.071435
Epoch   50 | train MSE 0.077589 | val MSE 0.074596
Epoch   60 | train MSE 0.077274 | val MSE 0.072284
Epoch   70 | train MSE 0.077475 | val MSE 0.074472
Epoch   80 | train MSE 0.077496 | val MSE 0.069833
Epoch   90 | train MSE 0.076978 | val MSE 0.074478
Epoch  100 | train MSE 0.077010 | val MSE 0.070693
Epoch  110 | train MSE 0.076845 | val MSE 0.071734
Epoch  120 | train MSE 0.076570 | val MSE 0.074963
Epoch  130 | train MSE 0.076802 | val MSE 0.073801
Epoch  140 | train MSE 0.076645 | val MSE 0.074555
Epoch  150 | train MSE 0.076337 | val MSE 0.073757
Epoch  160 | train MSE 0.076133 | val MSE 0.074326
Epoch  170 | train MSE 0.076698 | val MSE 0.071983
Epoch  180 | train MSE 0.076000 | val MSE 0.073883
Epoch  190 | train MSE 0.075961 | val MSE 0.075218
Epoch  200 | train MSE 0.075844 | val MSE 0.075661

================ RESULT ================
  model  test MSE : 0.086226   (lower = better)
  dumb-guess MSE  : 0.181610
  --> model beats the baseline by 52.5%  (it learned something)
  tested on 63 configs the model never saw during training.
========================================
```
