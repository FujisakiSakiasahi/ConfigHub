# Model Checkpoints

This document tracks the trained GraphSAGE checkpoints in
[`inferenceService/models/`](../../inferenceService/models/) — what each was trained
on and how it differs from the others. See [Model Training](model_training.md) for
how to produce a new checkpoint.

## proto311-100.pt

First model trained. Used a 100-row dataset purely as a smoke test to confirm the
training/inference pipeline works end-to-end — not intended for real predictions.

## protoN11-4k.pt

Trained on 311 talkers, covering 12 workload scenarios (~4k rows).

## protoN11-8k-lr1e.pt / protoN11-8k-lr3e.pt / protoN11-8k-lr5e.pt

Trained on a combined dataset of 111, 211, and 311 talkers, covering the same 12
workload scenarios (~8k rows).

Difference from `protoN11-4k.pt`: the dataset was filtered down to "good quality"
runs only, based on deadline miss ratio + priority rules.

The three checkpoints share the same data and architecture, differing only in
learning rate:

| Checkpoint             | Learning rate |
|-------------------------|--------------|
| `protoN11-8k-lr1e.pt`   | 1e-4         |
| `protoN11-8k-lr3e.pt`   | 3e-4         |
| `protoN11-8k-lr5e.pt`   | 5e-4         |
