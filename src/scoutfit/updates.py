"""Stage, validate, compare and atomically activate a fresh ESPN dataset."""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scoutfit.datasets import ESPN_FEATURES, activate, active_directory
from scoutfit.espn import build_current, download_current


class UpdateError(RuntimeError):
    pass


class UpdateInProgress(UpdateError):
    pass


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def update_lock(path):
    """OS locks release on process exit; an abandoned file cannot block future runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise UpdateInProgress(
                "Ya hay una actualización en curso en esta instalación."
            ) from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def same_scope(before_meta, after_meta):
    return all(
        before_meta.get(k) == after_meta.get(k)
        for k in ("provider", "competition_id", "season_id", "metric_set")
    )


def validate_dataset(frame, metadata, previous=None, previous_meta=None):
    if metadata.get("provider") != "espn" or metadata.get("competition_id") != 740:
        raise ValueError("La descarga no corresponde a LaLiga masculina de ESPN.")
    if metadata.get("gender") != "male" or metadata.get("partial"):
        raise ValueError("La descarga no confirma el conjunto masculino completo.")
    teams = metadata.get("roster_teams", [])
    team_ids = {int(t["id"]) for t in teams}
    if metadata.get("team_count") != 20 or len(teams) != 20 or len(team_ids) != 20:
        raise ValueError("El catálogo debe contener los 20 clubes distintos de LaLiga.")
    if (
        frame.empty
        or frame["profile_id"].duplicated().any()
        or frame["player_id"].duplicated().any()
    ):
        raise ValueError("Los perfiles están vacíos o contienen identidades ambiguas.")
    if not set(frame["team_id"]).issubset(team_ids):
        raise ValueError("Hay perfiles asociados a clubes fuera del catálogo.")
    if (
        not frame["competition_id"].eq(740).all()
        or not frame["season_id"].eq(metadata["season_id"]).all()
    ):
        raise ValueError("Hay perfiles de otra liga o temporada.")
    if not frame["provider"].eq("espn").all() or not frame["gender"].eq("male").all():
        raise ValueError("Los perfiles tienen otra fuente o género.")
    if set(metadata.get("features", {})) != set(ESPN_FEATURES):
        raise ValueError("Las métricas descargadas no coinciden con las esperadas.")
    values = frame[["minutes", "matches", *ESPN_FEATURES]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (frame["minutes"] <= 0).any():
        raise ValueError("Se han encontrado métricas incompletas, negativas o minutos no válidos.")
    if (frame["completion_pct"] > 100).any() or (frame["matches"] % 1 != 0).any():
        raise ValueError("Hay porcentajes o conteos de partidos no válidos.")
    requested = len(metadata.get("player_ids_requested", []))
    if not requested or len(frame) / requested < 0.85:
        raise ValueError(
            "Menos del 85 % de los jugadores consultados tiene estadísticas completas."
        )
    if (
        previous is not None
        and same_scope(previous_meta, metadata)
        and len(frame) < len(previous) * 0.8
    ):
        raise ValueError("La cobertura ha caído más del 20 % respecto a la consulta activa.")


def compare_datasets(before, before_meta, after, after_meta):
    report = {
        "before_snapshot": before_meta.get("snapshot") if before_meta else None,
        "after_snapshot": after_meta["snapshot"],
        "before_consulted_at": before_meta.get("downloaded_at") if before_meta else None,
        "after_consulted_at": after_meta["downloaded_at"],
        "season": after_meta["season"],
        "profiles": len(after),
        "team_count": after_meta["team_count"],
        "excluded_profiles": len(after_meta.get("excluded_profiles", [])),
        "comparable": before is not None and same_scope(before_meta, after_meta),
        "new_profiles": [],
        "removed_profiles": [],
        "team_changes": [],
        "statistics_changes": [],
        "identity_changes": [],
    }
    if not report["comparable"]:
        report["comparison_note"] = (
            "Primera consulta: no hay un conjunto anterior comparable."
            if before is None
            else "Ha cambiado la fuente, liga, temporada o definición de métricas. "
            "No se infieren traspasos ni variaciones entre conjuntos distintos."
        )
        return report
    old, new = before.set_index("player_id"), after.set_index("player_id")

    def identity(pid, player):
        return {
            "player_id": int(pid),
            "player_name": str(player["player_name"]),
            "team_name": str(player["team_name"]),
            "minutes": float(player["minutes"]),
        }

    report["new_profiles"] = [
        identity(pid, new.loc[pid]) for pid in sorted(set(new.index) - set(old.index))
    ]
    report["removed_profiles"] = [
        identity(pid, old.loc[pid]) for pid in sorted(set(old.index) - set(new.index))
    ]
    for pid in sorted(set(old.index) & set(new.index)):
        a, b = old.loc[pid], new.loc[pid]
        if a["team_id"] != b["team_id"]:
            report["team_changes"].append(
                {
                    "player_id": int(pid),
                    "player_name": str(b["player_name"]),
                    "previous_team": str(a["team_name"]),
                    "current_team": str(b["team_name"]),
                }
            )
        for field in ("player_name", "role", "team_name"):
            if a[field] != b[field]:
                report["identity_changes"].append(
                    {
                        "player_id": int(pid),
                        "player_name": str(b["player_name"]),
                        "field": field,
                        "previous_value": str(a[field]),
                        "current_value": str(b[field]),
                    }
                )
        changed = {}
        for field in ("minutes", "matches", *ESPN_FEATURES):
            if not np.isclose(float(a[field]), float(b[field]), rtol=1e-9, atol=1e-9):
                changed[field] = {"before": float(a[field]), "after": float(b[field])}
        if changed:
            report["statistics_changes"].append(
                {
                    **identity(pid, b),
                    "previous_minutes": float(a["minutes"]),
                    "minutes_delta": float(b["minutes"] - a["minutes"]),
                    "changes": changed,
                    "correction": bool(b["minutes"] < a["minutes"] or b["matches"] < a["matches"]),
                }
            )
    return report


def update_dataset(root: Path, progress=None, season=None):
    root = root.resolve()
    updates = root / "data/updates"
    processed = root / "data/processed"
    with update_lock(updates / "update.lock"):
        started = datetime.now(UTC).isoformat()
        pointer = processed / "active.json"
        original_pointer = pointer.read_bytes() if pointer.exists() else None
        before, before_meta = None, None
        directory = active_directory(processed)
        if (directory / "profiles.csv").exists() and (directory / "metadata.json").exists():
            before = pd.read_csv(directory / "profiles.csv")
            before_meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        try:
            with tempfile.TemporaryDirectory(
                prefix="staging-", dir=updates, ignore_cleanup_errors=True
            ) as temp:
                stage = Path(temp).resolve()
                if not stage.is_relative_to(updates.resolve()):
                    raise ValueError(
                        "La preparación debe permanecer dentro del directorio de actualizaciones."
                    )
                manifest = download_current(
                    stage / "raw", refresh=True, season=season, progress=progress
                )
                frame, metadata = build_current(
                    manifest, stage / "processed", activate_output=False, progress=progress
                )
                if progress:
                    progress("validation", 0, 1)
                validate_dataset(frame, metadata, before, before_meta)
                report = compare_datasets(before, before_meta, frame, metadata)
                report.update(
                    status="success", started_at=started, completed_at=datetime.now(UTC).isoformat()
                )
                staged_processed = stage / "processed/espn" / metadata["snapshot"]
                atomic_json(staged_processed / "update_report.json", report)
                if progress:
                    progress("publishing", 0, 1)
                if (pointer.read_bytes() if pointer.exists() else None) != original_pointer:
                    raise UpdateError(
                        "Otro proceso ha cambiado la consulta activa. Vuelve a actualizar."
                    )
                destination_raw = (root / "data/raw/espn" / metadata["snapshot"]).resolve()
                destination_processed = (processed / "espn" / metadata["snapshot"]).resolve()
                for destination in (destination_raw, destination_processed):
                    if not destination.is_relative_to(root / "data") or destination.exists():
                        raise ValueError(
                            "El destino de la consulta no es nuevo o está fuera del proyecto."
                        )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                manifest.parent.rename(destination_raw)
                staged_processed.rename(destination_processed)
                latest = root / "data/raw/espn/latest.json"
                previous_latest = (
                    json.loads(latest.read_text(encoding="utf-8")) if latest.exists() else None
                )
                atomic_json(latest, {"snapshot": metadata["snapshot"]})
                try:
                    activate(processed, destination_processed)
                except BaseException:
                    if previous_latest is None:
                        latest.unlink(missing_ok=True)
                    else:
                        atomic_json(latest, previous_latest)
                    raise
                # Audit failure must not turn a committed dataset into a reported failure.
                try:
                    atomic_json(updates / "last_attempt.json", report)
                except OSError:
                    pass
                return frame, metadata, report
        except Exception as exc:
            try:
                atomic_json(
                    updates / "last_attempt.json",
                    {
                        "status": "failed",
                        "started_at": started,
                        "completed_at": datetime.now(UTC).isoformat(),
                        "error": str(exc)[:1000],
                    },
                )
            except OSError:
                pass
            raise UpdateError(str(exc)) from exc
