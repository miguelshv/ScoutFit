import numpy as np
import pandas as pd
import pytest

from scoutfit.explorer import project_profiles


@pytest.fixture
def profiles():
    return pd.DataFrame(
        [
            {
                "profile_id": str(pid),
                "player_id": pid,
                "role": "Mediocentro",
                "competition_id": 740,
                "season_id": 2026,
                "provider": "espn",
                "minutes": 900,
                "a": a,
                "b": b,
            }
            for pid, a, b in [(1, 1, 4), (2, 2, 2), (3, 3, 5), (4, 4, 1)]
        ]
    )


def test_projection_fits_the_position_cohort_and_labels_without_refitting(profiles):
    other = profiles.iloc[[0]].copy()
    other["profile_id"] = "excluded"
    other["role"] = "Defensa"
    other["a"] = 10000
    with_other = pd.concat([profiles, other], ignore_index=True)
    first, explained = project_profiles(with_other, "1", {"a": "A", "b": "B"}, 450, {}, ["2"])
    second, _ = project_profiles(profiles, "1", {"a": "A", "b": "B"}, 450, {}, ["3"])
    assert set(first["profile_id"]) == {"1", "2", "3", "4"}
    np.testing.assert_allclose(first[["Eje 1", "Eje 2"]], second[["Eje 1", "Eje 2"]])
    assert first.set_index("profile_id").loc["1", "Grupo"] == "Referencia"
    assert first.set_index("profile_id").loc["2", "Grupo"] == "Candidato"
    assert sum(explained) == pytest.approx(1)


def test_weighted_map_preserves_full_two_metric_distance_and_zero_weights(profiles):
    projected, _ = project_profiles(profiles, "1", {"a": "A", "b": "B"}, 450, {"a": 4, "b": 1})
    values = profiles[["a", "b"]].to_numpy(float)
    scaled = (values - values.mean(0)) / values.std(0)
    expected = np.sqrt(((scaled[0] - scaled[1]) ** 2 * [0.8, 0.2]).sum())
    actual = np.linalg.norm(
        projected.loc[0, ["Eje 1", "Eje 2"]].to_numpy(float)
        - projected.loc[1, ["Eje 1", "Eje 2"]].to_numpy(float)
    )
    assert actual == pytest.approx(expected)
    one_metric, variance = project_profiles(profiles, "1", {"a": "A", "b": "B"}, 450, {"b": 0})
    assert np.isfinite(one_metric[["Eje 1", "Eje 2"]]).all().all()
    assert variance[1] == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("weights", [{"a": 0, "b": 0}, {"a": -1}, {"a": float("nan")}])
def test_projection_rejects_invalid_weights(profiles, weights):
    with pytest.raises(ValueError, match="pesos"):
        project_profiles(profiles, "1", {"a": "A", "b": "B"}, 450, weights)


def test_projection_handles_small_or_flat_cohorts_and_minimum(profiles):
    assert project_profiles(profiles.iloc[:2], "1", {"a": "A", "b": "B"}, 450, {})[0].empty
    flat = profiles.assign(a=1, b=1)
    assert project_profiles(flat, "1", {"a": "A", "b": "B"}, 450, {})[0].empty
    with pytest.raises(ValueError, match="mínimo"):
        project_profiles(profiles, "1", {"a": "A", "b": "B"}, 1000, {})


def test_projection_does_not_mix_season_or_provider(profiles):
    extra = profiles.iloc[[0, 1]].copy()
    extra["profile_id"] = ["old", "other_source"]
    extra.loc[extra["profile_id"] == "old", "season_id"] = 2025
    extra.loc[extra["profile_id"] == "other_source", "provider"] = "other"
    combined = pd.concat([profiles, extra], ignore_index=True)
    result, _ = project_profiles(combined, "1", {"a": "A", "b": "B"}, 450, {})
    assert set(result["profile_id"]) == {"1", "2", "3", "4"}
