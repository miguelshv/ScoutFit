import argparse
import json
from pathlib import Path

import pandas as pd

from scoutfit.data import (
    DEFAULT_COMPETITION,
    DEFAULT_SEASON,
    REVISION,
    competitions,
    download,
    read_json,
)
from scoutfit.datasets import activate, active_directory, metric_definitions
from scoutfit.espn import build_current, download_current, latest_manifest
from scoutfit.evaluation import benchmark_template, evaluate_judgments
from scoutfit.features import build_profiles
from scoutfit.recommender import recommend
from scoutfit.roles import infer_roles
from scoutfit.updates import UpdateError, update_dataset
from scoutfit.workspace import import_reviews, load_records


def main():
    parser = argparse.ArgumentParser(description="ScoutFit: LaLiga masculina y scouting explicable")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("competitions", help="Listar el catálogo histórico de StatsBomb")
    update = sub.add_parser(
        "update", help="Consultar LaLiga actual, validar y activar nuevos perfiles"
    )
    update.add_argument("--season", type=int, help="Año inicial; por defecto temporada actual")
    for name in ("fetch", "build"):
        command = sub.add_parser(name)
        command.add_argument("--source", choices=["espn", "statsbomb"], default="espn")
        command.add_argument(
            "--competition", type=int, default=DEFAULT_COMPETITION, help="Solo para StatsBomb"
        )
        command.add_argument("--season", type=int, help="ESPN: año inicial; StatsBomb: season_id")
        if name == "fetch":
            command.add_argument("--limit", type=int, help="Solo para StatsBomb")
            command.add_argument("--refresh", action="store_true", help="Volver a consultar ESPN")
    nearest = sub.add_parser("recommend")
    nearest.add_argument("profile_id", help="ID mostrado en el CSV activo")
    nearest.add_argument("--min-minutes", type=float, default=450)
    nearest.add_argument("--top-k", type=int, default=5)
    nearest.add_argument(
        "--same-profile", action="store_true", help="Mismo perfil estadístico inferido"
    )
    benchmark = sub.add_parser("benchmark", help="Crear referencias y candidatos sin valorar")
    benchmark.add_argument("--queries", type=int, default=20)
    evaluate = sub.add_parser("evaluate", help="Evaluar exclusivamente parejas revisadas")
    evaluate.add_argument("--judgments", type=Path, default=Path("data/user/judgments.json"))
    evaluate.add_argument("--top-k", type=int, default=5)
    importer = sub.add_parser("import-reviews", help="Importar una plantilla CSV revisada")
    importer.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    raw, processed = Path("data/raw"), Path("data/processed")
    try:
        if args.command == "competitions":
            frame = pd.DataFrame(competitions(raw))
            print(
                frame[
                    [
                        "competition_id",
                        "season_id",
                        "competition_name",
                        "season_name",
                        "competition_gender",
                    ]
                ].to_string(index=False)
            )
        elif args.command == "recommend":
            directory = active_directory(processed)
            profiles = pd.read_csv(directory / "profiles.csv")
            metadata = read_json(directory / "metadata.json")
            if metadata.get("provider") == "espn":
                profiles = infer_roles(profiles)
            ranking, _ = recommend(
                profiles,
                args.profile_id,
                args.min_minutes,
                args.top_k,
                feature_definitions=metric_definitions(metadata),
                match_inferred_role=args.same_profile,
            )
            print(
                ranking[["player_name", "team_name", "minutes", "distance"]].to_string(index=False)
            )
        elif args.command in ("benchmark", "evaluate", "import-reviews"):
            directory = active_directory(processed)
            profiles = pd.read_csv(directory / "profiles.csv")
            metadata = read_json(directory / "metadata.json")
            features = metric_definitions(metadata)
            snapshot = metadata.get("snapshot", metadata.get("revision", "historical"))
            if args.command == "benchmark":
                if not 1 <= args.queries <= 100:
                    raise ValueError("Usa entre 1 y 100 referencias")
                frame = benchmark_template(profiles, features, snapshot, args.queries)
                output = Path("data/evaluation") / f"{snapshot}-template.csv"
                output.parent.mkdir(parents=True, exist_ok=True)
                frame.to_csv(output, index=False)
                print(f"{frame['reference_id'].nunique()} referencias sin valorar: {output}")
            elif args.command == "import-reviews":
                count = import_reviews(
                    Path("data/user/judgments.json"), args.csv_path, snapshot, profiles
                )
                print(f"Valoraciones importadas: {count}")
            else:
                scores, skipped = evaluate_judgments(
                    profiles, features, load_records(args.judgments), snapshot, args.top_k
                )
                report = {
                    "snapshot": snapshot,
                    "status": "evaluated" if len(scores) else "pending_review",
                    "scope": "judged_pool_only",
                    "results": scores.to_dict("records"),
                    "skipped": skipped,
                }
                output = Path("reports/evaluation.json")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
                    encoding="utf-8",
                )
                print(f"Evaluaciones válidas: {len(scores)}. Informe: {output}")
        elif args.command == "update":
            profiles, metadata, report = update_dataset(Path.cwd(), season=args.season)
            print_summary(profiles, metadata)
            print(f"Resumen de cambios: {active_directory(processed) / 'update_report.json'}")
        elif args.source == "espn":
            if args.command == "fetch":
                if args.limit is not None:
                    raise ValueError(
                        "--limit solo se aplica a StatsBomb; LaLiga consulta los 20 clubes"
                    )
                print(download_current(raw, refresh=args.refresh, season=args.season))
            else:
                manifest = latest_manifest(raw)
                if args.season is not None and read_json(manifest)["season_id"] != args.season:
                    raise ValueError("Descarga de otra temporada; ejecuta fetch primero")
                profiles, metadata = build_current(manifest, processed)
                print_summary(profiles, metadata)
        else:
            season = args.season if args.season is not None else DEFAULT_SEASON
            if args.command == "fetch":
                print(download(raw, args.competition, season, args.limit))
            else:
                manifest = raw / REVISION / f"manifest-{args.competition}-{season}.json"
                profiles, metadata = build_profiles(manifest, processed)
                activate(processed, processed)
                print_summary(profiles, metadata)
    except (OSError, ValueError, KeyError, UpdateError) as exc:
        parser.exit(1, f"Error: {exc}\n")


def print_summary(profiles, metadata):
    summary = {
        "source": metadata["source"],
        "competition": metadata["competition"],
        "season": metadata["season"],
        "profiles": len(profiles),
    }
    if metadata.get("provider") == "espn":
        summary.update(
            {
                "teams": metadata["team_count"],
                "excluded_profiles": len(metadata["excluded_profiles"]),
                "downloaded_at": metadata["downloaded_at"],
            }
        )
    else:
        summary.update(
            {
                "matches_used": len(metadata["used_match_ids"]),
                "matches_excluded": len(metadata["excluded_matches"]),
            }
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
