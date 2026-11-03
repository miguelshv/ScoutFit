"""Dataset-specific metrics and atomic selection of a completed dataset."""

import json
import tempfile
from pathlib import Path

from scoutfit.features import FEATURES

ESPN_FEATURES = {
    "passes_p90": "Pases intentados /90",
    "completion_pct": "Pases completados (%)",
    "key_passes_p90": "Pases de tiro /90",
    "provider_progressive_carries_p90": "Conducciones progresivas (ESPN) /90",
    "crosses_p90": "Centros intentados /90",
    "long_balls_p90": "Pases largos intentados /90",
    "recoveries_p90": "Recuperaciones /90",
    "tackles_won_p90": "Entradas ganadas /90",
    "interceptions_p90": "Intercepciones /90",
    "shots_p90": "Tiros /90",
    "duels_won_p90": "Duelos ganados /90",
    "box_touches_p90": "Toques en área rival /90",
}


def metric_definitions(metadata: dict) -> dict[str, str]:
    return ESPN_FEATURES if metadata.get("provider") == "espn" else FEATURES


def active_directory(processed: Path) -> Path:
    pointer = processed / "active.json"
    if not pointer.exists():
        return processed
    relative = json.loads(pointer.read_text(encoding="utf-8"))["dataset"]
    candidate = (processed / relative).resolve()
    if not candidate.is_relative_to(processed.resolve()):
        raise ValueError("El conjunto activo debe estar dentro de data/processed")
    return candidate


def activate(processed: Path, dataset: Path):
    relative = dataset.resolve().relative_to(processed.resolve()).as_posix()
    processed.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=processed, suffix=".tmp", delete=False
    ) as stream:
        json.dump({"dataset": relative}, stream)
        temporary = Path(stream.name)
    try:
        temporary.replace(processed / "active.json")
    finally:
        temporary.unlink(missing_ok=True)
