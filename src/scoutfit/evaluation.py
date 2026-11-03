"""Human relevance evaluation on a judged pool, plus unlabeled sensitivity checks."""

from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import ndcg_score

from scoutfit.recommender import recommend

METHODS = {"euclidean": "Euclídea", "cosine": "Coseno"}


def ranking_metrics(order: list[str], relevance: dict[str, int], k: int) -> dict:
    if k < 1 or len(order) != len(set(order)) or set(order) != set(relevance):
        raise ValueError("El ranking debe cubrir exactamente el conjunto revisado, sin duplicados")
    if any(value not in (0, 1, 2) for value in relevance.values()):
        raise ValueError("Relevancia válida: 0, 1 o 2")
    if len(order) < 2 or len(set(relevance.values())) < 2:
        raise ValueError("Revisa al menos dos candidatos con relevancias diferentes")
    grades = np.array([relevance[pid] for pid in order], dtype=float)
    limit = min(k, len(order))
    hits = sum(relevance[pid] > 0 for pid in order[:limit])
    positives = sum(value > 0 for value in relevance.values())
    # Scores encode the deterministic model ordering, avoiding arbitrary tie handling.
    ndcg = ndcg_score([grades], [np.arange(len(order), 0, -1)], k=limit)
    return {
        "ndcg": float(ndcg),
        "precision": hits / limit,
        "recall": hits / positives if positives else np.nan,
        "pool_size": len(order),
    }


def benchmark_template(
    profiles: pd.DataFrame,
    features: dict,
    snapshot: str,
    queries: int = 20,
    min_minutes: float = 450,
) -> pd.DataFrame:
    eligible = profiles.loc[profiles["minutes"] >= min_minutes].sort_values(
        ["role", "minutes", "profile_id"], ascending=[True, False, True]
    )
    groups = [group for _, group in eligible.groupby("role", sort=True)]
    # Round-robin position groups prevents all 20 references coming from one position.
    references = []
    for offset in range(len(eligible)):
        for group in groups:
            if offset < len(group):
                references.append(group.iloc[offset])
                if len(references) >= queries:
                    break
        if len(references) >= queries:
            break
    rows = []
    generator = np.random.default_rng(7)
    for reference in references:
        candidates = {}
        for method in METHODS:
            try:
                ranking, _ = recommend(
                    profiles,
                    reference["profile_id"],
                    min_minutes,
                    10,
                    feature_definitions=features,
                    distance_metric=method,
                )
            except ValueError:
                continue
            candidates.update({row["profile_id"]: row for _, row in ranking.iterrows()})
        controls = eligible.loc[
            (eligible["role"] == reference["role"])
            & (eligible["competition_id"] == reference["competition_id"])
            & (eligible["season_id"] == reference["season_id"])
            & (eligible["team_id"] != reference["team_id"])
        ]
        if len(controls):
            for index in generator.choice(len(controls), min(2, len(controls)), replace=False):
                player = controls.iloc[index]
                candidates[player["profile_id"]] = player
        for pid in sorted(candidates):
            candidate = candidates[pid]
            rows.append(
                {
                    "snapshot": snapshot,
                    "reference_id": reference["profile_id"],
                    "reference_name": reference["player_name"],
                    "candidate_id": pid,
                    "candidate_name": candidate["player_name"],
                    "position": reference["role"],
                    "relevance": None,
                    "note": "",
                    "reviewer": "",
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "snapshot",
            "reference_id",
            "reference_name",
            "candidate_id",
            "candidate_name",
            "position",
            "relevance",
            "note",
            "reviewer",
        ],
    )


