import numpy as np
import pandas as pd
import pytest

from scoutfit.candidate_filters import CandidateFilters, filter_candidates
from scoutfit.evaluation import sensitivity_report
from scoutfit.recommender import recommend
from scoutfit.target_search import available_presets, recommend_target

FEATURES = {"passes": "Pases", "recoveries": "Recuperaciones"}


@pytest.fixture
def pool():
    return pd.DataFrame(
        [
            {
                "profile_id": str(pid),
                "player_id": pid,
                "player_name": f"Player {pid}",
                "team_id": pid,
                "team_name": f"Club {pid}",
                "role": "Mediocentro",
                "competition_id": 740,
                "season_id": 2026,
                "provider": "espn",
                "minutes": minutes,
                "passes": passes,
                "recoveries": recoveries,
            }
            for pid, passes, recoveries, minutes in [
                (1, 10, 40, 700),
                (2, 20, 30, 800),
                (3, 30, 20, 900),
                (4, 40, 10, 1000),
            ]
        ]
    )


def test_goal_search_has_no_reference_and_deficits_reproduce_distance(pool):
    ranking, details = recommend_target(
        pool, "Mediocentro", FEATURES, {"passes": 75, "recoveries": 75}, weights={"passes": 3}
    )
    assert len(ranking) == 4
    for player in ranking.itertuples():
        rows = details.loc[details["profile_id"] == player.profile_id]
        assert player.target_gap == pytest.approx(
            np.sqrt((rows["shortfall"] ** 2 * rows["weight"]).sum() / rows["weight"].sum())
        )
    assert ranking.iloc[0]["profile_id"] == "3"


def test_goals_are_floors_and_strict_search_does_not_relax_requirements(pool):
    ranking, details = recommend_target(pool, "Mediocentro", FEATURES, {"passes": 50}, strict=True)
    assert set(ranking["profile_id"]) == {"2", "3", "4"}
    assert (ranking["target_gap"] == 0).all()
    assert (details["shortfall"] == 0).all()
    impossible, _ = recommend_target(
        pool, "Mediocentro", FEATURES, {"passes": 100, "recoveries": 100}, strict=True
    )
    assert impossible.empty


def test_target_filters_precede_top_k_and_do_not_change_percentiles_or_scores(pool):
    broad, broad_detail = recommend_target(pool, "Mediocentro", FEATURES, {"passes": 100})
    narrow, detail = recommend_target(
        pool,
        "Mediocentro",
        FEATURES,
        {"passes": 100},
        top_k=1,
        candidate_filters=CandidateFilters(include_teams=(1, 2), exclude_teams=(2,)),
    )
    assert narrow["profile_id"].tolist() == ["1"]
    assert narrow.iloc[0]["target_gap"] == broad.set_index("profile_id").loc["1", "target_gap"]
    assert detail.iloc[0]["percentile"] == 25
    assert detail.iloc[0]["cohort_size"] == 4
    assert broad_detail.loc[broad_detail["profile_id"] == "1", "percentile"].iloc[0] == 25


def test_target_uses_position_sample_and_fixed_percentile_population(pool):
    extra = pool.iloc[[0]].assign(profile_id="defender", role="Defensa", passes=10000)
    small = pool.iloc[[0]].assign(profile_id="low_minutes", player_id=5, minutes=90, passes=10000)
    ranking, detail = recommend_target(
        pd.concat([pool, extra, small], ignore_index=True), "Mediocentro", FEATURES, {"passes": 80}
    )
    assert len(ranking) == 4
    assert set(detail["cohort_size"]) == {4}
    assert detail.set_index("profile_id").loc["4", "percentile"] == 100


@pytest.mark.parametrize(
    "goals,weights",
    [
        ({}, None),
        ({"typo": 75}, None),
        ({"passes": 101}, None),
        ({"passes": float("nan")}, None),
        ({"passes": 75}, {"passes": 0}),
        ({"passes": 75}, {"recoveries": 1}),
    ],
)
def test_target_rejects_invalid_goals_and_weights(pool, goals, weights):
    with pytest.raises(ValueError):
        recommend_target(pool, "Mediocentro", FEATURES, goals, weights=weights)


def test_target_handles_no_sample_and_rejects_incomplete_or_mixed_data(pool):
    assert recommend_target(pool, "Defensa", FEATURES, {"passes": 80})[0].empty
    with pytest.raises(ValueError, match="no finitos"):
        recommend_target(pool.assign(passes=np.nan), "Mediocentro", FEATURES, {"passes": 80})
    mixed = pool.copy()
    mixed.loc[0, "season_id"] = 2025
    with pytest.raises(ValueError, match="sola liga"):
        recommend_target(mixed, "Mediocentro", FEATURES, {"passes": 80})


def test_candidate_filters_intersection_exclusion_and_inclusive_minutes(pool):
    result = filter_candidates(pool, CandidateFilters((1, 2, 3), (2,), 700, 900))
    assert result["profile_id"].tolist() == ["1", "3"]
    assert filter_candidates(pool, CandidateFilters(include_teams=(999,))).empty
    for low, high in [(900, 450), (-1, 500), (0, float("inf"))]:
        with pytest.raises(ValueError, match="intervalo"):
            CandidateFilters(min_minutes=low, max_minutes=high)


def test_similarity_filters_leave_reference_unchanged_and_filter_before_top_k(pool):
    broad, _ = recommend(pool, "1", feature_definitions=FEATURES)
    ranking, detail = recommend(
        pool,
        "1",
        top_k=1,
        feature_definitions=FEATURES,
        candidate_filters=CandidateFilters(include_teams=(4,), min_minutes=950, max_minutes=1000),
    )
    assert ranking["profile_id"].tolist() == ["4"]
    assert ranking.iloc[0]["distance"] == broad.set_index("profile_id").loc["4", "distance"]
    assert detail["squared_contribution"].sum() == pytest.approx(ranking.iloc[0]["distance"] ** 2)
    assert pool.set_index("profile_id").loc["1", "minutes"] == 700


def test_sensitivity_respects_candidate_filters(pool):
    _, frequencies, _ = sensitivity_report(
        pool, "1", FEATURES, trials=3, candidate_filters=CandidateFilters(include_teams=(4,))
    )
    assert frequencies["profile_id"].tolist() == ["4"]


def test_presets_never_require_features_missing_from_the_source():
    assert available_presets("Mediocentro", FEATURES) == {
        "Personalizado": {"passes": 75, "recoveries": 75}
    }
