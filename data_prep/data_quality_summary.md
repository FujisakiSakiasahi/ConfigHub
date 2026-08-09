# Data Quality Filtering Summary

Purpose: report-ready summary of the quality-filtering pass that produced
`data_prep/JSON/protoN11-8k-filtered_datasets.json` (accepted) and
`data_prep/JSON/infeasible_datasets.json` (rejected) from the raw simulation
output. Computed by re-running the exact filter rule from
`data_prep/filter_quality.py` against the raw source folders and
cross-checking the result against the two output files record-for-record
(matched exactly, per config_id).

## 1. Filter rule

A record is **kept** iff:
- it has at least one active gate (`pkts_sent > 0`), **and**
- every active gate's `deadline_miss_ratio` is within its per-gate threshold:

| Gate | Traffic type | Max deadline-miss ratio |
|---|---|---|
| gate 3 | TT7 (highest priority) | 2% |
| gate 2 | TT6 | 5% |
| gate 1 | TT5 | 10% |
| gate 0 | BE (lowest priority) | 99% |

Anything failing either condition is dropped as **infeasible**.

## 2. Source data

Filtering was run over the combined raw per-config run files in:
- `data_prep/JSON/protoN11-8k/` — 280 files, 7,000 records
- `data_prep/JSON/protoN11-4k/` — 140 files, 3,500 records

(Confirmed: these two folders combined, filtered by the rule above, reproduce
`protoN11-8k-filtered_datasets.json` and `infeasible_datasets.json` exactly —
matching kept/dropped counts per `config_id`.)

## 3. Headline numbers

| Metric | Value |
|---|---|
| Total records before filtering | **10,500** |
| Accepted (kept/quality) records | **8,727** |
| Rejected (infeasible) records | **1,773** |
| % retained | **83.1%** |
| % rejected | **16.9%** |
| Unique configurations (`config_id`) before filtering | **420** |
| Duplicate-record count | **0** — checked two ways: exact full-record match, and duplicate `(config_id, run_id)` key. Neither found any duplicates. |
| Records with missing/invalid required fields | **0** — every record had complete `topology`, `workload`, `gcl`, and `performance` structures with all required sub-fields present. |
| Configs fully eliminated by filtering | **0 of 420** — every configuration retained at least one accepted run; none were wiped out entirely. |

## 4. Traffic-type distribution (TT7 / TT6 / TT5 / BE)

Two views, since "distribution" can mean either how many streams are of each
type, or how much of the network's load each type represents. Counted per
talker-stream entry inside `workload[].streams[]` (a single record can carry
multiple streams of different types).

### By stream count

| Type | Pre-filter (n=54,000 streams) | Kept (n=43,289) | Rejected (n=10,711) |
|---|---|---|---|
| TT7 | 15,600 (28.9%) | 12,295 (28.4%) | 3,305 (30.9%) |
| TT6 | 13,800 (25.6%) | 11,499 (26.6%) | 2,301 (21.5%) |
| TT5 | 13,800 (25.6%) | 11,513 (26.6%) | 2,287 (21.4%) |
| BE  | 10,800 (20.0%) | 7,982 (18.4%)  | 2,818 (26.3%) |

### By load-ratio share (sum of `load_ratio` per type ÷ total)

| Type | Pre-filter | Kept | Rejected |
|---|---|---|---|
| TT7 | 29.3% | 21.2% | **40.1%** |
| TT6 | 24.1% | 23.7% | 24.7% |
| TT5 | 24.1% | 26.1% | 21.4% |
| BE  | 22.6% | 29.1% | 13.8% |

**Observation**: TT7 carries a disproportionate share of the *load* in the
rejected set (40.1% of rejected load vs. 29.3% pre-filter) even though its
share of *stream count* barely shifts (30.9% vs 28.9%). This is consistent
with the filter rule — TT7 has the tightest deadline-miss tolerance (2%), so
configurations that overload TT7 traffic are the most likely to be flagged
infeasible.

## 5. Methodology notes

- "Total records before filtering" = the raw per-config JSON files that were
  the actual input to `filter_quality.py` for this dataset generation
  (`protoN11-8k/` + `protoN11-4k/` folders), **not** the merged
  `protoN11-8k_datasets.json` master file alone (7,000 rows) — that master
  only covers one of the two source folders.
- Duplicate detection was run two ways to be safe: (1) byte-for-byte identical
  JSON records, and (2) same `(config_id, run_id)` pair. Both returned zero.
- "Missing/invalid fields" checked for presence and non-null values of the
  required top-level keys (`run_id`, `config_id`, `topology`, `workload`,
  `gcl`, `performance`) and the required `topology` sub-fields
  (`num_talkers`, `num_switches`, `num_listeners`, `link_datarate_Mbps`,
  `num_tx_queues`, `gcl_cycle_time_ns`, `edges`).

## 6. File locations

- Filter script: `data_prep/filter_quality.py`
- Raw source folders: `data_prep/JSON/protoN11-8k/`, `data_prep/JSON/protoN11-4k/`
- Accepted output: `data_prep/JSON/protoN11-8k-filtered_datasets.json`
- Rejected output: `data_prep/JSON/infeasible_datasets.json`
