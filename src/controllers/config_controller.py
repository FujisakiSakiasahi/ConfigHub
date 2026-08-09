"""Bridge between the configuration generation view and the inference/service layers."""

import sys
from pathlib import Path

import pandas as pd

from src.layers.helperService import calculations, converters, validators
from src.layers.ieeeService import netconf_yang
from src.layers.logService.event_logger import LogCategory, logger

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_INFERENCE_DIR = _PROJECT_ROOT / "src" / "layers" / "inferenceService"

# Canonical pipeline step order, used by the view to render a fixed checklist
# (steps not yet reached by a run are shown as "not run" rather than omitted).
PIPELINE_STEPS = [
    "Build run payload",
    "GCL generation",
    "All nodes scheduled",
    "Gate bitmask format",
    "Positive gate durations",
    "Cycle-time coverage",
    "XML conversion",
    "XML well-formed",
]


class ConfigController:
    """Bridge between the configuration generation view and service layers."""

    # ── model discovery ──────────────────────────────────────────────────────

    def list_models(self) -> list[dict]:
        """Scan the inference service's models directory for trained checkpoints (*.pt),
        enriched with the architecture/hyperparameter metadata from models/index.md so
        the dropdown can show which architecture each checkpoint is."""
        if str(_INFERENCE_DIR) not in sys.path:
            sys.path.insert(0, str(_INFERENCE_DIR))
        import models as model_index  # local import: keeps torch off the page-load path

        out = []
        for m in model_index.list_models():
            out.append({
                "name": m["model_id"],
                "path": m["path"],
                "size_kb": m["size_kb"],
                "display_name": m["name"],
                "version": m["version"],
                "description": m["description"],
                "in_channels": m["in_channels"],
                "hidden_channels": m["hidden_channels"],
                "out_channels": m["out_channels"],
                "lr": m["lr"],
                "epochs": m["epochs"],
                "batch_size": m["batch_size"],
            })
        return out

    # ── view display helpers ─────────────────────────────────────────────────

    def status_icon(self, passed) -> str:
        return validators.status_icon(passed)

    def gcl_to_dataframe(self, gcl: list) -> pd.DataFrame:
        return converters.gcl_to_df(gcl)

    # ── run payload assembly ─────────────────────────────────────────────────

    def build_run(self, topo_params: dict, workload_rows: list[dict]) -> dict:
        """Assemble a model-ready run payload from raw UI state.

        Edges are taken directly from the Edges table on the Topology Manager
        page. If none were provided, they're synthesised for the single-switch
        star shape: every talker feeds S1, and S1 egresses to each listener
        over its own port.
        """
        n_talkers = int(topo_params.get("num_talkers", 0))
        n_switches = int(topo_params.get("num_switches", 1))
        n_listeners = int(topo_params.get("num_listeners", 1))
        link_dr = float(topo_params.get("link_datarate_Mbps", 1000))
        topology_id = topo_params.get("topology_id", "TsnIntelStar")
        device_model = topo_params.get("device_model", "intel_i226")
        num_tx_queues = int(topo_params.get("num_tx_queues", 4))
        cycle_ns = int(topo_params.get("gcl_cycle_time_ns", 1_000_000))

        edges = topo_params.get("edges") or (
            [{"from": f"T{i + 1}", "to": "S1"} for i in range(n_talkers)]
            + [{"from": "S1", "to": f"L{j + 1}", "port_id": f"S1P{j + 1}"} for j in range(n_listeners)]
        )

        workload = []
        for row in workload_rows:
            streams = []
            for s in row.get("streams", []):
                bw, lr = calculations.calc_bandwidth(s.get("packet_size_bytes"), s.get("period_ns"), link_dr)
                streams.append({**s, "bandwidth_Mbps": bw, "load_ratio": lr})
            workload.append({
                "talker_id": row["talker_id"],
                "switch_id": row["switch_id"],
                "listener_id": row["listener_id"],
                "num_streams": len(streams),
                "streams": streams,
                "total_bandwidth_Mbps": round(sum(s["bandwidth_Mbps"] for s in streams), 3),
                "total_load_ratio": round(sum(s["load_ratio"] for s in streams), 6),
            })

        return {
            "run_id": 0,
            "topology": {
                "topology_id": topology_id,
                "num_talkers": n_talkers,
                "num_switches": n_switches,
                "num_listeners": n_listeners,
                "link_datarate_Mbps": link_dr,
                "device_model": device_model,
                "num_tx_queues": num_tx_queues,
                "gcl_cycle_time_ns": cycle_ns,
                "edges": edges,
            },
            "workload": workload,
            # graph_builder.build_graph() reads this for training labels even
            # during inference; predict() itself never consumes the labels.
            "gcl": [],
        }

    # ── model inference ──────────────────────────────────────────────────────

    def _run_model(self, run: dict, model_path: str) -> list:
        if str(_INFERENCE_DIR) not in sys.path:
            sys.path.insert(0, str(_INFERENCE_DIR))
        import gnn_model  # local import: keeps torch off the page-load path

        gnn_model.MODEL_PATH = model_path
        return gnn_model.predict(run)

    # ── validation ────────────────────────────────────────────────────────────

    def validate_gcl(self, run: dict, gcl: list) -> list[dict]:
        checks = []
        cycle_ns = run["topology"]["gcl_cycle_time_ns"]

        expected_parents = {f"T{i + 1}" for i in range(run["topology"]["num_talkers"])}
        expected_parents |= {e["port_id"] for e in run["topology"]["edges"] if "port_id" in e}
        got_parents = {g["parent_id"] for g in gcl}
        checks.append({
            "name": "All nodes scheduled",
            "passed": expected_parents.issubset(got_parents),
            "detail": f"{len(got_parents & expected_parents)}/{len(expected_parents)} expected nodes have a GCL entry",
        })

        bitmask_ok = all(
            len(seq["gate_bitmask"]) == 4 and set(seq["gate_bitmask"]) <= {"0", "1"}
            for g in gcl for seq in g["gcl_sequences"]
        )
        checks.append({
            "name": "Gate bitmask format",
            "passed": bitmask_ok,
            "detail": "All gate_bitmask values are 4-bit binary strings" if bitmask_ok
            else "One or more gate_bitmask values are malformed",
        })

        duration_ok = all(seq["duration_ns"] > 0 for g in gcl for seq in g["gcl_sequences"])
        checks.append({
            "name": "Positive gate durations",
            "passed": duration_ok,
            "detail": "All duration_ns values are positive" if duration_ok
            else "One or more duration_ns values are zero or negative",
        })

        drift_msgs = []
        cycle_ok = True
        for g in gcl:
            total = sum(seq["duration_ns"] for seq in g["gcl_sequences"])
            drift = abs(total - cycle_ns) / cycle_ns if cycle_ns else 0
            if drift > 0.05:
                cycle_ok = False
                drift_msgs.append(f"{g['parent_id']}: {total:,}ns vs cycle {cycle_ns:,}ns ({drift:.1%} drift)")
        checks.append({
            "name": "Cycle-time coverage",
            "passed": cycle_ok,
            "detail": "All node schedules sum to within 5% of the cycle time" if cycle_ok
            else "; ".join(drift_msgs),
        })

        return checks

    # ── XML conversion ───────────────────────────────────────────────────────

    def gcl_to_xml(self, run: dict, gcl: list) -> str:
        return netconf_yang.gcl_to_xml(run, gcl)

    def validate_xml(self, xml_str: str) -> list[dict]:
        return netconf_yang.validate_xml(xml_str)

    # ── readiness (pre-generation) ───────────────────────────────────────────

    def readiness(self, topology_loaded: bool, workload_rows: list, model_available: bool) -> list[dict]:
        total_streams = sum(len(r.get("streams", [])) for r in workload_rows)
        return [
            {
                "name": "Network topology",
                "passed": topology_loaded,
                "detail": "Loaded" if topology_loaded else "Not loaded — configure it on Topology Manager",
            },
            {
                "name": "Workload",
                "passed": topology_loaded and total_streams > 0,
                "detail": f"{total_streams} stream(s) configured" if total_streams > 0
                else "No streams configured",
            },
            {
                "name": "Model",
                "passed": model_available,
                "detail": "Checkpoint available" if model_available else "No trained model (*.pt) found",
            },
        ]

    # ── end-to-end pipeline ───────────────────────────────────────────────────

    def generate(self, topo_params: dict, workload_rows: list[dict], model_path: str) -> dict:
        """Run the full topology → GCL → XML pipeline, recording per-step status."""
        result: dict = {"run": None, "gcl": None, "xml": None, "steps": [], "error": None}
        logger.info(
            LogCategory.MODEL, "generation_started",
            "Configuration generation pipeline started", model_path=model_path,
        )

        try:
            run = self.build_run(topo_params, workload_rows)
        except Exception as e:
            result["steps"].append({"name": "Build run payload", "passed": False, "detail": str(e)})
            result["error"] = str(e)
            logger.error(LogCategory.TOPOLOGY, "build_run_failed", "Failed to build run payload", exc=e)
            return result

        result["run"] = run
        n_streams = sum(len(w["streams"]) for w in run["workload"])
        result["steps"].append({
            "name": "Build run payload", "passed": True,
            "detail": f"{run['topology']['num_talkers']} talker(s), {n_streams} stream(s)",
        })

        try:
            gcl = self._run_model(run, model_path)
            for entry in gcl:
                for idx, seq in enumerate(entry["gcl_sequences"]):
                    seq["sequence_index"] = idx
        except Exception as e:
            result["steps"].append({"name": "GCL generation", "passed": False, "detail": str(e)})
            result["error"] = str(e)
            logger.error(
                LogCategory.MODEL, "inference_failed", "GNN model inference failed",
                exc=e, model_path=model_path,
            )
            return result

        result["gcl"] = gcl
        result["steps"].append({
            "name": "GCL generation", "passed": True,
            "detail": f"{len(gcl)} node schedule(s) produced",
        })
        logger.success(
            LogCategory.MODEL, "inference_completed",
            f"GNN inference produced {len(gcl)} node schedule(s)",
            model_path=model_path, node_count=len(gcl),
        )

        gcl_checks = self.validate_gcl(run, gcl)
        result["steps"].extend(gcl_checks)
        self._log_failed_checks(gcl_checks)

        try:
            xml_str = self.gcl_to_xml(run, gcl)
        except Exception as e:
            result["steps"].append({"name": "XML conversion", "passed": False, "detail": str(e)})
            result["error"] = str(e)
            logger.error(LogCategory.EXPORT, "xml_conversion_failed", "Failed to convert GCL to XML", exc=e)
            return result

        result["xml"] = xml_str
        result["steps"].append({
            "name": "XML conversion", "passed": True,
            "detail": f"{len(xml_str):,} characters generated",
        })
        xml_checks = self.validate_xml(xml_str)
        result["steps"].extend(xml_checks)
        self._log_failed_checks(xml_checks)

        if all(s["passed"] for s in result["steps"]):
            logger.success(
                LogCategory.EXPORT, "generation_completed",
                "Configuration generation completed with all checks passed",
            )
        else:
            failed = [s["name"] for s in result["steps"] if not s["passed"]]
            logger.warning(
                LogCategory.VALIDATION, "generation_completed_with_failures",
                f"Configuration generation completed but {len(failed)} check(s) failed",
                failed_checks=failed,
            )

        return result

    def _log_failed_checks(self, checks: list[dict]) -> None:
        for c in checks:
            if not c["passed"]:
                logger.warning(
                    LogCategory.VALIDATION, "check_failed",
                    f"Validation check failed: {c['name']}", detail=c.get("detail"),
                )
