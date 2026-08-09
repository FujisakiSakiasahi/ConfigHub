# Model Index

Metadata for each trained GNN checkpoint (`*.pt`) in this directory.
The model ID is the filename without its extension.

Each entry records the `GraphSAGENet` architecture the checkpoint was trained
with (`in_channels`, `hidden_channels`, `out_channels`) so it can be
reconstructed with the matching shape before `load_state_dict` — checkpoints
here are NOT all the same shape. Training hyperparameters (`lr`, `epochs`,
`batch_size`) are recorded for documentation only.

## proto311-100
- name: Proto 3-1-1 (100 samples)
- version: 0.1
- description: Earliest checkpoint. Trained on the small 100-sample proto311-100 dataset (fixed 3 talkers / 1 switch / 1 listener). Baseline sanity-check model, not tuned for accuracy.
- in_channels: 10
- hidden_channels: 64
- out_channels: 4
- lr: unknown (predates the lr sweep; not recorded)
- epochs: unknown (not recorded)
- batch_size: unknown (not recorded)

## protoN11-4k
- name: Proto N-1-1 (4k samples)
- version: 1.0
- description: Trained on the 4k-sample protoN11-4k dataset (variable talker count / 1 switch / 1 listener) using the default learning rate. First checkpoint to generalise across talker counts.
- in_channels: 14
- hidden_channels: 64
- out_channels: 4
- lr: 5e-4
- epochs: 200
- batch_size: 32

## protoN11-8k-lr1e
- name: Proto N-1-1 (8k, lr1e)
- version: 2.0
- description: Trained on the larger 8k-sample protoN11-8k dataset with the lowest learning rate of the lr1e/lr3e/lr5e sweep, for slower and more stable convergence.
- in_channels: 14
- hidden_channels: 64
- out_channels: 4
- lr: 1e-4
- epochs: 200
- batch_size: 32

## protoN11-8k-lr3e
- name: Proto N-1-1 (8k, lr3e)
- version: 2.1
- description: Same protoN11-8k dataset as lr1e/lr5e, trained with a mid-range learning rate between the two.
- in_channels: 14
- hidden_channels: 64
- out_channels: 4
- lr: 3e-4
- epochs: 200
- batch_size: 32

## protoN11-8k-lr5e
- name: Proto N-1-1 (8k, lr5e)
- version: 2.2
- description: Same protoN11-8k dataset, trained with the highest learning rate of the lr sweep and the default hidden-channel width.
- in_channels: 14
- hidden_channels: 64
- out_channels: 4
- lr: 5e-4
- epochs: 200
- batch_size: 32

## protoN11-8k-lr5e-hc128
- name: Proto N-1-1 (8k, lr5e, hc128)
- version: 2.3
- description: Same learning rate as protoN11-8k-lr5e, but with the GraphSAGE hidden-channel width widened to 128 to test capacity vs. accuracy.
- in_channels: 14
- hidden_channels: 128
- out_channels: 4
- lr: 5e-4
- epochs: 200
- batch_size: 32
