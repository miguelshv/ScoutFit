"""Descriptive sample context and deterministic minute-threshold comparisons."""

import pandas as pd

from scoutfit.recommender import recommend
from scoutfit.target_search import recommend_target


def cohort_for(profiles, reference, minimum):
    selected = profiles.minutes.ge(minimum)
    for field in ("role", "competition_id", "season_id", "provider"):
        if field in profiles and field in reference:
            selected &= profiles[field].eq(reference[field])
    return profiles.loc[selected]


def participation(minutes):
    if minutes < 450:
        return "Participación reducida"
    if minutes < 900:
        return "Participación intermedia"
    return "Mayor participación acumulada"


def sample_summary(profiles, reference, minimum):
    cohort = cohort_for(profiles, reference, minimum)
    return {
        "cohort_size": len(cohort),
        "clubs": int(cohort.team_id.nunique()),
        "median_minutes": float(cohort.minutes.median()) if len(cohort) else None,
        "below_450": int(cohort.minutes.lt(450).sum()),
        "small_cohort": len(cohort) < 20,
    }


def threshold_comparison(profiles, features, reference, minimum, config, mode="similarity"):
    def run(threshold):
        if mode == "similarity":
            return recommend(
                profiles,
                reference["profile_id"],
                threshold,
                config["top_k"],
                config.get("exclude_team", True),
                config.get("weights"),
                feature_definitions=features,
                match_inferred_role=config.get("match_role", False),
                candidate_filters=config.get("candidate_filters"),
            )[0]
        return recommend_target(
            profiles,
            reference["role"],
            features,
            config["goals"],
            threshold,
            config["top_k"],
            config.get("weights"),
            config.get("candidate_filters"),
            config.get("strict", False),
        )[0]

    baseline = run(minimum)
    base_ids = set(baseline.profile_id)
    rows = []
    for threshold in sorted({minimum, 450, 600, 900}):
        row = {
            "minimum": threshold,
            "cohort_size": len(cohort_for(profiles, reference, threshold)),
            "candidates": 0,
            "retained": 0,
            "jaccard": None,
            "status": "Comparable",
        }
        try:
            result = run(threshold)
            ids = set(result.profile_id)
            row.update(candidates=len(result), retained=len(ids & base_ids))
            if ids | base_ids:
                row["jaccard"] = len(ids & base_ids) / len(ids | base_ids)
            else:
                row["status"] = "Sin candidatos en ambas consultas de umbral"
        except ValueError as exc:
            row["status"] = str(exc)
        rows.append(row)
    return pd.DataFrame(rows)