def evaluate_judgments(
    profiles: pd.DataFrame,
    features: dict,
    judgments: list[dict],
    snapshot: str,
    k: int = 5,
    min_minutes: float = 450,
) -> tuple[pd.DataFrame, list[str]]:
    scoped = [row for row in judgments if row.get("snapshot") == snapshot]
    rows, skipped = [], []
    references = sorted({row["reference_id"] for row in scoped})
    for reference_id in references:
        pool = [row for row in scoped if row["reference_id"] == reference_id]
        if len({row["candidate_id"] for row in pool}) != len(pool):
            raise ValueError("Hay valoraciones duplicadas para la misma pareja y consulta")
        for method, method_name in METHODS.items():
            try:
                full, _ = recommend(
                    profiles,
                    reference_id,
                    min_minutes,
                    len(profiles),
                    feature_definitions=features,
                    distance_metric=method,
                )
                available = set(full["profile_id"])
                relevance = {
                    row["candidate_id"]: row["relevance"]
                    for row in pool
                    if row["candidate_id"] in available
                }
                order = [pid for pid in full["profile_id"] if pid in relevance]
                metrics = ranking_metrics(order, relevance, k)
                top = list(full["profile_id"].head(k))
                rows.append(
                    {
                        "reference_id": reference_id,
                        "method": method_name,
                        **metrics,
                        "judged_top_k_coverage": sum(pid in relevance for pid in top) / len(top),
                        "excluded_judgments": len(pool) - len(relevance),
                    }
                )
            except ValueError as exc:
                skipped.append(f"{reference_id} · {method_name}: {exc}")
    return pd.DataFrame(rows), skipped


def sensitivity_report(
    profiles: pd.DataFrame,
    reference_id: str,
    features: dict,
    min_minutes: float = 450,
    k: int = 5,
    weights: dict | None = None,
    match_role: bool = False,
    exclude_team: bool = True,
    trials: int = 30,
    seed: int = 7,
    candidate_filters=None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not 1 <= trials <= 200:
        raise ValueError("Número de pruebas fuera de rango")
    baseline, _ = recommend(
        profiles,
        reference_id,
        min_minutes,
        k,
        exclude_team,
        weights,
        feature_definitions=features,
        match_inferred_role=match_role,
        candidate_filters=candidate_filters,
    )
    base_ids = set(baseline["profile_id"])
    if not base_ids:
        raise ValueError("No hay candidatos para medir estabilidad")
    base_weights = {name: (weights or {}).get(name, 1.0) for name in features}
    generator = np.random.default_rng(seed)
    seen, runs = Counter(), []
    for run in range(trials):
        perturbation = generator.lognormal(0, 0.15, len(features))
        changed = {
            name: base_weights[name] * perturbation[index] for index, name in enumerate(features)
        }
        ranking, _ = recommend(
            profiles,
            reference_id,
            min_minutes,
            k,
            exclude_team,
            changed,
            feature_definitions=features,
            match_inferred_role=match_role,
            candidate_filters=candidate_filters,
        )
        ids = set(ranking["profile_id"])
        seen.update(ids)
        runs.append(
            {
                "trial": run + 1,
                "jaccard": len(ids & base_ids) / len(ids | base_ids),
                "retained": len(ids & base_ids),
                "baseline_size": len(base_ids),
            }
        )
    names = profiles.set_index("profile_id")["player_name"].to_dict()
    frequencies = pd.DataFrame(
        [
            {
                "profile_id": pid,
                "player_name": names[pid],
                "appearances": count,
                "trials": trials,
                "frequency": count / trials,
            }
            for pid, count in seen.items()
        ]
    ).sort_values(["appearances", "player_name"], ascending=[False, True])
    thresholds = []
    for threshold in sorted({min_minutes, 450, 600, 900}):
        try:
            ranking, _ = recommend(
                profiles,
                reference_id,
                threshold,
                k,
                exclude_team,
                weights,
                feature_definitions=features,
                match_inferred_role=match_role,
                candidate_filters=candidate_filters,
            )
            ids = set(ranking["profile_id"])
            thresholds.append(
                {
                    "min_minutes": threshold,
                    "candidates": len(ids),
                    "jaccard": len(ids & base_ids) / len(ids | base_ids),
                    "status": "Comparable",
                }
            )
        except ValueError as exc:
            thresholds.append(
                {"min_minutes": threshold, "candidates": 0, "jaccard": np.nan, "status": str(exc)}
            )
    return pd.DataFrame(runs), frequencies, pd.DataFrame(thresholds)
