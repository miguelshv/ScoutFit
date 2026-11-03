import json

import numpy as np
import pandas as pd
import pytest

from scoutfit.comparison import compare_players, html_report
from scoutfit.evaluation import (
    benchmark_template,
    evaluate_judgments,
    ranking_metrics,
    sensitivity_report,
)
from scoutfit.history import discover_snapshots, interval_changes, player_timeline
from scoutfit.recommender import recommend
from scoutfit.workspace import (
    import_reviews,
    load_records,
    player_key,
    remove_favorite,
    save_favorite,
    save_judgment,
)

FEATURES = {"passes_p90": "Pases /90", "shots_p90": "Tiros /90"}


@pytest.fixture
def players():
    return pd.DataFrame(
        [
            {
                "profile_id": str(pid),
                "player_id": pid,
                "player_name": f"Player {pid}",
                "team_id": pid,
                "team_name": f"Team {pid}",
                "role": "Mediocentro",
                "provider": "espn",
                "competition_id": 740,
                "season_id": 2026,
                "minutes": 900,
                "matches": 10,
                "passes_p90": passes,
                "shots_p90": shots,
                "inferred_role": "Creador" if pid < 4 else "Recuperador",
            }
            for pid, passes, shots in [
                (1, 10, 2),
                (2, 12, 1),
                (3, 50, 5),
                (4, 5, 8),
                (5, 2, 10),
                (6, 20, 9),
            ]
        ]
    )


@pytest.fixture
def metadata():
    return {
        "provider": "espn",
        "competition": "LaLiga masculina",
        "competition_id": 740,
        "season_id": 2026,
        "season": "2026/27",
        "metric_set": "espn_season_v1",
        "snapshot": "one",
        "source": "ESPN",
        "downloaded_at": "2026-10-28T12:00:00Z",
    }


def test_comparison_percentiles_use_the_whole_eligible_position_not_selected_players(players):
    result = compare_players(players, ["1", "2", "3"], FEATURES)
    cell = result.loc[(result.profile_id == "3") & (result.feature == "passes_p90")].iloc[0]
    assert cell.percentile == 100
    assert cell.cohort_size == 6
    assert result.loc[
        (result.profile_id == "1") & (result.feature == "passes_p90"), "percentile"
    ].iloc[0] == pytest.approx(50)


@pytest.mark.parametrize("case", ["position", "season", "source", "minutes", "duplicate", "four"])
def test_comparison_rejects_incompatible_or_invalid_selections(players, case):
    ids = ["1", "2"]
    if case == "position":
        players.loc[1, "role"] = "Defensa"
    elif case == "season":
        players.loc[1, "season_id"] = 2025
    elif case == "source":
        players.loc[1, "provider"] = "other"
    elif case == "minutes":
        players.loc[1, "minutes"] = 30
    elif case == "duplicate":
        ids = ["1", "1"]
    else:
        ids = ["1", "2", "3", "4"]
    with pytest.raises(ValueError):
        compare_players(players, ids, FEATURES)


def test_report_is_standalone_and_escapes_names_notes_and_source(players, metadata):
    players.loc[0, "player_name"] = '<script>alert("player")</script>'
    metadata["competition"] = "<img src=x onerror=alert(1)>"
    data = compare_players(players, ["1", "2"], FEATURES)
    report = html_report(players, ["1", "2"], data, metadata, 450, '<script>alert("note")</script>')
    assert '<meta charset="utf-8">' in report
    assert "<script>" not in report and "<img src=x" not in report
    assert "&lt;script&gt;" in report and "@media print" in report
    assert "Consulta UTC" in report and "Snapshot: one" in report


def test_favorites_are_persistent_deduplicated_and_follow_the_same_player_after_transfer(
    tmp_path, players, metadata
):
    path = tmp_path / "favorites.json"
    player = players.iloc[0].to_dict()
    save_favorite(path, player, metadata, "Revisar creación")
    original_key = player_key(player, metadata)
    player.update({"profile_id": "new-team-profile", "team_id": 99, "team_name": "New Team"})
    save_favorite(path, player, metadata)
    saved = load_records(path)
    assert len(saved) == 1 and saved[0]["key"] == original_key
    assert saved[0]["note"] == "Revisar creación"
    assert saved[0]["team_at_save"] == "New Team"
    remove_favorite(path, original_key)
    assert load_records(path) == []


