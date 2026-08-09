#!/usr/bin/env python3
"""Merge per-config *_datasets.json files and split runs into quality (kept)
and infeasible (dropped) sets under a per-gate deadline-miss-ratio rule."""

import argparse
import glob
import json
import os
import statistics
import sys
from collections import defaultdict

# Max allowed deadline_miss_ratio per gate, evaluated only for gates with
# pkts_sent > 0. gate3=TT7 (highest priority) ... gate0=BE (lowest).
MISS_THRESHOLD = {
    3: 0.02,
    2: 0.05,
    1: 0.10,
    0: 0.99,
}

GATE_NAME = {3: "TT7", 2: "TT6", 1: "TT5", 0: "BE"}


def load_folder(folder):
    """Load and concatenate all *_datasets.json files in a folder."""
    pattern = os.path.join(folder, "*_datasets.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"WARNING: no *_datasets.json files found in {folder!r}", file=sys.stderr)

    rows = []
    for path in files:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print(f"  {os.path.basename(path)}: {len(data)} rows")
        rows.extend(data)
    print(f"{folder}: {len(files)} files, {len(rows)} rows total")
    return rows


def is_quality(run):
    """A run is kept iff it has >=1 active gate and every active gate's
    deadline_miss_ratio is within MISS_THRESHOLD for its gate_id."""
    metrics = run["performance"][0]["metrics"]
    active = [m for m in metrics if m["pkts_sent"] > 0]
    if not active:
        return False
    for m in active:
        threshold = MISS_THRESHOLD[m["gate_id"]]
        if m["deadline_miss_ratio"] > threshold:
            return False
    return True


def renumber(runs):
    for i, run in enumerate(runs, start=1):
        run["run_id"] = i
    return runs


def print_delay_stats(kept):
    print("\nTT latency (KEPT set) - delay_max_us by gate:")
    for gate_id in (3, 2, 1):
        values = []
        for run in kept:
            for m in run["performance"][0]["metrics"]:
                if m["gate_id"] == gate_id and m["pkts_sent"] > 0:
                    values.append(m["delay_max_us"])
        if values:
            mean_v = statistics.mean(values)
            max_v = max(values)
            print(f"  gate{gate_id} ({GATE_NAME[gate_id]}): n={len(values)} "
                  f"mean={mean_v:.2f}us max={max_v:.2f}us")
        else:
            print(f"  gate{gate_id} ({GATE_NAME[gate_id]}): no active samples")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", help="Folders containing *_datasets.json files")
    parser.add_argument("-o", "--output", default="quality_datasets.json",
                         help="Output path for kept (quality) runs")
    parser.add_argument("--dropped-output", default="infeasible_datasets.json",
                         help="Output path for dropped (infeasible) runs")
    args = parser.parse_args()

    all_rows = []
    per_file_counts = []
    for folder in args.folders:
        print(f"Loading {folder} ...")
        rows = load_folder(folder)
        per_file_counts.append((folder, len(rows)))
        all_rows.extend(rows)

    print(f"\nCombined rows read: {len(all_rows)}")

    kept, dropped = [], []
    for run in all_rows:
        (kept if is_quality(run) else dropped).append(run)

    total = len(all_rows)
    n_kept, n_dropped = len(kept), len(dropped)
    kept_pct = (n_kept / total * 100) if total else 0.0
    dropped_pct = (n_dropped / total * 100) if total else 0.0

    print(f"Kept:    {n_kept} ({kept_pct:.1f}%)")
    print(f"Dropped: {n_dropped} ({dropped_pct:.1f}%)")

    # Per-config breakdown.
    kept_by_config = defaultdict(int)
    dropped_by_config = defaultdict(int)
    for run in kept:
        kept_by_config[run["config_id"]] += 1
    for run in dropped:
        dropped_by_config[run["config_id"]] += 1

    all_configs = sorted(set(kept_by_config) | set(dropped_by_config))
    print("\nPer-config breakdown (kept / dropped):")
    for cfg in all_configs:
        k = kept_by_config.get(cfg, 0)
        d = dropped_by_config.get(cfg, 0)
        print(f"  {cfg}: {k} / {d}")

    eliminated = [cfg for cfg in all_configs if kept_by_config.get(cfg, 0) == 0]
    if eliminated:
        print(f"\nFully eliminated configs (0 kept): {len(eliminated)}")
        for cfg in eliminated:
            print(f"  - {cfg}")
    else:
        print("\nNo config was fully eliminated.")

    renumber(kept)
    renumber(dropped)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(kept, fh, indent=2)
    with open(args.dropped_output, "w", encoding="utf-8") as fh:
        json.dump(dropped, fh, indent=2)

    print(f"\nWrote {n_kept} kept runs to {args.output}")
    print(f"Wrote {n_dropped} dropped runs to {args.dropped_output}")

    print_delay_stats(kept)


if __name__ == "__main__":
    main()
