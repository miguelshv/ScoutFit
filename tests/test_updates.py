import json
from urllib.error import URLError

import numpy as np
import pandas as pd
import pytest

import scoutfit.espn as espn
import scoutfit.updates as updates
from scoutfit.datasets import active_directory
from scoutfit.update_view import preserve_search


@pytest.fixture
def provider(monkeypatch):
    year = 2026
    teams = [{"team": {"id": str(t), "displayName": f"Club {t}"}} for t in range(1, 21)]
    payloads = {
        f"{espn.SITE}/scoreboard": {"leagues": [{"season": {"year": year}}]},
        f"{espn.SITE}/teams?season={year}&limit=100": {
            "sports": [{"leagues": [{"id": "740", "season": {"year": year}, "teams": teams}]}]
        },
    }
    for team in range(1, 21):
        athletes = []
        for pid in (2 * team - 1, 2 * team):
            athletes.append(
                {
                    "id": str(pid),
                    "displayName": f"Player {pid}",
                    "gender": "MALE",
                    "position": {"abbreviation": "M"},
                }
            )
            stats = {name: float(10 + pid) for name in espn.COUNTS.values()}
            stats.update(minutes=900.0, appearances=10.0, totalPasses=100 + pid, accuratePasses=80)
            payloads[f"{espn.CORE}/seasons/{year}/types/1/athletes/{pid}/statistics/0"] = {
                "season": {
                    "$ref": f"https://sports.core.api.espn.com/v2/sports/soccer/leagues/esp.1/seasons/{year}"
                },
                "athlete": {
                    "$ref": f"https://sports.core.api.espn.com/v2/sports/soccer/leagues/esp.1/athletes/{pid}"
                },
                "splits": {
                    "categories": [{"stats": [{"name": n, "value": v} for n, v in stats.items()]}]
                },
            }
        payloads[f"{espn.SITE}/teams/{team}/roster?season={year}"] = {
            "season": {"year": year},
            "team": {"id": str(team)},
            "athletes": athletes,
        }

    def fetch(url):
        return json.dumps(payloads[url]).encode()

    monkeypatch.setattr(espn, "fetch_bytes", fetch)
    return payloads


def test_update_stages_and_validates_before_activation_and_keeps_user_records(tmp_path, provider):
    path = tmp_path / "data/user/projects.json"
    path.parent.mkdir(parents=True)
    path.write_text('[{"name":"Real project"}]')
    phases = []
    frame, meta, report = updates.update_dataset(
        tmp_path, progress=lambda phase, done, total: phases.append(phase)
    )
    assert len(frame) == 40
    assert not report["comparable"]
    assert report["status"] == "success"
    active = active_directory(tmp_path / "data/processed")
    assert active.name == meta["snapshot"]
    assert (
        json.loads((active / "update_report.json").read_text())["after_snapshot"]
        == meta["snapshot"]
    )
    assert (tmp_path / "data/raw/espn" / meta["snapshot"] / "manifest.json").exists()
    assert path.read_text() == '[{"name":"Real project"}]'
    assert {"competition", "rosters", "statistics", "profiles", "validation", "publishing"} <= set(
        phases
    )
    assert not list((tmp_path / "data/updates").glob("staging-*"))


def test_summary_tracks_identity_by_player_not_roster_profile_id(tmp_path, provider):
    before, before_meta, _ = updates.update_dataset(tmp_path)
    after = before.copy()
    after.loc[after.player_id.eq(1), ["team_id", "team_name", "profile_id"]] = [
        2,
        "Club 2",
        "espn:1:2",
    ]
    after.loc[after.player_id.eq(2), "minutes"] += 90
    after.loc[after.player_id.eq(3), "minutes"] -= 90
    after.loc[after.player_id.eq(4), "passes_p90"] += 0.01
    after = after.loc[after.player_id.ne(40)]
    new = after.iloc[[0]].assign(player_id=41, player_name="New player", profile_id="espn:41:1")
    after = pd.concat([after, new], ignore_index=True)
    meta = {**before_meta, "snapshot": "next", "downloaded_at": "2026-10-30T12:00:00Z"}
    report = updates.compare_datasets(before, before_meta, after, meta)
    assert [r["player_id"] for r in report["new_profiles"]] == [41]
    assert [r["player_id"] for r in report["removed_profiles"]] == [40]
    assert [r["player_id"] for r in report["team_changes"]] == [1]
    changes = {r["player_id"]: r for r in report["statistics_changes"]}
    assert changes[2]["minutes_delta"] == 90
    assert changes[3]["correction"]
    assert (
        changes[4]["changes"]["passes_p90"]["after"] > changes[4]["changes"]["passes_p90"]["before"]
    )


def test_unchanged_and_cross_season_reports_do_not_invent_transfers(tmp_path, provider):
    before, meta, _ = updates.update_dataset(tmp_path)
    same = updates.compare_datasets(before, meta, before.copy(), {**meta, "snapshot": "next"})
    assert same["comparable"]
    assert not any(
        same[key]
        for key in (
            "new_profiles",
            "removed_profiles",
            "team_changes",
            "statistics_changes",
            "identity_changes",
        )
    )
    changed = updates.compare_datasets(before, meta, before, {**meta, "season_id": 2027})
    assert not changed["comparable"]
    assert not changed["team_changes"]


