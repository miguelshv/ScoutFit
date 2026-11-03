import json
from collections import Counter

import pytest

from scoutfit.features import (
    action_counts,
    build_profiles,
    period_lengths,
    player_minutes,
)


def position(start="00:00", end=None, start_period=1, end_period=None, pos=14):
    return {
        "position_id": pos,
        "from": start,
        "to": end,
        "from_period": start_period,
        "to_period": end_period,
    }


def test_full_match_includes_stoppage_time_without_break():
    minutes, roles = player_minutes({"positions": [position()]}, {1: 48 * 60, 2: 50 * 60})
    assert minutes == 98
    assert roles == Counter({"Mediocentro": 98})


def test_substitution_clock_accounts_for_first_half_stoppage():
    minutes, _ = player_minutes(
        {"positions": [position(start="60:00", start_period=2)]}, {1: 48 * 60, 2: 50 * 60}
    )
    assert minutes == 35


def test_halftime_role_change_neither_loses_nor_duplicates_minutes():
    player = {
        "positions": [
            position(end="45:00", end_period=2, pos=4),
            position(start="45:00", start_period=2, pos=6),
        ]
    }
    minutes, roles = player_minutes(player, {1: 48 * 60, 2: 50 * 60})
    assert minutes == 98
    assert roles == {"Central": 48, "Lateral / carrilero": 50}


def test_duplicate_intervals_do_not_double_playing_time():
    minutes, _ = player_minutes({"positions": [position(), position()]}, {1: 45 * 60, 2: 45 * 60})
    assert minutes == 90


def test_unused_substitute_has_no_minutes():
    assert player_minutes({"positions": []}, {1: 2700, 2: 2700}) == (0, Counter())


def test_extra_time_included_and_shootout_ignored():
    events = [
        {"period": p, "timestamp": timestamp}
        for p, timestamp in [
            (1, "00:47:00.000"),
            (2, "00:49:00.000"),
            (3, "00:16:00.000"),
            (4, "00:17:00.000"),
            (5, "01:00:00.000"),
        ]
    ]
    lengths = period_lengths(events)
    assert player_minutes({"positions": [position()]}, lengths)[0] == 129
    assert action_counts({"period": 5, "type": {"name": "Shot"}}) == Counter()


def pass_event(start=None, end=None, **pass_extra):
    return {
        "period": 1,
        "type": {"name": "Pass"},
        "location": start or [70, 40],
        "pass": {"end_location": end or [105, 40], **pass_extra},
    }


def test_completed_progressive_pass_enters_third_and_box():
    counts = action_counts(pass_event())
    for key in (
        "passes",
        "completed_passes",
        "progressive_passes",
        "final_third_entries",
        "box_entries",
    ):
        assert counts[key] == 1


def test_failed_pass_is_not_a_completed_progression_or_entry():
    counts = action_counts(pass_event(outcome={"name": "Incomplete"}))
    assert counts["passes"] == 1
    assert counts["completed_passes"] == 0
    assert counts["progressive_passes"] == 0
    assert counts["box_entries"] == 0


def test_pressure_completion_is_counted():
    event = pass_event()
    event["under_pressure"] = True
    assert action_counts(event)["pressured_completions"] == 1


def test_set_pieces_are_excluded_from_open_play():
    counts = action_counts(pass_event(type={"name": "Corner"}))
    assert counts["passes"] == 0
    assert counts["box_entries"] == 0


def test_backwards_and_short_passes_are_not_progressive():
    assert action_counts(pass_event([70, 40], [65, 40]))["progressive_passes"] == 0
    assert action_counts(pass_event([70, 40], [75, 40]))["progressive_passes"] == 0


def test_missing_location_retains_volume_without_inventing_distance():
    event = pass_event()
    event.pop("location")
    counts = action_counts(event)
    assert counts["completed_passes"] == 1
    assert counts["progressive_passes"] == 0


def test_winning_tackle_is_counted_but_lost_interception_is_not():
    tackle = {
        "type": {"name": "Duel"},
        "duel": {"type": {"name": "Tackle"}, "outcome": {"name": "Won"}},
    }
    lost = {"type": {"name": "Interception"}, "interception": {"outcome": {"name": "Lost"}}}
    assert action_counts(tackle)["defensive_actions"] == 1
    assert action_counts(lost)["defensive_actions"] == 0


@pytest.fixture
def source_data(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "lineups").mkdir()
    events = [
        {"period": 1, "timestamp": "00:45:00.000", "type": {"name": "Half End"}},
        {"period": 2, "timestamp": "00:45:00.000", "type": {"name": "Half End"}},
    ]
    for event in [pass_event(), pass_event(outcome={"name": "Incomplete"})]:
        event.update({"timestamp": "00:10:00.000", "player": {"id": 1}, "team": {"id": 2}})
        events.append(event)
    lineup = [
        {
            "team_id": 2,
            "team_name": "Test FC",
            "lineup": [{"player_id": 1, "player_name": "Test Player", "positions": [position()]}],
        }
    ]
    manifest = {"match_ids": [10], "competition_id": 37, "season_id": 281}
    for name, content in [
        ("events/10.json", events),
        ("lineups/10.json", lineup),
        ("manifest.json", manifest),
    ]:
        (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")
    return tmp_path


def test_pipeline_aggregates_rates_and_percentage_differently(source_data):
    tmp_path = source_data
    frame, _ = build_profiles(tmp_path / "manifest.json", tmp_path / "out")
    row = frame.iloc[0]
    assert row["minutes"] == 90
    assert row["passes_p90"] == 2
    assert row["completion_pct"] == 50
    assert row["progressive_passes_p90"] == 1
    assert (tmp_path / "out/player_matches.csv").exists()


def test_bad_match_is_excluded_before_any_statistics_are_accumulated(source_data):
    root = source_data
    lineup = json.loads((root / "lineups/10.json").read_text())
    lineup[0]["lineup"].append(
        {
            "player_id": 2,
            "player_name": "Invalid Player",
            "positions": [position(start="75:00", end="60:00", start_period=2, end_period=2)],
        }
    )
    (root / "lineups/11.json").write_text(json.dumps(lineup))
    (root / "events/11.json").write_bytes((root / "events/10.json").read_bytes())
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["match_ids"].append(11)
    (root / "manifest.json").write_text(json.dumps(manifest))
    frame, meta = build_profiles(root / "manifest.json", root / "out")
    assert frame.iloc[0]["minutes"] == 90
    assert frame.iloc[0]["matches"] == 1
    assert meta["used_match_ids"] == [10]
    assert meta["excluded_matches"][0]["match_id"] == 11
    assert (root / "out/quality_report.json").exists()


def test_hash_mismatch_stops_build_without_writing_profiles(source_data):
    root = source_data
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["sha256"] = {"events/10.json": "invalid_hash"}
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="SHA-256"):
        build_profiles(root / "manifest.json", root / "out")
    assert not (root / "out/profiles.csv").exists()


def test_distinct_overlapping_position_intervals_are_rejected():
    player = {
        "positions": [
            position(end="70:00", end_period=2),
            position(start="60:00", start_period=2, pos=4),
        ]
    }
    with pytest.raises(ValueError, match="solapados"):
        player_minutes(player, {1: 2700, 2: 2700})


def test_invalid_period_sequence_fails_loudly():
    with pytest.raises(ValueError, match="Periodos"):
        period_lengths([{"period": 2, "timestamp": "00:45:00.000"}])
