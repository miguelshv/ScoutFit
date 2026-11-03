"""Current LaLiga rosters and season aggregates from ESPN's public JSON services.

These web-facing endpoints are not a supported API contract. Keep local snapshots,
validate their scope and schema, and fail explicitly when coverage changes.
"""

import hashlib
import json
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd

from scoutfit.data import fetch_bytes, read_json
from scoutfit.datasets import ESPN_FEATURES, activate
from scoutfit.roles import ROLE_MODEL_VERSION, infer_roles

SITE = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1"
CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues/esp.1"
COUNTS = {
    "passes_p90": "totalPasses",
    "key_passes_p90": "shotAssists",
    "provider_progressive_carries_p90": "progressiveCarries",
    "crosses_p90": "totalCrosses",
    "long_balls_p90": "totalLongBalls",
    "recoveries_p90": "recoveries",
    "tackles_won_p90": "effectiveTackles",
    "interceptions_p90": "interceptions",
    "shots_p90": "totalShots",
    "duels_won_p90": "duelsWon",
    "box_touches_p90": "touchesInOppBox",
}
ROLES = {"G": "Portería", "GK": "Portería", "D": "Defensa", "M": "Mediocentro", "F": "Delantera"}


def flatten_stats(payload: dict) -> dict[str, float]:
    values = {}
    for category in payload.get("splits", {}).get("categories", []):
        for stat in category.get("stats", []):
            value = stat.get("value")
            if isinstance(value, (int, float)) and math.isfinite(value):
                values[stat["name"]] = float(value)
    return values


def player_profile(athlete: dict, team: dict, statistics: dict, season: int) -> dict:
    pid = str(athlete["id"])
    gender = athlete.get("gender", "").upper()
    if gender != "MALE":
        raise ValueError("Género masculino no confirmado por la fuente")
    abbreviation = athlete.get("position", {}).get("abbreviation")
    if abbreviation not in ROLES:
        raise ValueError(f"Posición no reconocida: {abbreviation}")
    season_ref = statistics.get("season", {}).get("$ref", "")
    athlete_ref = statistics.get("athlete", {}).get("$ref", "")
    if not re.search(rf"/leagues/esp\.1/seasons/{season}(?:[/?]|$)", season_ref):
        raise ValueError("Estadísticas de otra liga o temporada")
    if not re.search(rf"/athletes/{re.escape(pid)}(?:[/?]|$)", athlete_ref):
        raise ValueError("Las estadísticas no corresponden al jugador")
    values = flatten_stats(statistics)
    required = {"minutes", "appearances", "accuratePasses", *COUNTS.values()}
    missing = required - values.keys()
    if missing:
        raise ValueError(f"Métricas ausentes: {', '.join(sorted(missing))}")
    if any(values[name] < 0 for name in required):
        raise ValueError("Conteos negativos")
    minutes = values["minutes"]
    if minutes <= 0:
        raise ValueError("Sin minutos de liga registrados")
    if values["accuratePasses"] > values["totalPasses"]:
        raise ValueError("Pases completados superiores a intentados")
    row = {
        "profile_id": f"espn:{pid}:{team['id']}",
        "player_id": int(pid),
        "player_name": athlete["displayName"],
        "team_id": int(team["id"]),
        "team_name": team["displayName"],
        "role": ROLES[abbreviation],
        "minutes": minutes,
        "matches": int(values["appearances"]),
        "role_share": None,
        "competition_id": 740,
        "season_id": season,
        "provider": "espn",
        "gender": "male",
        "source_url": f"https://www.espn.com/soccer/player/_/id/{pid}",
    }
    for feature, name in COUNTS.items():
        row[feature] = values[name] * 90 / minutes
    row["completion_pct"] = (
        100 * values["accuratePasses"] / values["totalPasses"] if values["totalPasses"] else 0.0
    )
    return row


