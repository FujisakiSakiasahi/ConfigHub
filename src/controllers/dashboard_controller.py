import pandas as pd

from src.layers.helperService import converters
from src.layers.inferenceService import models as model_registry


class DashboardController:
    """Bridge between the dashboard view and service layers."""

    # ── model discovery ──────────────────────────────────────────────────────

    def list_models(self) -> list[dict]:
        return model_registry.list_models()

    def models_to_dataframe(self, models: list[dict]) -> pd.DataFrame:
        return converters.models_to_df(models)

    # ── overview summary ─────────────────────────────────────────────────────

    def get_summary(self, topology_loaded: bool, workload_loaded: bool) -> dict:
        models = self.list_models()
        return {
            "models": models,
            "model_count": len(models),
            "topology_loaded": topology_loaded,
            "workload_loaded": workload_loaded,
        }
