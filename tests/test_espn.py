import hashlib
import json

import pandas as pd
import pytest

from scoutfit.datasets import ESPN_FEATURES, activate, active_directory
from scoutfit.espn import COUNTS, build_current, player_profile
from scoutfit.recommender import recommend


def athlete(pid=1, **extra):
    return {
        "id": str(pid),
        "displayName": f"Player {pid}",
        "gender": "MALE",
        "position": {"abbreviation": "M"},
        **extra,
    }


def statistics(pid=1, season=2026, **overrides):
    values = {name: 10.0 for name in COUNTS.values()}
    values.update(
        {
            "minutes": 180.0,
            "appearances": 2.0,
            "totalPasses": 100.0,
            "accuratePasses": 80.0,
            **overrides,
        }
    )
    return {
        "season": {
            "$ref": f"https://sports.core.api.espn.com/v2/sports/soccer/leagues/esp.1/seasons/{season}"
        },
        "athlete": {
            "$ref": f"https://sports.core.api.espn.com/v2/sports/soccer/leagues/esp.1/seasons/{season}/athletes/{pid}"
        },
        "splits": {
            "categories": [
                {"stats": [{"name": name, "value": value} for name, value in values.items()]}
            ]
        },
    }


def test_espn_rates_and_percentage_are_derived_without_inventing_event_metrics():
    row = player_profile(athlete(), {"id": "83", "displayName": "Barcelona"}, statistics(), 2026)
    assert row["passes_p90"] == 50
    assert row["completion_pct"] == 80
    assert row["recoveries_p90"] == 5
    assert row["role_share"] is None
    assert "pressures_p90" not in row
    assert "progressive_passes_p90" not in row


@pytest.mark.parametrize(
    "payload,season", [(statistics(season=2025), 2026), (statistics(pid=2), 2026)]
)
def test_other_season_or_player_is_rejected(payload, season):
    with pytest.raises(ValueError):
        player_profile(athlete(), {"id": "83", "displayName": "Barcelona"}, payload, season)


@pytest.mark.parametrize(
    "values",
    [
        {"minutes": 0},
        {"accuratePasses": 101},
        {"totalPasses": -1},
        {"recoveries": None},
        {"recoveries": float("nan")},
    ],
)
def test_unusable_statistics_are_excluded_instead_of_imputed(values):
    with pytest.raises(ValueError):
        player_profile(
            athlete(), {"id": "83", "displayName": "Barcelona"}, statistics(**values), 2026
        )


def test_gender_must_be_confirmed():
    with pytest.raises(ValueError, match="masculino"):
        player_profile(
            athlete(gender="FEMALE"), {"id": "83", "displayName": "Barcelona"}, statistics(), 2026
        )


def test_current_feature_set_is_used_for_ranking_and_exact_explanation():
    rows = [
        player_profile(
            athlete(pid),
            {"id": str(pid), "displayName": f"Team {pid}"},
            statistics(pid, totalPasses=100 + pid),
            2026,
        )
        for pid in (1, 2, 3)
    ]
    frame = pd.DataFrame(rows)
    ranking, detail = recommend(
        frame, "espn:1:1", min_minutes=90, feature_definitions=ESPN_FEATURES
    )
    assert len(ranking) == 2
    assert set(detail["feature"]) == set(ESPN_FEATURES)
    for _, candidate in ranking.iterrows():
        contribution = detail.loc[
            detail["profile_id"] == candidate["profile_id"], "squared_contribution"
        ].sum()
        assert contribution == pytest.approx(candidate["distance"] ** 2)


def test_active_dataset_cannot_point_outside_processed_directory(tmp_path):
    (tmp_path / "active.json").write_text(json.dumps({"dataset": "../outside"}))
    with pytest.raises(ValueError, match="dentro"):
        active_directory(tmp_path)


def test_failed_build_keeps_previous_active_dataset(tmp_path):
    processed, snapshot = tmp_path / "processed", tmp_path / "raw/snapshot"
    previous = processed / "espn/previous"
    previous.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    activate(processed, previous)
    (snapshot / "broken.json").write_text("modified")
    (snapshot / "manifest.json").write_text(json.dumps({"sha256": {"broken.json": "wrong"}}))
    with pytest.raises(ValueError, match="SHA-256"):
        build_current(snapshot / "manifest.json", processed)
    assert active_directory(processed) == previous.resolve()


def test_ambiguous_team_membership_is_not_assigned_arbitrarily(tmp_path):
    snapshot = tmp_path / "raw/snapshot"
    (snapshot / "rosters").mkdir(parents=True)
    (snapshot / "statistics").mkdir()
    teams = [{"team": {"id": str(tid), "displayName": f"Team {tid}"}} for tid in (83, 86)]
    payloads = {
        "teams.json": {"sports": [{"leagues": [{"teams": teams}]}]},
        "rosters/83.json": {"athletes": [athlete(1), athlete(2)]},
        "rosters/86.json": {"athletes": [athlete(1)]},
        "statistics/1.json": statistics(1),
        "statistics/2.json": statistics(2),
    }
    hashes = {}
    for name, payload in payloads.items():
        content = json.dumps(payload).encode("utf-8")
        (snapshot / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    manifest = {"snapshot": "snapshot", "season_id": 2026, "sha256": hashes}
    (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    frame, metadata = build_current(snapshot / "manifest.json", tmp_path / "processed")
    assert frame["player_id"].tolist() == [2]
    assert len(metadata["excluded_profiles"]) == 2
    assert active_directory(tmp_path / "processed").name == "snapshot"