def download_current(
    root: Path, refresh: bool = False, season: int | None = None, progress=None
) -> Path:
    root = root / "espn"
    latest = root / "latest.json"
    if latest.exists() and not refresh:
        existing = root / read_json(latest)["snapshot"] / "manifest.json"
        if season is None or read_json(existing)["season_id"] == season:
            print(
                f"Caché local: {existing}. Usa scoutfit update para consultar de nuevo.", flush=True
            )
            return existing
    now = datetime.now(UTC)
    snapshot = root / now.strftime("%Y%m%dT%H%M%S%fZ")
    snapshot.mkdir(parents=True, exist_ok=False)
    urls, checksums = {}, {}

    def get(relative: str, url: str):
        content = fetch_bytes(url)
        payload = json.loads(content)
        (snapshot / relative).parent.mkdir(parents=True, exist_ok=True)
        (snapshot / relative).write_bytes(content)
        # Each worker owns a unique key. No shared read-modify-write counter.
        urls[relative] = url
        checksums[relative] = hashlib.sha256(content).hexdigest()
        return payload

    if progress:
        progress("competition", 0, 1)
    scoreboard = get("scoreboard.json", f"{SITE}/scoreboard")
    season_info = scoreboard["leagues"][0]["season"]
    year = int(season or season_info["year"])
    team_payload = get("teams.json", f"{SITE}/teams?season={year}&limit=100")
    league = team_payload["sports"][0]["leagues"][0]
    if str(league.get("id")) != "740" or league.get("season", {}).get("year") != year:
        raise ValueError("El catálogo no corresponde a LaLiga y la temporada solicitada")
    teams = [entry["team"] for entry in league["teams"]]
    if len(teams) != 20 or len({str(t["id"]) for t in teams}) != 20:
        raise ValueError("Se esperaban 20 equipos distintos de LaLiga; no se publica la descarga")
    rosters = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = {
            executor.submit(
                get, f"rosters/{t['id']}.json", f"{SITE}/teams/{t['id']}/roster?season={year}"
            ): t
            for t in teams
        }
        for index, job in enumerate(as_completed(jobs), 1):
            team = jobs[job]
            payload = job.result()
            if payload.get("season", {}).get("year") != year:
                raise ValueError(f"Temporada de plantilla incorrecta: {team['displayName']}")
            if str(payload.get("team", {}).get("id")) != str(team["id"]):
                raise ValueError(f"Equipo de plantilla incorrecto: {team['displayName']}")
            if not payload.get("athletes"):
                raise ValueError(f"Plantilla vacía: {team['displayName']}")
            rosters[str(team["id"])] = payload
            if progress:
                progress("rosters", index, len(jobs))
    player_ids = set()
    for payload in rosters.values():
        for athlete in payload["athletes"]:
            if athlete.get("position", {}).get("abbreviation") in {"G", "GK"}:
                continue
            appearances = flatten_stats(athlete.get("statistics", {})).get("appearances")
            if appearances != 0:
                player_ids.add(str(athlete["id"]))
    print(
        f"LaLiga {year}/{year + 1}: 20 equipos, {len(player_ids)} jugadores con apariciones "
        "o sin conteo de apariciones disponible",
        flush=True,
    )
    unavailable = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = {
            executor.submit(
                get,
                f"statistics/{pid}.json",
                f"{CORE}/seasons/{year}/types/1/athletes/{pid}/statistics/0",
            ): pid
            for pid in sorted(player_ids)
        }
        for index, job in enumerate(as_completed(jobs), 1):
            pid = jobs[job]
            try:
                job.result()
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                unavailable[pid] = "Sin estadísticas públicas (HTTP 404)"
            if index % 40 == 0 or index == len(jobs):
                print(f"  {index}/{len(jobs)} estadísticas consultadas", flush=True)
            if progress and (index == 1 or index % 10 == 0 or index == len(jobs)):
                progress("statistics", index, len(jobs))
    if not player_ids or len(unavailable) / len(player_ids) > 0.15:
        raise ValueError("Cobertura de estadísticas insuficiente; se conserva el conjunto anterior")
    manifest = {
        "provider": "espn",
        "source": "ESPN",
        "competition": "LaLiga masculina",
        "competition_id": 740,
        "season_id": year,
        "season": f"{year}/{year + 1}",
        "gender": "male",
        "snapshot": snapshot.name,
        "downloaded_at": now.isoformat(),
        "download_finished_at": datetime.now(UTC).isoformat(),
        "provider_timestamps": {tid: p.get("timestamp") for tid, p in rosters.items()},
        "team_count": len(teams),
        "player_ids_requested": sorted(player_ids),
        "unavailable_statistics": unavailable,
        "sha256": checksums,
        "urls": urls,
        "partial": False,
        "metric_set": "espn_season_v1",
        "team_assignment": "Plantilla consultada en ESPN",
        "statistics_scope": "Jugador, liga y temporada; puede incluir otro club de la temporada",
    }
    (snapshot / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary = root / "latest.tmp"
    temporary.write_text(json.dumps({"snapshot": snapshot.name}), encoding="utf-8")
    temporary.replace(latest)
    return snapshot / "manifest.json"


def latest_manifest(raw: Path) -> Path:
    name = read_json(raw / "espn/latest.json")["snapshot"]
    if Path(name).name != name:
        raise ValueError("Identificador de descarga inválido")
    return raw / "espn" / name / "manifest.json"


def build_current(
    manifest_path: Path, processed: Path, *, activate_output: bool = True, progress=None
) -> tuple[pd.DataFrame, dict]:
    manifest = read_json(manifest_path)
    snapshot = manifest_path.parent
    for relative, expected in manifest["sha256"].items():
        if hashlib.sha256((snapshot / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"SHA-256 no coincide: {relative}")
    league = read_json(snapshot / "teams.json")["sports"][0]["leagues"][0]
    rows, excluded, memberships, roster_total = [], [], [], 0
    for index, entry in enumerate(league["teams"], 1):
        team = entry["team"]
        roster = read_json(snapshot / f"rosters/{team['id']}.json")
        for athlete in roster["athletes"]:
            roster_total += 1
            if athlete.get("position", {}).get("abbreviation") in {"G", "GK"}:
                continue
            pid = str(athlete["id"])
            memberships.append(pid)
            path = snapshot / f"statistics/{pid}.json"
            try:
                if not path.exists():
                    raise ValueError("Sin apariciones o estadísticas de liga disponibles")
                rows.append(player_profile(athlete, team, read_json(path), manifest["season_id"]))
            except ValueError as exc:
                excluded.append(
                    {
                        "player_id": pid,
                        "player_name": athlete["displayName"],
                        "team_name": team["displayName"],
                        "reason": str(exc),
                    }
                )
        if progress:
            progress("profiles", index, len(league["teams"]))
    ambiguous = {pid for pid, count in Counter(memberships).items() if count > 1}
    for row in rows:
        if str(row["player_id"]) in ambiguous:
            excluded.append(
                {
                    "player_id": str(row["player_id"]),
                    "player_name": row["player_name"],
                    "team_name": row["team_name"],
                    "reason": "Jugador presente en más de una plantilla; equipo ambiguo",
                }
            )
    rows = [row for row in rows if str(row["player_id"]) not in ambiguous]
    if not rows:
        raise ValueError("No hay perfiles válidos; se conserva el conjunto anterior")
    frame = pd.DataFrame(rows).sort_values(["role", "player_name", "team_id"])
    frame = infer_roles(frame)
    manifest.update(
        {
            "roster_players": roster_total,
            "profiles": len(frame),
            "excluded_profiles": excluded,
            "features": ESPN_FEATURES,
            "role_model_version": ROLE_MODEL_VERSION,
            "profiles_with_inferred_role": int(frame["inferred_role"].ne("").sum()),
            "roster_teams": [
                {"id": t["team"]["id"], "name": t["team"]["displayName"]} for t in league["teams"]
            ],
        }
    )
    quality = {
        "roster_players": roster_total,
        "profiles_used": len(frame),
        "excluded_profiles": excluded,
        "policy": "Sin imputación de métricas; excluir registros incompletos o ambiguos",
    }
    output = processed / "espn" / manifest["snapshot"]
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "profiles.csv", index=False)
    (output / "metadata.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "quality_report.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if activate_output:
        activate(processed, output)
    return frame, manifest
