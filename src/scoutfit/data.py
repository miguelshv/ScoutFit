"""Download a pinned, resumable StatsBomb snapshot. No API key required."""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REVISION = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
BASE = f"https://raw.githubusercontent.com/hudl/open-data/{REVISION}"
DEFAULT_COMPETITION = 37
DEFAULT_SEASON = 281


def fetch_bytes(url: str) -> bytes:
    for attempt in range(3):
        try:
            with urlopen(
                Request(url, headers={"User-Agent": "ScoutFit/0.1"}), timeout=60
            ) as response:
                return response.read()
        except (URLError, TimeoutError) as exc:
            if isinstance(exc, HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Download failed")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cached_json(root: Path, relative: str):
    path = root / REVISION / relative
    if not path.exists():
        content = fetch_bytes(f"{BASE}/data/{relative}")
        json.loads(content)  # Never cache an invalid response.
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
    return read_json(path)


def competitions(root: Path) -> list[dict]:
    return cached_json(root, "competitions.json")


def download(root: Path, competition: int, season: int, limit: int | None = None) -> Path:
    if limit is not None and limit < 1:
        raise ValueError("--limit debe ser mayor que cero")
    catalog = competitions(root)
    selection = next(
        (c for c in catalog if c["competition_id"] == competition and c["season_id"] == season),
        None,
    )
    if selection is None:
        raise ValueError("Competición/temporada no disponible; ejecuta scoutfit competitions")
    matches = cached_json(root, f"matches/{competition}/{season}.json")
    matches = sorted(matches, key=lambda m: (m["match_date"], m["match_id"]))
    selected = matches[:limit] if limit else matches
    tasks = [(kind, m["match_id"]) for m in selected for kind in ("events", "lineups")]
    print(
        f"{selection['competition_name']} {selection['season_name']}: "
        f"{len(selected)}/{len(matches)} partidos",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(cached_json, root, f"{kind}/{mid}.json"): (kind, mid)
            for kind, mid in tasks
        }
        for index, future in enumerate(as_completed(futures), 1):
            future.result()
            if index % 10 == 0 or index == len(tasks):
                print(f"  {index}/{len(tasks)} archivos verificados", flush=True)
    files = {}
    for kind, mid in tasks:
        relative = f"{kind}/{mid}.json"
        files[relative] = hashlib.sha256((root / REVISION / relative).read_bytes()).hexdigest()
    manifest = {
        "source": "StatsBomb Open Data",
        "repository": "https://github.com/hudl/open-data",
        "revision": REVISION,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "competition_id": competition,
        "season_id": season,
        "competition": selection["competition_name"],
        "season": selection["season_name"],
        "matches_available": len(matches),
        "match_ids": [m["match_id"] for m in selected],
        "partial": len(selected) < len(matches),
        "sha256": files,
    }
    path = root / REVISION / f"manifest-{competition}-{season}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    logo = Path("assets/statsbomb.png")
    if not logo.exists():
        logo.parent.mkdir(exist_ok=True)
        logo.write_bytes(
            fetch_bytes(f"{BASE}/img/{quote('SB - Icon Lockup - Colour positive.png')}")
        )
    return path
