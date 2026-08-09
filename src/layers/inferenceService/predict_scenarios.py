"""
predict_scenarios.py
Runs a trained GNN checkpoint over a batch of RL scenarios (topology +
workload only -- no ground-truth GCL/performance) and saves the predicted
GCL for each one.

Usage:
  python predict_scenarios.py rl_scenarios.json -o baseline_gcls.json --model protoN11-8k-lr5e
"""

import argparse
import json
from pathlib import Path

import gnn_model

MODELS_DIR = Path(__file__).resolve().parent / 'models'
DEFAULT_MODEL = 'protoN11-8k-lr5e'


def predict_scenario(scenario: dict) -> list:
    """Predict the GCL for one scenario.

    build_graph() expects a 'gcl' key (it uses it to build training labels),
    but scenarios here have no ground truth -- an empty one is fine since
    prediction never reads data.y, only data.x/edge_index.
    """
    run = {**scenario, 'gcl': scenario.get('gcl', [])}
    return gnn_model.predict(run)


def main():
    parser = argparse.ArgumentParser(
        description='Run a trained GNN over a set of scenarios and save predicted GCLs.')
    parser.add_argument('scenarios', help='Path to rl_scenarios.json')
    parser.add_argument('-o', '--output', default='baseline_gcls.json',
                         help='Output path for predicted GCLs (default: baseline_gcls.json)')
    parser.add_argument('--model', default=DEFAULT_MODEL,
                         help=f'Checkpoint id under models/, without .pt (default: {DEFAULT_MODEL})')
    args = parser.parse_args()

    model_name = args.model[:-3] if args.model.endswith('.pt') else args.model
    model_path = MODELS_DIR / f'{model_name}.pt'
    if not model_path.exists():
        raise SystemExit(f'Model checkpoint not found: {model_path}')

    # predict() loads whatever checkpoint gnn_model.MODEL_PATH points at, and
    # derives its architecture (in_channels/hidden_channels) from index.md via
    # load_checkpoint() -- pointing it here reuses that exact path.
    gnn_model.MODEL_PATH = str(model_path)

    with open(args.scenarios) as f:
        scenarios = json.load(f)

    results = []
    errors = []
    for scenario in scenarios:
        scenario_id = scenario.get('scenario_id', '?')
        try:
            predicted_gcl = predict_scenario(scenario)
            results.append({
                'scenario_id': scenario_id,
                'config_id': scenario.get('config_id'),
                'run_id': scenario.get('run_id'),
                'topology': scenario['topology'],
                'workload': scenario['workload'],
                'predicted_gcl': predicted_gcl,
            })
        except Exception as e:
            errors.append((scenario_id, str(e)))
            print(f'ERROR  scenario {scenario_id}: {e}')

    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)

    print(f'\nProcessed {len(results)}/{len(scenarios)} scenario(s) -> {args.output} (model: {model_name})')
    if errors:
        print(f'{len(errors)} scenario(s) failed:')
        for scenario_id, msg in errors:
            print(f'  {scenario_id}: {msg}')


if __name__ == '__main__':
    main()
