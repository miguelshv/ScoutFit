"""A cohort-scaled nearest-neighbor baseline with exact distance explanations."""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from scoutfit.candidate_filters import CandidateFilters, filter_candidates
from scoutfit.features import FEATURES


def recommend(
    profiles: pd.DataFrame,
    reference_id: str,
    min_minutes: float = 450,
    top_k: int = 5,
    exclude_team: bool = True,
    weights: dict[str, float] | None = None,
    feature_definitions: dict[str, str] | None = None,
    match_inferred_role: bool = False,
    distance_metric: str = "euclidean",
    candidate_filters: CandidateFilters | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if min_minutes < 0 or top_k < 1:
        raise ValueError("Minutos y número de candidatos inválidos")
    if profiles["profile_id"].duplicated().any():
        raise ValueError("profile_id debe ser único")
    reference = profiles.loc[profiles["profile_id"] == reference_id]
    if len(reference) != 1:
        raise ValueError("Jugador de referencia no encontrado")
    target = reference.iloc[0]
    if target["minutes"] < min_minutes:
        raise ValueError("La referencia no alcanza el mínimo de minutos")
    scope = (
        (profiles["role"] == target["role"])
        & (profiles["minutes"] >= min_minutes)
        & (profiles["competition_id"] == target["competition_id"])
        & (profiles["season_id"] == target["season_id"])
    )
    if "provider" in profiles:
        scope &= profiles["provider"] == target["provider"]
    cohort = profiles.loc[scope].copy().reset_index(drop=True)
    feature_definitions = FEATURES if feature_definitions is None else feature_definitions
    if not feature_definitions:
        raise ValueError("El conjunto debe definir al menos una métrica")
    feature_names = list(feature_definitions)
    metric_weights = {name: 1.0 for name in feature_names}
    if weights is not None:
        if set(weights) - set(feature_names):
            raise ValueError("Peso asociado a una métrica desconocida")
        metric_weights.update(weights)
    w = np.array([metric_weights[name] for name in feature_names], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("Usa pesos finitos no negativos y al menos uno positivo")
    values = cohort[feature_names].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Las métricas contienen valores ausentes o no finitos")
    scaler = StandardScaler()
    z = scaler.fit_transform(values)
    target_index = np.flatnonzero(cohort["profile_id"].to_numpy() == reference_id)[0]
    if distance_metric == "euclidean":
        contributions = (z - z[target_index]) ** 2 * w / w.sum()
        cohort["distance"] = np.sqrt(contributions.sum(axis=1))
    elif distance_metric == "cosine":
        weighted = z * np.sqrt(w)
        norms = np.linalg.norm(weighted, axis=1)
        if norms[target_index] <= 1e-12:
            raise ValueError("Coseno no definido: la referencia coincide con la media del grupo")
        units = np.divide(
            weighted, norms[:, None], out=np.zeros_like(weighted), where=norms[:, None] > 1e-12
        )
        contributions = 0.5 * (units - units[target_index]) ** 2
        cohort["distance"] = contributions.sum(axis=1)
        # A zero vector has no angle: exclude it instead of inventing a cosine distance.
        cohort.loc[norms <= 1e-12, "distance"] = np.nan
    else:
        raise ValueError("Métrica de distancia desconocida")
    standardized = pd.DataFrame(z, columns=feature_names, index=cohort["profile_id"])
    candidates = cohort[(cohort["player_id"] != target["player_id"]) & cohort["distance"].notna()]
    if match_inferred_role:
        if (
            "inferred_role" not in cohort
            or not isinstance(target.get("inferred_role"), str)
            or not target["inferred_role"]
        ):
            raise ValueError("La referencia no tiene un perfil inferido disponible")
        candidates = candidates[candidates["inferred_role"] == target["inferred_role"]]
    if exclude_team:
        candidates = candidates[candidates["team_id"] != target["team_id"]]
    candidates = filter_candidates(candidates, candidate_filters)
    ranking = candidates.sort_values(["distance", "player_name", "profile_id"]).head(top_k)
    explanation_rows = []
    for index, candidate in cohort.iterrows():
        if candidate["profile_id"] not in set(ranking["profile_id"]):
            continue
        position = cohort.index.get_loc(index)
        for j, feature in enumerate(feature_names):
            explanation_rows.append(
                {
                    "profile_id": candidate["profile_id"],
                    "feature": feature,
                    "metric": feature_definitions[feature],
                    "reference": target[feature],
                    "candidate": candidate[feature],
                    "weight": w[j],
                    "squared_contribution": (
                        contributions[position, j] if distance_metric == "euclidean" else np.nan
                    ),
                    "distance_contribution": (
                        contributions[position, j] if distance_metric == "cosine" else np.nan
                    ),
                    "distance_metric": distance_metric,
                    "reference_z": standardized.loc[reference_id, feature],
                    "candidate_z": standardized.loc[candidate["profile_id"], feature],
                }
            )
    return ranking.reset_index(drop=True), pd.DataFrame(explanation_rows)
