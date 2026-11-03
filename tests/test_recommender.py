import numpy as np
import pandas as pd
import pytest

from scoutfit.features import FEATURES
from scoutfit.recommender import recommend


def profile(pid, value=1, **extra):
    return {
        "profile_id": f"{pid}:10",
        "player_id": pid,
        "player_name": f"Player {pid}",
        "team_id": pid * 10,
        "team_name": f"Team {pid}",
        "role": "Mediocentro",
        "minutes": 900,
        "competition_id": 37,
        "season_id": 281,
        **dict.fromkeys(FEATURES, value),
        **extra,
    }


def test_identical_profile_is_nearest_and_reference_is_excluded():
    frame = pd.DataFrame([profile(1), profile(2), profile(3, value=4)])
    ranking, _ = recommend(frame, "1:10")
    assert ranking.iloc[0]["player_id"] == 2
    assert ranking.iloc[0]["distance"] == 0
    assert 1 not in ranking["player_id"].tolist()


def test_filters_role_minutes_team_season_and_same_person_other_team():
    frame = pd.DataFrame(
        [
            profile(1),
            profile(2),
            profile(3, role="Central"),
            profile(4, minutes=100),
            profile(5, team_id=10),
            profile(6, season_id=90),
            profile(7, competition_id=99),
            profile(1, profile_id="1:99", team_id=99),
        ]
    )
    assert recommend(frame, "1:10")[0]["player_id"].tolist() == [2]


def test_constant_cohort_has_zero_distances_and_no_nans():
    frame = pd.DataFrame([profile(1), profile(2), profile(3)])
    ranking, detail = recommend(frame, "1:10")
    assert np.isfinite(ranking["distance"]).all()
    assert (ranking["distance"] == 0).all()
    assert (detail["squared_contribution"] == 0).all()


def test_explanation_sums_to_squared_distance():
    frame = pd.DataFrame([profile(1), profile(2, value=2), profile(3, value=4)])
    ranking, detail = recommend(frame, "1:10", weights={"passes_p90": 3})
    for _, row in ranking.iterrows():
        explained = detail.loc[
            detail["profile_id"] == row["profile_id"], "squared_contribution"
        ].sum()
        assert explained == pytest.approx(row["distance"] ** 2)


def test_weight_changes_nearest_neighbor():
    frame = pd.DataFrame(
        [profile(1, value=0), profile(2, value=0, passes_p90=10), profile(3, value=0, shots_p90=10)]
    )
    passes_only = dict.fromkeys(FEATURES, 0)
    passes_only["passes_p90"] = 1
    shots_only = dict.fromkeys(FEATURES, 0)
    shots_only["shots_p90"] = 1
    assert recommend(frame, "1:10", weights=passes_only)[0].iloc[0]["player_id"] == 3
    assert recommend(frame, "1:10", weights=shots_only)[0].iloc[0]["player_id"] == 2


@pytest.mark.parametrize(
    "weights",
    [dict.fromkeys(FEATURES, 0), {"passes_p90": -1}, {"passes_p90": float("nan")}, {"typo": 1}],
)
def test_invalid_weights_fail(weights):
    with pytest.raises(ValueError):
        recommend(pd.DataFrame([profile(1), profile(2)]), "1:10", weights=weights)


def test_reference_must_meet_minutes_threshold():
    with pytest.raises(ValueError, match="mínimo"):
        recommend(pd.DataFrame([profile(1, minutes=100), profile(2)]), "1:10")


def test_nonfinite_metrics_fail_instead_of_filling_silently():
    with pytest.raises(ValueError, match="no finitos"):
        recommend(pd.DataFrame([profile(1), profile(2, passes_p90=float("nan"))]), "1:10")


def test_empty_candidate_pool_returns_empty_ranking():
    ranking, detail = recommend(pd.DataFrame([profile(1), profile(2, role="Central")]), "1:10")
    assert ranking.empty
    assert detail.empty


def test_inferred_role_filter_limits_candidates_without_changing_distances():
    frame = pd.DataFrame(
        [
            profile(1, inferred_role="Organizador"),
            profile(2, value=2, inferred_role="Organizador"),
            profile(3, value=1, inferred_role="Recuperador"),
        ]
    )
    broad, _ = recommend(frame, "1:10")
    strict, explanation = recommend(frame, "1:10", match_inferred_role=True)
    assert strict["player_id"].tolist() == [2]
    assert strict.iloc[0]["distance"] == pytest.approx(
        broad.loc[broad["player_id"] == 2, "distance"].iloc[0]
    )
    assert set(explanation["profile_id"]) == {"2:10"}


def test_missing_inferred_role_is_explicit_and_empty_pool_is_not_broadened():
    frame = pd.DataFrame([profile(1, inferred_role=""), profile(2, inferred_role="Recuperador")])
    with pytest.raises(ValueError, match="perfil inferido"):
        recommend(frame, "1:10", match_inferred_role=True)
    frame.loc[0, "inferred_role"] = "Organizador"
    ranking, _ = recommend(frame, "1:10", match_inferred_role=True)
    assert ranking.empty