def test_update_publishes_json_report_when_statistics_change(tmp_path, provider):
    _, previous, _ = updates.update_dataset(tmp_path)
    for pid, minutes, appearances in ((1, 990, 11), (2, 810, 9)):
        payload = provider[f"{espn.CORE}/seasons/2026/types/1/athletes/{pid}/statistics/0"]
        for stat in payload["splits"]["categories"][0]["stats"]:
            if stat["name"] == "minutes":
                stat["value"] = minutes
            elif stat["name"] == "appearances":
                stat["value"] = appearances
    _, current, report = updates.update_dataset(tmp_path)
    active = active_directory(tmp_path / "data/processed")
    assert active.name == current["snapshot"] != previous["snapshot"]
    saved = json.loads((active / "update_report.json").read_text(encoding="utf-8"))
    assert saved == report
    changes = {r["player_id"]: r for r in saved["statistics_changes"]}
    assert changes[1]["minutes_delta"] == 90
    assert changes[1]["correction"] is False
    assert changes[2]["minutes_delta"] == -90
    assert changes[2]["correction"] is True


@pytest.mark.parametrize("failure", ["download", "build", "validation", "activate"])
def test_failed_update_keeps_previous_dataset_and_latest_pointer(
    tmp_path, provider, monkeypatch, failure
):
    _, meta, _ = updates.update_dataset(tmp_path)
    pointer = tmp_path / "data/processed/active.json"
    latest = tmp_path / "data/raw/espn/latest.json"
    original, raw_pointer = pointer.read_bytes(), latest.read_bytes()

    def fail(*args, **kwargs):
        raise OSError(f"Simulated {failure} failure")

    monkeypatch.setattr(
        updates,
        {
            "download": "download_current",
            "build": "build_current",
            "validation": "validate_dataset",
            "activate": "activate",
        }[failure],
        fail,
    )
    with pytest.raises(updates.UpdateError, match=failure):
        updates.update_dataset(tmp_path)
    assert pointer.read_bytes() == original
    assert latest.read_bytes() == raw_pointer
    assert active_directory(tmp_path / "data/processed").name == meta["snapshot"]
    assert (
        json.loads((tmp_path / "data/updates/last_attempt.json").read_text())["status"] == "failed"
    )
    assert not list((tmp_path / "data/updates").glob("staging-*"))


def test_validation_rejects_low_coverage_and_nonfinite_statistics(tmp_path, provider):
    frame, meta, _ = updates.update_dataset(tmp_path)
    with pytest.raises(ValueError, match="85"):
        updates.validate_dataset(frame.iloc[:30], meta)
    with pytest.raises(ValueError, match="incompletas"):
        updates.validate_dataset(frame.assign(passes_p90=np.nan), meta)
    with pytest.raises(ValueError, match="20 %"):
        updates.validate_dataset(
            frame.iloc[:30], {**meta, "player_ids_requested": list(range(30))}, frame, meta
        )
    with pytest.raises(ValueError, match="20 clubes"):
        updates.validate_dataset(frame, {**meta, "team_count": 19})


def test_lock_rejects_simultaneous_updates_and_releases_on_failure(tmp_path):
    lock = tmp_path / "update.lock"
    with updates.update_lock(lock):
        with pytest.raises(updates.UpdateInProgress):
            with updates.update_lock(lock):
                pytest.fail("Acquired a second update lock")
    with pytest.raises(RuntimeError):
        with updates.update_lock(lock):
            raise RuntimeError("Interrupted")
    with updates.update_lock(lock):
        pass


def test_download_connection_failure_does_not_publish_initial_data(tmp_path, monkeypatch):
    def fail(url):
        raise URLError("offline")

    monkeypatch.setattr(espn, "fetch_bytes", fail)
    with pytest.raises(updates.UpdateError, match="offline"):
        updates.update_dataset(tmp_path)
    assert not (tmp_path / "data/processed/active.json").exists()
    assert not (tmp_path / "data/raw/espn/latest.json").exists()


def test_preserve_search_follows_transfer_but_does_not_change_projects(tmp_path, provider):
    frame, meta, _ = updates.update_dataset(tmp_path)
    selected = frame.loc[frame.player_id.eq(1)].iloc[0]
    state = {
        "reference_player": selected.profile_id,
        "reference_team": "Club 1",
        "reference_position": "Mediocentro",
        "active_project": "keep-me",
        "player_search": "Player 1",
    }
    after = frame.copy()
    after.loc[after.player_id.eq(1), ["team_id", "team_name", "profile_id"]] = [
        2,
        "Club 2",
        "espn:1:2",
    ]
    preserve_search(state, frame, meta, after, meta)
    assert state["reference_player"] == "espn:1:2"
    assert state["reference_team"] == "Todos"
    assert state["active_project"] == "keep-me"


def test_competing_activation_is_not_overwritten(tmp_path, provider):
    updates.update_dataset(tmp_path)
    other = tmp_path / "data/processed/other"
    other.mkdir()

    def progress(phase, done, total):
        if phase == "publishing":
            updates.activate(tmp_path / "data/processed", other)

    with pytest.raises(updates.UpdateError, match="Otro proceso"):
        updates.update_dataset(tmp_path, progress=progress)
    assert active_directory(tmp_path / "data/processed") == other.resolve()
