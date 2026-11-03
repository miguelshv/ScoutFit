import json

import numpy as np
import pandas as pd
import pytest

from scoutfit.datasets import ESPN_FEATURES
from scoutfit.roles import ARCHETYPES, infer_roles


def cohort(position="Mediocentro", count=8):
    return pd.DataFrame(
        [
            {
                "profile_id": str(pid),
                "role": position,
                "competition_id": 740,
                "season_id": 2026,
                "minutes": 900,
                **dict.fromkeys(ESPN_FEATURES, float(pid)),
            }
            for pid in range(count)
        ]
    )


@pytest.mark.parametrize(
    "position,label",
    [(position, label) for position, styles in ARCHETYPES.items() for label in styles],
)
def test_extreme_style_is_recognized_within_position(position, label):
    frame = cohort(position)
    frame.loc[0, list(ARCHETYPES[position][label])] = 100.0
    result = infer_roles(frame)
    assert result.loc[0, "inferred_role"] == label
    assert result.loc[0, "inferred_role_status"] == "Predominante"
    assert result.loc[0, "inferred_role_evidence"]
    scores = json.loads(result.loc[0, "inferred_role_scores"])
    assert max(scores, key=scores.get) == label


def test_low_minutes_neither_receive_labels_nor_change_the_peer_distribution():
    frame = cohort()
    frame.loc[0, ["passes_p90", "completion_pct", "long_balls_p90"]] = 100.0
    low = frame.iloc[[0]].copy()
    low["profile_id"], low["minutes"] = "low", 90
    low[list(ESPN_FEATURES)] = 10000.0
    combined = infer_roles(pd.concat([frame, low], ignore_index=True))
    original = infer_roles(frame)
    assert combined.iloc[-1]["inferred_role"] == ""
    assert combined.iloc[-1]["inferred_role_status"] == "Menos de 450 minutos"
    pd.testing.assert_series_equal(
        combined.iloc[:8]["inferred_role_scores"], original["inferred_role_scores"]
    )


def test_insufficient_and_constant_cohorts_do_not_fabricate_labels():
    small = infer_roles(cohort(count=7))
    assert small["inferred_role"].eq("").all()
    assert small["inferred_role_status"].str.contains("Grupo insuficiente").all()
    frame = cohort()
    frame[list(ESPN_FEATURES)] = 1.0
    constant = infer_roles(frame)
    assert constant["inferred_role"].eq("").all()
    assert constant["inferred_role_status"].eq("Sin variación estadística").all()


def test_seasons_and_leagues_are_never_pooled_to_reach_eight_peers():
    frame = cohort(count=12)
    frame.loc[4:7, "season_id"] = 2025
    frame.loc[8:, "competition_id"] = 999
    assert infer_roles(frame)["inferred_role"].eq("").all()


def test_roles_are_deterministic_under_row_reordering_and_do_not_mutate_input():
    frame = cohort(count=20)
    generator = np.random.default_rng(17)
    frame[list(ESPN_FEATURES)] = generator.uniform(0, 10, (20, len(ESPN_FEATURES)))
    expected = infer_roles(frame).sort_values("profile_id").reset_index(drop=True)
    actual = (
        infer_roles(frame.sample(frac=1, random_state=42))
        .sort_values("profile_id")
        .reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(actual, expected)
    assert "inferred_role" not in frame
    assert actual["inferred_role_status"].isin(["Mixto", "Predominante"]).all()


def test_missing_or_nonfinite_data_is_not_silently_imputed():
    with pytest.raises(ValueError, match="Faltan métricas"):
        infer_roles(cohort().drop(columns="passes_p90"))
    frame = cohort(count=9)
    frame.loc[0, "passes_p90"] = np.nan
    result = infer_roles(frame)
    assert result.loc[0, "inferred_role"] == ""
    assert result.loc[0, "inferred_role_status"] == "Métricas incompletas"
