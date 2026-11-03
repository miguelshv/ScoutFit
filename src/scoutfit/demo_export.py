"""Export only an allowlisted public snapshot; never copy the local workspace."""

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from scoutfit.benchmark_review import campaign, campaign_report
from scoutfit.datasets import active_directory, metric_definitions
from scoutfit.recommender import recommend
from scoutfit.roles import infer_roles

ASSETS = ("index.html", "style.css", "app.js", "engine.mjs")


def export_demo(root, output):
    root, output = root.resolve(), output.resolve()
    # Never export over application data or use a folder containing prior unrelated files.
    if output == root or output.is_relative_to(root / "data"):
        raise ValueError("Usa una carpeta de demo separada de los datos de trabajo.")
    directory = active_directory(root / "data/processed")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("provider") != "espn" or metadata.get("gender") != "male":
        raise ValueError("La demo requiere la consulta masculina de ESPN.")
    profiles = infer_roles(pd.read_csv(directory / "profiles.csv"))
    features = metric_definitions(metadata)
    columns = [
        "profile_id",
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "role",
        "minutes",
        "matches",
        "inferred_role",
        *features,
    ]
    pairs, config = campaign(root, profiles, metadata, features)
    # No notes, reviewer identities or local judgments enter a public build.
    report = campaign_report(profiles, features, pairs, config, [])
    payload = {
        "schema": 1,
        "source": "ESPN",
        "source_url": "https://www.espn.com/soccer/league/_/name/esp.1",
        "snapshot": metadata["snapshot"],
        "consulted_at": metadata["downloaded_at"],
        "season": metadata["season"],
        "team_count": metadata["team_count"],
        "features": features,
        "players": json.loads(profiles[columns].to_json(orient="records", double_precision=15)),
        "evaluation": report,
    }
    dist = output / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    unexpected = set(p.name for p in dist.iterdir()) - set(ASSETS) - {"data.json", "evidence.json"}
    if unexpected:
        raise ValueError("La carpeta dist contiene archivos ajenos a la demo; usa una vacía.")
    for name in ASSETS:
        shutil.copyfile(root / "demo/site" / name, dist / name)
    (dist / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    (dist / "evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    # Independent Python oracle for JavaScript parity, outside the published assets.
    cases = []
    for minimum in (450, 600, 900):
        for _, player in profiles.loc[profiles.minutes.ge(minimum)].iterrows():
            for priority, emphasized in {
                "balanced": (),
                "creation": (
                    "key_passes_p90",
                    "provider_progressive_carries_p90",
                    "box_touches_p90",
                ),
                "defense": ("recoveries_p90", "tackles_won_p90", "interceptions_p90"),
            }.items():
                weights = {f: 3 if f in emphasized else 1 for f in features}
                ranking, _ = recommend(
                    profiles,
                    player.profile_id,
                    minimum,
                    5,
                    weights=weights,
                    feature_definitions=features,
                )
                cases.append(
                    {
                        "reference": player.profile_id,
                        "minimum": minimum,
                        "priority": priority,
                        "ids": ranking.profile_id.tolist(),
                        "distances": ranking.distance.tolist(),
                    }
                )
    (output / "parity.json").write_text(json.dumps(cases, allow_nan=False), encoding="utf-8")
    return {
        "snapshot": metadata["snapshot"],
        "profiles": len(profiles),
        "parity_cases": len(cases),
        "output": str(dist),
    }


def main():
    parser = argparse.ArgumentParser(description="Exportar la demo pública sin archivos personales")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_demo(Path.cwd(), args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
