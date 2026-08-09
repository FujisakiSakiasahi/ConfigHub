"""Discovers trained model checkpoints and enriches them with metadata from index.md."""

import re
from pathlib import Path

_MODELS_DIR = Path(__file__).resolve().parent / "models"
_INDEX_PATH = _MODELS_DIR / "index.md"

_HEADING_RE = re.compile(r"^##\s+(\S+)\s*$")
_FIELD_RE = re.compile(r"^-\s*(\w+)\s*:\s*(.+)$")

# Architecture fields every checkpoint should carry; used to reconstruct
# GraphSAGENet with the right shape before load_state_dict. Falls back to
# these defaults (with a warning) when a checkpoint has no index.md entry,
# or when a specific field wasn't recorded.
DEFAULT_IN_CHANNELS = 14
DEFAULT_HIDDEN_CHANNELS = 64
DEFAULT_OUT_CHANNELS = 4

_ARCH_INT_FIELDS = ("in_channels", "hidden_channels", "out_channels")


def _parse_index(index_path: Path) -> dict[str, dict]:
    """Parse index.md into {model_id: {"name": ..., "version": ..., "description": ...,
    "in_channels": ..., "hidden_channels": ..., "out_channels": ..., "lr": ...,
    "epochs": ..., "batch_size": ...}}.

    Expected format, one section per model:
        ## <model_id>
        - name: <display name>
        - version: <version>
        - description: <short description>
        - in_channels: <int>
        - hidden_channels: <int>
        - out_channels: <int>
        - lr: <learning rate used to train this checkpoint>
        - epochs: <epochs used to train this checkpoint>
        - batch_size: <batch size used to train this checkpoint>
    """
    entries: dict[str, dict] = {}
    if not index_path.exists():
        return entries

    current_id = None
    for line in index_path.read_text(encoding="utf-8").splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            current_id = heading.group(1)
            entries[current_id] = {
                "name": "", "version": "", "description": "",
                "in_channels": None, "hidden_channels": None, "out_channels": None,
                "lr": "", "epochs": "", "batch_size": "",
            }
            continue
        if current_id is None:
            continue
        field = _FIELD_RE.match(line)
        if field:
            key, value = field.group(1).lower(), field.group(2).strip()
            if key not in entries[current_id]:
                continue
            if key in _ARCH_INT_FIELDS:
                try:
                    entries[current_id][key] = int(value)
                except ValueError:
                    entries[current_id][key] = None
            else:
                entries[current_id][key] = value

    return entries


def get_architecture(model_id: str) -> dict:
    """Return the {in_channels, hidden_channels, out_channels} GraphSAGENet
    shape documented for `model_id` in index.md.

    Falls back to the module defaults (with a printed warning naming the
    checkpoint) for any field missing from index.md, or for checkpoints with
    no entry at all.
    """
    meta = _parse_index(_INDEX_PATH).get(model_id, {})
    defaults = {
        "in_channels": DEFAULT_IN_CHANNELS,
        "hidden_channels": DEFAULT_HIDDEN_CHANNELS,
        "out_channels": DEFAULT_OUT_CHANNELS,
    }
    arch = {}
    for field, default in defaults.items():
        value = meta.get(field)
        if value is None:
            print(
                f"WARNING: no '{field}' recorded for checkpoint '{model_id}' in "
                f"index.md — falling back to default {field}={default}."
            )
            arch[field] = default
        else:
            arch[field] = value
    return arch


def list_models() -> list[dict]:
    """List trained model checkpoints (*.pt) found in this directory.

    Each checkpoint is enriched with metadata from index.md, keyed by model ID
    (the filename without extension). Checkpoints without a matching index.md
    entry fall back to the filename as their display name and default
    architecture.
    """
    metadata = _parse_index(_INDEX_PATH)
    models = []
    for p in sorted(_MODELS_DIR.glob("*.pt")):
        model_id = p.stem
        meta = metadata.get(model_id, {})
        models.append({
            "model_id": model_id,
            "name": meta.get("name") or model_id,
            "version": meta.get("version") or "—",
            "description": meta.get("description") or "",
            "in_channels": meta.get("in_channels") if meta.get("in_channels") is not None else DEFAULT_IN_CHANNELS,
            "hidden_channels": meta.get("hidden_channels") if meta.get("hidden_channels") is not None else DEFAULT_HIDDEN_CHANNELS,
            "out_channels": meta.get("out_channels") if meta.get("out_channels") is not None else DEFAULT_OUT_CHANNELS,
            "lr": meta.get("lr") or "",
            "epochs": meta.get("epochs") or "",
            "batch_size": meta.get("batch_size") or "",
            "path": str(p),
            "size_kb": round(p.stat().st_size / 1024, 1),
        })
    return models