def test_judgments_require_an_explicit_grade_and_preserve_other_snapshots(tmp_path):
    path = tmp_path / "judgments.json"
    record = {
        "snapshot": "one",
        "reference_id": "1",
        "candidate_id": "2",
        "relevance": 2,
        "note": "Similar",
    }
    save_judgment(path, record)
    save_judgment(path, {**record, "relevance": 1})
    save_judgment(path, {**record, "snapshot": "two"})
    assert len(load_records(path)) == 2
    with pytest.raises(ValueError):
        save_judgment(path, {**record, "relevance": None})


def test_review_csv_import_validates_every_row_before_writing(tmp_path, players):
    csv, output = tmp_path / "review.csv", tmp_path / "judgments.json"
    rows = [
        {
            "snapshot": "one",
            "reference_id": "1",
            "candidate_id": "2",
            "relevance": 2,
            "note": "Similar",
        },
        {
            "snapshot": "one",
            "reference_id": "1",
            "candidate_id": "3",
            "relevance": 7,
            "note": "Invalid",
        },
    ]
    pd.DataFrame(rows).to_csv(csv, index=False)
    # Profile IDs are strings, including when CSV inference would otherwise turn them into integers.
    players["profile_id"] = [f"espn:{pid}" for pid in players.profile_id]
    for row in rows:
        row["reference_id"] = f"espn:{row['reference_id']}"
        row["candidate_id"] = f"espn:{row['candidate_id']}"
    pd.DataFrame(rows).to_csv(csv, index=False)
    with pytest.raises(ValueError):
        import_reviews(output, csv, "one", players)
    assert not output.exists()
    rows[1]["relevance"] = ""
    pd.DataFrame(rows).to_csv(csv, index=False)
    assert import_reviews(output, csv, "one", players) == 1
    assert len(load_records(output)) == 1


def test_ranking_quality_metrics_use_only_the_fully_reviewed_pool():
    labels = {"a": 2, "b": 1, "c": 0}
    perfect = ranking_metrics(["a", "b", "c"], labels, 2)
    assert perfect["ndcg"] == pytest.approx(1)
    assert perfect["precision"] == perfect["recall"] == 1
    reversed_order = ranking_metrics(["c", "b", "a"], labels, 2)
    assert reversed_order["ndcg"] < 1
    assert reversed_order["precision"] == reversed_order["recall"] == 0.5
    with pytest.raises(ValueError):
        ranking_metrics(["a", "b"], labels, 2)
    with pytest.raises(ValueError):
        ranking_metrics(["a", "b"], {"a": 2, "b": 2}, 2)


def test_no_human_judgments_means_no_claimed_quality_metrics(players):
    scores, skipped = evaluate_judgments(players, FEATURES, [], "one")
    assert scores.empty and not skipped
    unrelated = [{"snapshot": "other", "reference_id": "1", "candidate_id": "2", "relevance": 2}]
    assert evaluate_judgments(players, FEATURES, unrelated, "one")[0].empty


def test_evaluation_reports_coverage_and_does_not_treat_unreviewed_players_as_irrelevant(players):
    labels = [
        {"snapshot": "one", "reference_id": "1", "candidate_id": "2", "relevance": 2},
        {"snapshot": "one", "reference_id": "1", "candidate_id": "3", "relevance": 0},
    ]
    scores, skipped = evaluate_judgments(players, FEATURES, labels, "one", k=5)
    assert not skipped and len(scores) == 2
    assert scores.pool_size.eq(2).all()
    assert scores.judged_top_k_coverage.eq(0.4).all()


def test_template_contains_unreviewed_real_ids_and_is_reproducible(players):
    first = benchmark_template(players, FEATURES, "one", queries=4)
    second = benchmark_template(players, FEATURES, "one", queries=4)
    pd.testing.assert_frame_equal(first, second)
    assert first.reference_id.nunique() == 4
    assert first.relevance.isna().all()
    assert set(first.reference_id) <= set(players.profile_id)
    assert (first.reference_id != first.candidate_id).all()


