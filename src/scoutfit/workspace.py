"""Local, atomic user records. Files never leave the project automatically."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"Formato de registros inválido: {path.name}")
    return value


def write_records(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as stream:
        json.dump(rows, stream, ensure_ascii=False, indent=2, allow_nan=False)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def player_key(player: dict, metadata: dict) -> str:
    return ":".join(
        str(value)
        for value in (
            metadata.get("provider", "statsbomb"),
            player["competition_id"],
            player["season_id"],
            player["player_id"],
        )
    )


def save_favorite(path: Path, player: dict, metadata: dict, note: str | None = None):
    if note is not None and len(note) > 4000:
        raise ValueError("La nota no puede superar los 4000 caracteres")
    identity = player_key(player, metadata)
    rows = load_records(path)
    existing = next((row for row in rows if row.get("key") == identity), None)
    note = note if note is not None else (existing["note"] if existing else "")
    record = {
        "key": identity,
        "player_id": int(player["player_id"]),
        "profile_id": player["profile_id"],
        "player_name": player["player_name"],
        "team_at_save": player["team_name"],
        "role": player["role"],
        "provider": metadata.get("provider", "statsbomb"),
        "competition_id": int(player["competition_id"]),
        "season_id": int(player["season_id"]),
        "snapshot": metadata.get("snapshot", "historical"),
        "note": note,
        "saved_at": datetime.now(UTC).isoformat(),
    }
    if existing:
        record["saved_at"] = existing["saved_at"]
    rows = [row for row in rows if row.get("key") != identity]
    write_records(path, [*rows, record])


def remove_favorite(path: Path, identity: str):
    write_records(path, [row for row in load_records(path) if row.get("key") != identity])


def save_judgment(path: Path, record: dict):
    required = {"snapshot", "reference_id", "candidate_id", "relevance", "note"}
    if not required <= record.keys() or record["relevance"] not in (0, 1, 2):
        raise ValueError("Valoración inválida: usa relevancia 0, 1 o 2")
    if record["reference_id"] == record["candidate_id"]:
        raise ValueError("La referencia no puede evaluarse contra sí misma")
    if len(str(record["note"])) > 4000:
        raise ValueError("Nota demasiado larga")
    rows = load_records(path)
    identity = (record["snapshot"], record["reference_id"], record["candidate_id"])
    rows = [
        row
        for row in rows
        if (row.get("snapshot"), row.get("reference_id"), row.get("candidate_id")) != identity
    ]
    write_records(path, [*rows, {**record, "reviewed_at": datetime.now(UTC).isoformat()}])


def import_reviews(path: Path, csv_path: Path, snapshot: str, profiles) -> int:
    """Validate the whole CSV before a single atomic write. Blank grades remain unreviewed."""
    import pandas as pd

    frame = pd.read_csv(
        csv_path,
        keep_default_na=False,
        encoding="utf-8-sig",
        dtype={"snapshot": str, "reference_id": str, "candidate_id": str},
    )
    required = {"snapshot", "reference_id", "candidate_id", "relevance", "note"}
    if not required <= set(frame):
        raise ValueError("El CSV no tiene las columnas requeridas de valoración")
    known = profiles.set_index("profile_id")
    records, seen = [], set()
    for row in frame.to_dict("records"):
        if str(row["relevance"]).strip() == "":
            continue
        value = float(row["relevance"])
        if value not in (0, 1, 2) or row["snapshot"] != snapshot or not str(row["note"]).strip():
            raise ValueError("Relevancia, consulta o justificación inválida")
        ref, candidate = row["reference_id"], row["candidate_id"]
        if ref not in known.index or candidate not in known.index or ref == candidate:
            raise ValueError("Pareja de jugadores inválida")
        for column in ("role", "competition_id", "season_id"):
            if known.loc[ref, column] != known.loc[candidate, column]:
                raise ValueError("Los jugadores no pertenecen al mismo grupo comparable")
        identity = (snapshot, ref, candidate)
        if identity in seen:
            raise ValueError("Pareja duplicada en el CSV")
        seen.add(identity)
        records.append(
            {
                "snapshot": snapshot,
                "reference_id": ref,
                "candidate_id": candidate,
                "relevance": int(value),
                "note": str(row["note"]).strip(),
                "reviewer": str(row.get("reviewer", "CSV local")),
                "reviewed_at": datetime.now(UTC).isoformat(),
            }
        )
    if records:
        old = [
            row
            for row in load_records(path)
            if (row.get("snapshot"), row.get("reference_id"), row.get("candidate_id")) not in seen
        ]
        write_records(path, [*old, *records])
    return len(records)
