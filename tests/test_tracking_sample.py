import copy
import json

import numpy as np
import pandas as pd
import pytest

from scoutfit.candidate_filters import CandidateFilters
from scoutfit.sample_context import cohort_for, participation, sample_summary, threshold_comparison
from scoutfit.tracking import compare_player, project_changes, snapshot_frames

FEATURES = {"passes_p90": "Pases /90", "completion_pct": "Pases completados (%)"}


@pytest.fixture
def players():
    return pd.DataFrame(
        [
            {
                "profile_id": f"espn:{i}:{i % 3}",
                "player_id": i,
                "player_name": f"Player {i}",
                "team_id": i % 3,
                "team_name": f"Club {i % 3}",
                "role": "Mediocentro",
                "provider": "espn",
                "competition_id": 740,
                "season_id": 2026,
                "minutes": 150 * i + 100,
                "matches": i + 1,
                "passes_p90": 10 + i * 3,
                "completion_pct": 70 + i,
                "inferred_role": "Creador",
            }
            for i in range(1, 9)
        ]
    )


def test_sample_uses_full_scope_before_candidate_constraints(players):
    reference = players.iloc[4]
    foreign = players.assign(profile_id=lambda x: x.profile_id + ":other", season_id=2025)
    mixed = pd.concat([players, foreign], ignore_index=True)
    summary = sample_summary(mixed, reference, 0)
    assert summary["cohort_size"] == 8 and summary["below_450"] == 2
    assert len(cohort_for(mixed, reference, 450)) == 6
    assert participation(449) == "Participación reducida"
    assert participation(450) == "Participación intermedia"
    assert participation(900) == "Mayor participación acumulada"


def test_thresholds_preserve_filters_and_do_not_relax_reference_minutes(players):
    reference = players.iloc[4]  # 850 min: cannot be used at 900.
    filters = CandidateFilters(include_teams=(0,), max_minutes=800)
    config = {"top_k": 5, "weights": {"passes_p90": 3}, "candidate_filters": filters}
    before = players.copy(deep=True)
    result = threshold_comparison(players, FEATURES, reference, 450, config).set_index("minimum")
    assert result.loc[450, "candidates"] == 1
    assert result.loc[450, "jaccard"] == 1
    assert result.loc[600, "candidates"] == 0
    assert pd.isna(result.loc[900, "jaccard"])
    assert "referencia" in result.loc[900, "status"].lower()
    pd.testing.assert_frame_equal(players, before)


def test_target_thresholds_keep_strict_goals_and_support_empty_pools(players):
    result = threshold_comparison(
        players,
        FEATURES,
        players.iloc[0],
        450,
        {
            "top_k": 5,
            "goals": {"passes_p90": 100, "completion_pct": 100},
            "strict": True,
            "candidate_filters": CandidateFilters(include_teams=(1,)),
        },
        mode="target",
    )
    assert result.candidates.eq(0).all()
    assert result.jaccard.isna().all()
    assert "referencia" not in " ".join(result.status).lower()


def test_changes_follow_player_and_expose_absolute_units_and_provider_corrections(players):
    before = players.iloc[0].copy()
    after = before.copy()
    after.update(
        pd.Series(
            {
                "team_id": 2,
                "team_name": "New club",
                "profile_id": "espn:1:2",
                "minutes": before.minutes + 90,
                "matches": before.matches + 1,
                "passes_p90": before.passes_p90 - 10,
                "completion_pct": before.completion_pct + 2,
            }
        )
    )
    result = compare_player(before, after, FEATURES)
    assert result["team_changed"] and result["minutes_delta"] == 90
    assert result["changed_metrics"] == 2 and result["possible_correction"]
    assert result["metrics"][1]["delta"] == 2 and result["metrics"][1]["unit"] == "pp"
    assert result["metrics"][0]["unit"] == "/90"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "old,new,status",
    [
        (False, True, "Ahora disponible"),
        (True, False, "Ya no disponible"),
        (False, False, "Sin datos utilizables"),
    ],
)
def test_missing_profiles_are_not_zero_or_a_transfer(players, old, new, status):
    result = compare_player(
        players.iloc[0] if old else None, players.iloc[0] if new else None, FEATURES
    )
    assert result["status"] == status
    assert result["minutes_delta"] is None and not result["team_changed"]
    assert not result["metrics"]


def test_missing_metric_and_unknown_team_id_are_not_fabricated(players):
    before, after = players.iloc[0].copy(), players.iloc[0].copy()
    before["team_id"] = None
    after["passes_p90"] = np.nan
    result = compare_player(before, after, FEATURES)
    assert not result["team_changed"] and result["metrics"][0]["after"] is None
    assert result["metrics"][0]["delta"] is None
    assert result["status"] == "Datos incompletos"
    json.dumps(result, allow_nan=False)


def test_project_uses_saved_baseline_preserves_notes_and_rejects_other_seasons(tmp_path, players):
    metadata = {
        "provider": "espn",
        "competition_id": 740,
        "season_id": 2026,
        "metric_set": "test",
        "snapshot": "new",
        "downloaded_at": "2026-11-03T12:00:00Z",
    }
    old = players.copy()
    old.minutes -= 90
    folder = tmp_path / "espn/old"
    folder.mkdir(parents=True)
    old.to_csv(folder / "profiles.csv", index=False)
    (folder / "metadata.json").write_text(
        json.dumps({**metadata, "snapshot": "old", "downloaded_at": "2026-11-02T12:00:00Z"})
    )
    item = {
        "key": "espn:740:2026:1",
        "player_id": 1,
        "player_name": "Player 1",
        "provider": "espn",
        "competition_id": 740,
        "season_id": 2026,
        "snapshot": "old",
        "team_at_save": "Club 1",
        "note": "Private note",
    }
    project = {
        "candidates": [
            item,
            {**item, "key": "other", "season_id": 2025},
            {**item, "key": "missing", "snapshot": "missing"},
            {**item, "key": "same", "snapshot": "new"},
        ]
    }
    untouched = copy.deepcopy(project)
    snapshots, errors = snapshot_frames(tmp_path, metadata)
    assert not errors
    result = project_changes(project, players, metadata, snapshots, FEATURES).set_index("key")
    assert result.loc[item["key"], "minutes_delta"] == 90
    assert result.loc["other", "status"] == "Otra fuente, liga o temporada"
    assert result.loc["missing", "status"] == "Sin consulta de origen comparable"
    assert result.loc["same", "status"] == "Misma consulta al guardar"
    assert project == untouched
    backwards = project_changes(
        {"candidates": [item]},
        players,
        {**metadata, "downloaded_at": "2026-11-01T12:00:00Z"},
        snapshots,
        FEATURES,
    )
    assert backwards.iloc[0]["status"] == "Origen posterior a la consulta activa"