def test_sensitivity_is_seeded_and_never_a_probability_of_success(players):
    first = sensitivity_report(players, "1", FEATURES, trials=5)
    second = sensitivity_report(players, "1", FEATURES, trials=5)
    for expected, actual in zip(first, second):
        pd.testing.assert_frame_equal(expected, actual)
    assert first[0].jaccard.between(0, 1).all()
    assert first[1].frequency.between(0, 1).all()
    assert (first[1].appearances <= 5).all()


def test_cosine_contributions_sum_to_distance_and_zero_reference_is_rejected(players):
    ranked, detail = recommend(players, "1", feature_definitions=FEATURES, distance_metric="cosine")
    for _, candidate in ranked.iterrows():
        explained = detail.loc[
            detail.profile_id == candidate.profile_id, "distance_contribution"
        ].sum()
        assert explained == pytest.approx(candidate.distance)
    assert detail.squared_contribution.isna().all()
    players[list(FEATURES)] = 1.0
    with pytest.raises(ValueError, match="Coseno no definido"):
        recommend(players, "1", feature_definitions=FEATURES, distance_metric="cosine")


def snapshot(tmp_path, metadata, name, day, minutes=90, rate=10, team="Old Team", missing=False):
    directory = tmp_path / "espn" / name
    directory.mkdir(parents=True)
    meta = {**metadata, "snapshot": name, "downloaded_at": f"2026-10-{day:02}T12:00:00Z"}
    (directory / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "player_id": 2 if missing else 1,
                "player_name": "Player",
                "team_name": team,
                "minutes": minutes,
                "matches": 1,
                "passes_p90": rate,
            }
        ]
    ).to_csv(directory / "profiles.csv", index=False)
    return directory


def test_history_tracks_identity_after_transfer_and_calculates_only_a_query_interval(
    tmp_path, metadata
):
    snapshot(tmp_path, metadata, "one", 28)
    snapshot(tmp_path, metadata, "two", 29, minutes=180, rate=15, team="New Team")
    snapshots, errors = discover_snapshots(tmp_path, metadata)
    assert len(snapshots) == 2 and not errors
    timeline = player_timeline(snapshots, 1, FEATURES)
    assert timeline.team_name.tolist() == ["Old Team", "New Team"]
    interval = interval_changes(timeline, "passes_p90").iloc[0]
    assert interval.minutes_added == 90
    assert interval.interval_rate == 20
    assert "no es un partido" in interval.status


@pytest.mark.parametrize(
    "minutes,rate,status",
    [
        (90, 10, "Sin minutos nuevos"),
        (90, 12, "Cambio estadístico"),
        (45, 10, "disminuyen los minutos"),
        (180, 4, "disminuye un conteo"),
    ],
)
def test_no_new_minutes_and_provider_corrections_do_not_produce_fictional_rates(
    tmp_path, metadata, minutes, rate, status
):
    snapshot(tmp_path, metadata, "one", 28)
    snapshot(tmp_path, metadata, "two", 29, minutes=minutes, rate=rate)
    timeline = player_timeline(discover_snapshots(tmp_path, metadata)[0], 1, FEATURES)
    interval = interval_changes(timeline, "passes_p90").iloc[0]
    assert np.isnan(interval.interval_rate)
    assert status in interval.status


def test_missing_history_is_not_filled_or_bridged_and_other_seasons_are_excluded(
    tmp_path, metadata
):
    snapshot(tmp_path, metadata, "one", 27)
    snapshot(tmp_path, metadata, "two", 28, missing=True)
    snapshot(tmp_path, metadata, "three", 29, minutes=180)
    snapshot(tmp_path, {**metadata, "season_id": 2025}, "other", 26)
    snapshots, _ = discover_snapshots(tmp_path, metadata)
    assert len(snapshots) == 3
    timeline = player_timeline(snapshots, 1, FEATURES)
    assert np.isnan(timeline.iloc[1].passes_p90)
    assert interval_changes(timeline, "passes_p90").interval_rate.isna().all()
