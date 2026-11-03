"""Identity-based changes in real saved season queries, without filling gaps."""

import numpy as np
import pandas as pd

from scoutfit.history import discover_snapshots
from scoutfit.updates import same_scope


def compare_player(before, after, features):
    old_available = before is not None
    new_available = after is not None
    result = {
        "status": "Sin datos utilizables",
        "before_available": old_available,
        "after_available": new_available,
        "team_before": str(before["team_name"]) if old_available else None,
        "team_after": str(after["team_name"]) if new_available else None,
        "team_changed": False,
        "minutes_delta": None,
        "matches_delta": None,
        "changed_metrics": 0,
        "incomplete_values": 0,
        "possible_correction": False,
        "metrics": [],
    }
    if not old_available or not new_available:
        result["status"] = (
            "Ahora disponible"
            if new_available
            else "Ya no disponible"
            if old_available
            else "Sin datos utilizables"
        )
        return result
    result["team_changed"] = bool(
        pd.notna(before.get("team_id"))
        and pd.notna(after.get("team_id"))
        and before["team_id"] != after["team_id"]
    )
    for feature in ("minutes", "matches", *features):
        old, new = float(before.get(feature, np.nan)), float(after.get(feature, np.nan))
        valid = np.isfinite(old) and np.isfinite(new)
        result["incomplete_values"] += int(not valid)
        changed = bool(not np.isclose(old, new, rtol=1e-9, atol=1e-9)) if valid else False
        delta = float(new - old) if valid else None
        if feature in ("minutes", "matches"):
            result[f"{feature}_delta"] = delta
            if delta is not None and delta < 0:
                result["possible_correction"] = True
        else:
            result["changed_metrics"] += int(changed)
            if valid and feature.endswith("_p90"):
                old_count = old * float(before["minutes"]) / 90
                new_count = new * float(after["minutes"]) / 90
                if new_count < old_count - 1e-6:
                    result["possible_correction"] = True
            result["metrics"].append(
                {
                    "feature": feature,
                    "metric": features[feature],
                    "before": old if np.isfinite(old) else None,
                    "after": new if np.isfinite(new) else None,
                    "delta": delta,
                    "changed": changed,
                    "unit": "pp" if feature.endswith("_pct") else "/90",
                }
            )
    changed = (
        result["changed_metrics"] > 0
        or result["team_changed"]
        or result["minutes_delta"] not in (None, 0)
        or result["matches_delta"] not in (None, 0)
        or before["team_name"] != after["team_name"]
    )
    result["status"] = (
        "Datos incompletos"
        if result["incomplete_values"]
        else "Con cambios"
        if changed
        else "Sin cambios"
    )
    return result


def unique_player(frame, player_id):
    selected = frame.loc[frame.player_id.eq(player_id)]
    return selected.iloc[0] if len(selected) == 1 else None


def snapshot_frames(processed, metadata):
    snapshots, errors = discover_snapshots(processed, metadata)
    readable = []
    for snapshot in snapshots:
        try:
            frame = pd.read_csv(snapshot["directory"] / "profiles.csv")
            readable.append({**snapshot, "profiles": frame})
        except (OSError, ValueError) as exc:
            errors.append(f"{snapshot['metadata']['snapshot']}: {exc}")
    return readable, errors


def project_changes(project, profiles, metadata, snapshots, features):
    """Compare to each candidate's actual saved baseline, never another season."""
    catalog = {s["metadata"]["snapshot"]: s for s in snapshots}
    rows = []
    active_scope = {
        "provider": metadata.get("provider", "statsbomb"),
        "competition_id": metadata.get(
            "competition_id", int(profiles.iloc[0]["competition_id"]) if len(profiles) else None
        ),
        "season_id": metadata.get(
            "season_id", int(profiles.iloc[0]["season_id"]) if len(profiles) else None
        ),
    }
    for candidate in project["candidates"]:
        row = {
            "key": candidate["key"],
            "player_id": candidate["player_id"],
            "player_name": candidate["player_name"],
            "baseline_snapshot": candidate["snapshot"],
            "current_snapshot": metadata.get("snapshot"),
            "status": "Sin consulta de origen comparable",
            "team_before": candidate["team_at_save"],
            "team_after": None,
            "minutes_delta": None,
            "matches_delta": None,
            "changed_metrics": None,
            "possible_correction": False,
            "team_changed": False,
        }
        compatible = all(
            candidate.get(k) == active_scope.get(k)
            for k in ("provider", "competition_id", "season_id")
        )
        if not compatible:
            row["status"] = "Otra fuente, liga o temporada"
        else:
            current = unique_player(profiles, candidate["player_id"])
            row["team_after"] = str(current["team_name"]) if current is not None else None
            baseline = catalog.get(candidate["snapshot"])
            if candidate["snapshot"] == metadata.get("snapshot"):
                row["status"] = "Misma consulta al guardar"
            elif baseline and same_scope(baseline["metadata"], metadata):
                if baseline["time"] > pd.Timestamp(metadata["downloaded_at"]):
                    row["status"] = "Origen posterior a la consulta activa"
                else:
                    old = unique_player(baseline["profiles"], candidate["player_id"])
                    report = compare_player(old, current, features)
                    row.update({k: v for k, v in report.items() if k != "metrics"})
        rows.append(row)
    return pd.DataFrame(rows)
