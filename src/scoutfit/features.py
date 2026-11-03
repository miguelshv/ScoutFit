"""Explicit football definitions and playing time from lineup intervals."""

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from scoutfit.data import read_json

FEATURES = {
    "passes_p90": "Pases intentados /90",
    "completion_pct": "Pases completados (%)",
    "progressive_passes_p90": "Pases progresivos /90",
    "progressive_carries_p90": "Conducciones progresivas /90",
    "final_third_entries_p90": "Entradas al último tercio /90",
    "box_entries_p90": "Entradas al área /90",
    "pressured_completions_p90": "Pases completados bajo presión /90",
    "pressures_p90": "Presiones /90",
    "defensive_actions_p90": "Entradas e intercepciones ganadas /90",
    "shots_p90": "Tiros /90",
}
COUNTS = [f.removesuffix("_p90") for f in FEATURES if f.endswith("_p90")]
PERIOD_START = {1: 0, 2: 45 * 60, 3: 90 * 60, 4: 105 * 60}
SET_PIECES = {"Corner", "Free Kick", "Goal Kick", "Kick Off", "Throw-in"}


def clock_seconds(value: str) -> float:
    parts = [float(p) for p in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"Reloj inválido: {value}")


def period_lengths(events: list[dict]) -> dict[int, float]:
    lengths = {}
    for event in events:
        period = event["period"]
        if period not in PERIOD_START:
            continue  # Shootouts have no playing time or profile actions.
        seconds = clock_seconds(event["timestamp"])
        lengths[period] = max(lengths.get(period, 0), seconds)
    if not lengths or any(p not in lengths for p in range(1, max(lengths) + 1)):
        raise ValueError("Periodos ausentes o discontinuos")
    return lengths


def role(position_id: int) -> str:
    if position_id == 1:
        return "Portería"
    if position_id in (3, 4, 5):
        return "Central"
    if position_id in (2, 6, 7, 8):
        return "Lateral / carrilero"
    if position_id in (9, 10, 11, 13, 14, 15):
        return "Mediocentro"
    if position_id in (12, 16, 17, 21):
        return "Banda"
    if position_id in (18, 19, 20):
        return "Mediapunta"
    if position_id in (22, 23, 24, 25):
        return "Delantera"
    raise ValueError(f"Posición no reconocida: {position_id}")


def player_minutes(player: dict, lengths: dict[int, float]) -> tuple[float, Counter]:
    def elapsed(clock, period):
        if clock is None:
            return sum(lengths.values())
        if period not in lengths:
            raise ValueError(f"Periodo de alineación no disponible: {period}")
        local = clock_seconds(clock) - PERIOD_START[period]
        local = min(max(local, 0), lengths[period])
        return sum(lengths[p] for p in lengths if p < period) + local

    intervals, roles, seen = [], Counter(), set()
    for position in player.get("positions", []):
        start = elapsed(position["from"], position["from_period"])
        end = elapsed(position.get("to"), position.get("to_period"))
        if end < start:
            raise ValueError("Intervalo de participación invertido")
        identity = (start, end, position["position_id"])
        if identity in seen:
            continue
        seen.add(identity)
        intervals.append((start, end))
        roles[role(position["position_id"])] += (end - start) / 60
    # Union prevents double-counting if a source repeats a position interval.
    minutes, previous_end = 0.0, 0.0
    for start, end in sorted(intervals):
        if start < previous_end - 1e-6:
            raise ValueError("Intervalos de participación solapados")
        minutes += max(0.0, end - max(start, previous_end)) / 60
        previous_end = max(previous_end, end)
    return minutes, roles


def valid_point(point) -> bool:
    return (
        isinstance(point, list)
        and len(point) >= 2
        and all(isinstance(v, (int, float)) and math.isfinite(v) for v in point[:2])
        and 0 <= point[0] <= 120
        and 0 <= point[1] <= 80
    )


def goal_distance(point: list) -> float:
    return math.hypot((120 - point[0]) * 105 / 120, (40 - point[1]) * 68 / 80)


def inside_box(point: list) -> bool:
    return point[0] >= 102 and 18 <= point[1] <= 62


