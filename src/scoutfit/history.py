"""Real saved queries; aggregate changes are never presented as match-level data."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scoutfit.data import read_json


def discover_snapshots(processed: Path, metadata: dict) -> tuple[list[dict], list[str]]:
    snapshots, errors = [], []
    for path in sorted((processed / "espn").glob("*/metadata.json")):
        try:
            meta = read_json(path)
            if any(
                meta.get(k) != metadata.get(k)
                for k in ("provider", "competition_id", "season_id", "metric_set")
            ):
                continue
            when = datetime.fromisoformat(meta["downloaded_at"].replace("Z", "+00:00"))
            profiles = path.parent / "profiles.csv"
            if not profiles.exists():
                raise ValueError("Falta profiles.csv")
            snapshots.append({"directory": path.parent, "metadata": meta, "time": when})
        except (OSError, KeyError, ValueError) as exc:
            errors.append(f"{path.parent.name}: {exc}")
    return sorted(snapshots, key=lambda row: row["time"]), errors


def player_timeline(snapshots: list[dict], player_id: int, features: dict) -> pd.DataFrame:
    rows = []
    for snapshot in snapshots:
        meta = snapshot["metadata"]
        profiles = pd.read_csv(snapshot["directory"] / "profiles.csv")
        selected = profiles.loc[profiles["player_id"] == player_id]
        row = {
            "snapshot": meta["snapshot"],
            "consulted_at": snapshot["time"],
            "status": "Disponible" if len(selected) == 1 else "No disponible o equipo ambiguo",
        }
        if len(selected) == 1:
            player = selected.iloc[0]
            row.update(
                {
                    "player_name": player["player_name"],
                    "player_id": int(player["player_id"]),
                    "team_id": int(player["team_id"]) if "team_id" in player else None,
                    "team_name": player["team_name"],
                    "minutes": player["minutes"],
                    "matches": player["matches"],
                    "inferred_role": player.get("inferred_role", ""),
                }
            )
            row.update({feature: player.get(feature, np.nan) for feature in features})
        rows.append(row)
    return pd.DataFrame(rows)


def interval_changes(timeline: pd.DataFrame, feature: str) -> pd.DataFrame:
    """A rate for the interval between two cumulative season queries, not a match."""
    rows = []
    for before, after in zip(timeline.to_dict("records"), timeline.to_dict("records")[1:]):
        row = {
            "from": before["consulted_at"],
            "to": after["consulted_at"],
            "minutes_added": np.nan,
            "interval_rate": np.nan,
            "status": "Sin datos comparables",
        }
        if before["status"] == after["status"] == "Disponible":
            old_minutes, new_minutes = before["minutes"], after["minutes"]
            added = new_minutes - old_minutes
            row["minutes_added"] = added
            old_value, new_value = before.get(feature, np.nan), after.get(feature, np.nan)
            if not all(np.isfinite(v) for v in (old_minutes, new_minutes, old_value, new_value)):
                pass
            elif added < 0:
                row["status"] = "Corrección del proveedor: disminuyen los minutos"
            elif added == 0:
                row["status"] = (
                    "Sin minutos nuevos"
                    if np.isclose(old_value, new_value)
                    else "Cambio estadístico sin minutos nuevos: posible corrección"
                )
            elif feature.endswith("_p90"):
                delta = new_value * new_minutes / 90 - old_value * old_minutes / 90
                if delta < -1e-6:
                    row["status"] = "Corrección del proveedor: disminuye un conteo acumulado"
                else:
                    row["interval_rate"] = max(0, delta) * 90 / added
                    row["status"] = "Tramo entre consultas; no es un partido individual"
            else:
                row["status"] = "Porcentaje acumulado: no se convierte en tasa del tramo"
        rows.append(row)
    return pd.DataFrame(rows)
