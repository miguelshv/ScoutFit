"""Optional biographical facts from the same checksum-verified roster snapshot."""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def media_url(value):
    if not isinstance(value, str):
        return ""
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.netloc == "a.espncdn.com" else ""


def biography(athlete, team, consulted_at):
    birth, age = "", None
    try:
        day = datetime.fromisoformat(athlete.get("dateOfBirth", "").replace("Z", "+00:00")).date()
        consulted = datetime.fromisoformat(consulted_at.replace("Z", "+00:00")).date()
        computed = (
            consulted.year - day.year - ((consulted.month, consulted.day) < (day.month, day.day))
        )
        if 0 <= computed <= 100:
            birth, age = day.isoformat(), computed
    except (ValueError, TypeError, AttributeError):
        raw_age = athlete.get("age")
        if isinstance(raw_age, int) and not isinstance(raw_age, bool) and 0 <= raw_age <= 100:
            age = raw_age
    inches = athlete.get("height")
    height = None
    if isinstance(inches, (int, float)) and not isinstance(inches, bool):
        if math.isfinite(inches) and 40 <= inches <= 100:
            height = round(inches * 2.54)
    logos = team.get("logos", [])
    logo = media_url(team.get("logo", "")) or next(
        (media_url(item.get("href", "")) for item in logos if media_url(item.get("href", ""))), ""
    )
    return {
        "bio_age": age,
        "bio_birth_date": birth,
        "bio_height_cm": height,
        "bio_nationality": str(athlete.get("citizenship") or ""),
        "bio_foot": "",  # This roster does not publish a verified dominant foot.
        "bio_photo_url": media_url((athlete.get("headshot") or {}).get("href", "")),
        "bio_team_logo_url": logo,
        "bio_consulted_at": consulted_at,
    }


def enrich_biographies(profiles, root: Path, metadata):
    """Read optional roster data without changing profiles, snapshots or ranking metrics."""
    result = profiles.copy()
    empty = biography({}, {}, metadata.get("downloaded_at", ""))
    empty["bio_consulted_at"] = ""
    for column, value in empty.items():
        result[column] = value
    if metadata.get("provider") != "espn":
        return result, []
    snapshot = str(metadata.get("snapshot", ""))
    if not snapshot or Path(snapshot).name != snapshot or snapshot in (".", ".."):
        return result, ["Identificador de consulta no válido para las biografías"]
    folder = root / "data/raw/espn" / snapshot
    if not (folder / "manifest.json").exists():
        return result, []
    issues, facts = [], {}
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("snapshot") != snapshot or manifest.get("season_id") != int(
            profiles.iloc[0]["season_id"]
        ):
            raise ValueError("La biografía no corresponde a la consulta activa")

        def verified(relative):
            content = (folder / relative).read_bytes()
            if hashlib.sha256(content).hexdigest() != manifest["sha256"].get(relative):
                raise ValueError(f"Biografías no verificadas: {relative}")
            return json.loads(content)

        catalog = verified("teams.json")["sports"][0]["leagues"][0]
        if (
            str(catalog.get("id")) != "740"
            or catalog.get("season", {}).get("year") != manifest["season_id"]
        ):
            raise ValueError("Catálogo biográfico de otra liga o temporada")
        for entry in catalog["teams"]:
            team = entry["team"]
            tid = int(team["id"])
            try:
                roster = verified(f"rosters/{tid}.json")
                if (
                    roster.get("season", {}).get("year") != manifest["season_id"]
                    or int(roster["team"]["id"]) != tid
                ):
                    raise ValueError("Plantilla biográfica de otro equipo o temporada")
                for athlete in roster["athletes"]:
                    if athlete.get("gender", "").upper() == "MALE":
                        facts[(int(athlete["id"]), tid)] = biography(
                            athlete, team, metadata["downloaded_at"]
                        )
            except (OSError, ValueError, KeyError, TypeError) as exc:
                issues.append(str(exc))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return result, [str(exc)]
    for index, row in result.iterrows():
        for column, value in facts.get((int(row["player_id"]), int(row["team_id"])), {}).items():
            result.at[index, column] = value
    return result, issues