def action_counts(event: dict) -> Counter:
    result = Counter()
    if event.get("period", 1) not in PERIOD_START:
        return result
    kind = event.get("type", {}).get("name")
    pass_data = event.get("pass", {})
    if kind == "Pass" and pass_data.get("type", {}).get("name") not in SET_PIECES:
        result["passes"] = 1
        completed = "outcome" not in pass_data
        result["completed_passes"] = int(completed)
        result["pressured_completions"] = int(completed and event.get("under_pressure", False))
        end = pass_data.get("end_location") if completed else None
    elif kind == "Carry":
        end = event.get("carry", {}).get("end_location")
    else:
        end = None
    start = event.get("location")
    if valid_point(start) and valid_point(end):
        progressive = goal_distance(start) - goal_distance(end) >= 10
        result["progressive_passes" if kind == "Pass" else "progressive_carries"] = int(progressive)
        result["final_third_entries"] = int(start[0] < 80 <= end[0])
        result["box_entries"] = int(not inside_box(start) and inside_box(end))
    result["pressures"] = int(kind == "Pressure")
    result["shots"] = int(kind == "Shot")
    tackle = (
        kind == "Duel"
        and event.get("duel", {}).get("type", {}).get("name") == "Tackle"
        and event.get("duel", {}).get("outcome", {}).get("name")
        in {"Won", "Success", "Success In Play", "Success Out"}
    )
    interception = kind == "Interception" and event.get("interception", {}).get("outcome", {}).get(
        "name"
    ) in {"Won", "Success", "Success In Play", "Success Out"}
    result["defensive_actions"] = int(tackle or interception)
    return result


def build_profiles(manifest_path: Path, output: Path) -> tuple[pd.DataFrame, dict]:
    manifest = read_json(manifest_path)
    source = manifest_path.parent
    players = {}
    observations = []
    excluded, used = [], []
    for mid in manifest["match_ids"]:
        for kind in ("events", "lineups"):
            relative = f"{kind}/{mid}.json"
            expected = manifest.get("sha256", {}).get(relative)
            if (
                expected
                and hashlib.sha256((source / relative).read_bytes()).hexdigest() != expected
            ):
                raise ValueError(f"SHA-256 no coincide: {relative}")
        events = read_json(source / f"events/{mid}.json")
        lineups = read_json(source / f"lineups/{mid}.json")
        try:
            lengths = period_lengths(events)
        except ValueError as exc:
            excluded.append({"match_id": mid, "errors": [{"reason": str(exc)}]})
            continue
        participants, errors = [], []
        for team in lineups:
            for player in team["lineup"]:
                try:
                    minutes, roles = player_minutes(player, lengths)
                except ValueError as exc:
                    errors.append(
                        {
                            "player_id": player["player_id"],
                            "player_name": player["player_name"],
                            "reason": str(exc),
                        }
                    )
                    continue
                if minutes > 0:
                    participants.append((team, player, minutes, roles))
        if errors:
            excluded.append({"match_id": mid, "errors": errors})
            continue
        used.append(mid)
        match_players = {}
        for team, player, minutes, roles in participants:
            key = (player["player_id"], team["team_id"])
            if key not in players:
                players[key] = {
                    "profile_id": f"{key[0]}:{key[1]}",
                    "player_id": key[0],
                    "player_name": player["player_name"],
                    "team_id": key[1],
                    "team_name": team["team_name"],
                    "minutes": 0.0,
                    "matches": 0,
                    "roles": Counter(),
                    "counts": Counter(),
                }
            record = players[key]
            record["minutes"] += minutes
            record["matches"] += 1
            record["roles"].update(roles)
            match_players[key] = {"minutes": minutes, "counts": Counter()}
        for event in events:
            key = (event.get("player", {}).get("id"), event.get("team", {}).get("id"))
            if key in match_players:
                counts = action_counts(event)
                players[key]["counts"].update(counts)
                match_players[key]["counts"].update(counts)
        for key, row in match_players.items():
            observations.append(
                {
                    "match_id": mid,
                    "profile_id": f"{key[0]}:{key[1]}",
                    "minutes": row["minutes"],
                    **dict(row["counts"]),
                }
            )
    rows = []
    for record in players.values():
        roles, counts = record.pop("roles"), record.pop("counts")
        record["role"] = roles.most_common(1)[0][0]
        record["role_share"] = roles[record["role"]] / sum(roles.values())
        record["competition_id"] = manifest["competition_id"]
        record["season_id"] = manifest["season_id"]
        for count in COUNTS:
            record[f"{count}_p90"] = counts[count] * 90 / record["minutes"]
        record["completion_pct"] = (
            100 * counts["completed_passes"] / counts["passes"] if counts["passes"] else 0.0
        )
        rows.append(record)
    if not rows:
        raise ValueError("No hay participaciones válidas")
    profiles = pd.DataFrame(rows).sort_values(["role", "player_name", "team_id"])
    output.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(output / "profiles.csv", index=False)
    pd.DataFrame(observations).fillna(0).to_csv(output / "player_matches.csv", index=False)
    manifest = {**manifest, "used_match_ids": used, "excluded_matches": excluded}
    (output / "quality_report.json").write_text(
        json.dumps(
            {
                "matches_downloaded": len(manifest["match_ids"]),
                "matches_used": len(used),
                "excluded_matches": excluded,
                "policy": "Excluir partido completo ante intervalos inválidos o solapados",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output / "metadata.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profiles, manifest
