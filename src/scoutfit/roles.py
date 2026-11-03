"""Transparent style archetypes, inferred within position/league/season cohorts.

These hand-authored prototypes describe statistical styles, not observed tactical
positions. Percentile affinities are not probabilities or validated scouting labels.
"""

import json

import numpy as np
import pandas as pd

from scoutfit.datasets import ESPN_FEATURES

ROLE_MODEL_VERSION = "archetypes-v1"
MIN_ROLE_MINUTES = 450
MIN_ROLE_PEERS = 8
MIXED_MARGIN = 0.05
ARCHETYPES = {
    "Defensa": {
        "Defensa distribuidor": {"passes_p90": 2, "completion_pct": 1, "long_balls_p90": 2},
        "Defensa recuperador": {
            "recoveries_p90": 1,
            "tackles_won_p90": 2,
            "interceptions_p90": 2,
            "duels_won_p90": 1,
        },
        "Defensa de proyección": {
            "crosses_p90": 2,
            "provider_progressive_carries_p90": 2,
            "key_passes_p90": 1,
            "box_touches_p90": 1,
        },
    },
    "Mediocentro": {
        "Mediocentro organizador": {"passes_p90": 2, "completion_pct": 1, "long_balls_p90": 2},
        "Mediocentro recuperador": {
            "recoveries_p90": 1,
            "tackles_won_p90": 2,
            "interceptions_p90": 2,
            "duels_won_p90": 1,
        },
        "Mediocentro creador": {
            "key_passes_p90": 2,
            "provider_progressive_carries_p90": 2,
            "box_touches_p90": 1,
        },
    },
    "Delantera": {
        "Atacante finalizador": {"shots_p90": 2, "box_touches_p90": 2},
        "Atacante creador": {
            "key_passes_p90": 2,
            "passes_p90": 1,
            "completion_pct": 1,
            "long_balls_p90": 1,
        },
        "Atacante de conducción y centro": {
            "provider_progressive_carries_p90": 2,
            "crosses_p90": 2,
            "duels_won_p90": 1,
        },
    },
}


def infer_roles(profiles: pd.DataFrame) -> pd.DataFrame:
    """Assign archetypes using fixed eligibility, independent of UI filters or weights."""
    result = profiles.copy().reset_index(drop=True)
    result["inferred_role"] = ""
    result["inferred_role_alternative"] = ""
    result["inferred_role_status"] = "Posición sin modelo de perfiles"
    result["inferred_role_margin"] = np.nan
    result["inferred_role_evidence"] = ""
    result["inferred_role_scores"] = "{}"
    result["role_model_version"] = ROLE_MODEL_VERSION
    features = list(ESPN_FEATURES)
    missing = set(features) - set(result.columns)
    if missing:
        raise ValueError(f"Faltan métricas para inferir perfiles: {', '.join(sorted(missing))}")
    groups = ["competition_id", "season_id", "role"]
    if "provider" in result:
        groups.append("provider")
    for _, group in result.groupby(groups, sort=True, dropna=False):
        position = group.iloc[0]["role"]
        prototypes = ARCHETYPES.get(position)
        if prototypes is None:
            continue
        result.loc[group.index, "inferred_role_status"] = "Menos de 450 minutos"
        eligible = group.loc[group["minutes"] >= MIN_ROLE_MINUTES]
        if eligible.empty:
            continue
        valid = np.isfinite(eligible[features].to_numpy(dtype=float)).all(axis=1)
        result.loc[eligible.index[~valid], "inferred_role_status"] = "Métricas incompletas"
        eligible = eligible.loc[valid]
        if len(eligible) < MIN_ROLE_PEERS:
            result.loc[eligible.index, "inferred_role_status"] = (
                "Grupo insuficiente: menos de 8 perfiles"
            )
            continue
        informative = eligible[features].nunique() > 1
        if not informative.any():
            result.loc[eligible.index, "inferred_role_status"] = "Sin variación estadística"
            continue
        percentiles = eligible[features].rank(method="average", pct=True)
        # Constant dimensions provide no stylistic evidence, regardless of ties.
        percentiles.loc[:, ~informative] = 0.5
        scores = pd.DataFrame(index=eligible.index)
        for label, weights in prototypes.items():
            scores[label] = sum(percentiles[f] * w for f, w in weights.items()) / sum(
                weights.values()
            )
        for index in eligible.index:
            ordered = sorted(scores.loc[index].items(), key=lambda item: (-item[1], item[0]))
            primary, best = ordered[0]
            secondary, second = ordered[1]
            margin = float(best - second)
            # Exact flat evidence must not fabricate a role via alphabetical tie-breaking.
            if np.isclose(scores.loc[index].max(), scores.loc[index].min()):
                result.at[index, "inferred_role_status"] = "Sin predominio de perfil"
                continue
            result.at[index, "inferred_role"] = primary
            result.at[index, "inferred_role_alternative"] = secondary
            result.at[index, "inferred_role_margin"] = margin
            result.at[index, "inferred_role_status"] = (
                "Mixto" if margin < MIXED_MARGIN else "Predominante"
            )
            evidence = sorted(prototypes[primary], key=lambda f: (-percentiles.at[index, f], f))[:3]
            result.at[index, "inferred_role_evidence"] = "; ".join(
                f"{ESPN_FEATURES[f]}: percentil {100 * percentiles.at[index, f]:.0f}"
                for f in evidence
            )
            result.at[index, "inferred_role_scores"] = json.dumps(
                {name: round(float(value), 6) for name, value in ordered}, ensure_ascii=False
            )
    return result
