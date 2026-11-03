"""Reference-free discovery by weighted shortfall against minimum percentile goals."""

import numpy as np
import pandas as pd

from scoutfit.candidate_filters import CandidateFilters, filter_candidates

PRESETS = {
    "Mediocentro": {
        "Recuperación y distribución": {
            "recoveries_p90": 75,
            "interceptions_p90": 70,
            "tackles_won_p90": 70,
            "passes_p90": 75,
            "completion_pct": 70,
        },
        "Creación y llegada": {
            "key_passes_p90": 80,
            "provider_progressive_carries_p90": 75,
            "box_touches_p90": 70,
        },
        "Organización del juego": {
            "passes_p90": 80,
            "completion_pct": 80,
            "long_balls_p90": 70,
        },
    },
    "Defensa": {
        "Recuperación y salida de balón": {
            "interceptions_p90": 75,
            "tackles_won_p90": 75,
            "passes_p90": 75,
            "completion_pct": 70,
        },
        "Proyección y centros": {
            "provider_progressive_carries_p90": 75,
            "crosses_p90": 80,
            "key_passes_p90": 70,
        },
    },
    "Delantera": {
        "Remate y presencia en el área": {"shots_p90": 80, "box_touches_p90": 80},
        "Creación y conducción": {
            "key_passes_p90": 80,
            "provider_progressive_carries_p90": 80,
            "crosses_p90": 70,
        },
    },
}


def available_presets(position, features):
    available = {
        name: goals
        for name, goals in PRESETS.get(position, {}).items()
        if set(goals).issubset(features)
    }
    available["Personalizado"] = dict.fromkeys(list(features)[:3], 75)
    return available


def recommend_target(
    profiles: pd.DataFrame,
    position: str,
    features: dict,
    goals: dict[str, float],
    min_minutes: float = 450,
    top_k: int = 5,
    weights: dict[str, float] | None = None,
    candidate_filters: CandidateFilters | None = None,
    strict: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if min_minutes < 0 or not np.isfinite(min_minutes) or top_k < 1:
        raise ValueError("Minutos y número de candidatos inválidos")
    if profiles["profile_id"].duplicated().any():
        raise ValueError("profile_id debe ser único")
    if not goals or set(goals) - set(features):
        raise ValueError("Selecciona al menos una métrica conocida para el objetivo")
    targets = np.array(list(goals.values()), dtype=float)
    if not np.isfinite(targets).all() or (targets < 0).any() or (targets > 100).any():
        raise ValueError("Los objetivos deben ser percentiles entre 0 y 100")
    if set(weights or {}) - set(goals):
        raise ValueError("Hay pesos para métricas que no pertenecen al objetivo")
    w = np.array([(weights or {}).get(feature, 1.0) for feature in goals], dtype=float)
    if not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("Las importancias de las métricas activas deben ser positivas y finitas")
    cohort = profiles.loc[
        (profiles["role"] == position) & (profiles["minutes"] >= min_minutes)
    ].copy()
    for column in ("competition_id", "season_id", "provider"):
        if column in cohort and cohort[column].nunique(dropna=False) > 1:
            raise ValueError("La búsqueda requiere una sola liga, temporada y fuente")
    if cohort.empty:
        return cohort.assign(target_gap=0.0, goals_met=0, cohort_size=0), pd.DataFrame()
    values = cohort[list(goals)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Las métricas del objetivo contienen valores ausentes o no finitos")
    percentiles = cohort[list(goals)].rank(method="average", pct=True) * 100
    deficit = np.maximum(targets - percentiles.to_numpy(), 0)
    cohort["target_gap"] = np.sqrt((deficit**2 * w / w.sum()).sum(axis=1))
    cohort["goals_met"] = (deficit == 0).sum(axis=1)
    cohort["cohort_size"] = len(cohort)
    candidates = filter_candidates(cohort, candidate_filters)
    if strict:
        candidates = candidates.loc[candidates["goals_met"] == len(goals)]
    ranking = candidates.sort_values(
        ["target_gap", "minutes", "player_name", "profile_id"],
        ascending=[True, False, True, True],
    ).head(top_k)
    details = []
    for index, player in ranking.iterrows():
        for feature, target in goals.items():
            percentile = float(percentiles.loc[index, feature])
            details.append(
                {
                    "profile_id": player["profile_id"],
                    "feature": feature,
                    "metric": features[feature],
                    "value": player[feature],
                    "percentile": percentile,
                    "target": target,
                    "shortfall": max(target - percentile, 0),
                    "weight": (weights or {}).get(feature, 1.0),
                    "cohort_size": len(cohort),
                }
            )
    return ranking.reset_index(drop=True), pd.DataFrame(details)
