import copy
import hashlib
import json

import pandas as pd
import pytest

from scoutfit.biographies import biography, enrich_biographies, media_url
from scoutfit.datasets import ESPN_FEATURES
from scoutfit.projects import (
    add_candidate,
    create_project,
    prepare_search_state,
    project_by_id,
    save_search,
    scope_for,
    update_candidate,
)


@pytest.fixture
def environment():
    frame = pd.DataFrame(
        [
            {
                "profile_id": "espn:1:83",
                "player_id": 1,
                "player_name": "Player",
                "team_id": 83,
                "team_name": "Club",
                "minutes": 900,
                "role": "Mediocentro",
                "competition_id": 740,
                "season_id": 2026,
                "inferred_role": "Mediocentro creador",
            },
        ]
    )
    meta = {"provider": "espn", "snapshot": "test", "downloaded_at": "2026-10-29T12:00:00Z"}
    config = {
        "mode": "similarity",
        "reference_id": "espn:1:83",
        "reference_player_id": 1,
        "minimum_minutes": 450,
        "top_k": 5,
        "weights": dict.fromkeys(ESPN_FEATURES, 1),
        "exclude_team": True,
        "match_inferred_role": True,
        "candidate_filters": {
            "include_teams": [83],
            "exclude_teams": [],
            "min_minutes": 500,
            "max_minutes": 1000,
        },
    }
    return frame, meta, config


def test_biography_uses_age_at_snapshot_and_converts_inches_without_filling_foot():
    bio = biography(
        {"dateOfBirth": "2002-11-25T08:00Z", "age": 99, "height": 69, "citizenship": "Spain"},
        {},
        "2026-10-29T12:00:00Z",
    )
    assert bio["bio_age"] == 23
    assert bio["bio_height_cm"] == 175
    assert bio["bio_nationality"] == "Spain"
    assert bio["bio_foot"] == ""
    assert biography({}, {}, "2026-10-29T12:00:00Z")["bio_age"] is None
    assert biography({"height": float("nan")}, {}, "")["bio_height_cm"] is None


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://evil.test/photo.png",
        "http://a.espncdn.com/x",
        "https://a.espncdn.com@evil.test/x",
    ],
)
def test_only_provider_media_urls_are_rendered(url):
    assert media_url(url) == ""
    assert biography({"headshot": {"href": url}}, {}, "")["bio_photo_url"] == ""


def test_biographies_require_roster_checksum_and_matching_team(tmp_path, environment):
    frame, meta, _ = environment
    folder = tmp_path / "data/raw/espn/test"
    (folder / "rosters").mkdir(parents=True)
    team = {"id": "83", "logos": [{"href": "https://a.espncdn.com/i/83.png"}]}
    catalog = {
        "sports": [
            {"leagues": [{"id": "740", "season": {"year": 2026}, "teams": [{"team": team}]}]}
        ]
    }
    roster = {
        "season": {"year": 2026},
        "team": {"id": "83"},
        "athletes": [
            {"id": "1", "gender": "MALE", "age": 23, "citizenship": "Spain"},
        ],
    }
    checksums = {}
    for name, data in [("teams.json", catalog), ("rosters/83.json", roster)]:
        raw = json.dumps(data).encode()
        (folder / name).write_bytes(raw)
        checksums[name] = hashlib.sha256(raw).hexdigest()
    (folder / "manifest.json").write_text(
        json.dumps({"snapshot": "test", "season_id": 2026, "sha256": checksums})
    )
    enriched, errors = enrich_biographies(frame, tmp_path, meta)
    assert not errors
    assert enriched.iloc[0]["bio_age"] == 23
    assert "bio_age" not in frame
    (folder / "rosters/83.json").write_text("{}")
    failed, errors = enrich_biographies(frame, tmp_path, meta)
    assert errors
    assert failed.iloc[0]["bio_age"] is None
    assert failed.iloc[0]["bio_team_logo_url"] == ""


def test_projects_persist_separately_and_duplicate_candidates_keep_status(tmp_path, environment):
    frame, meta, _ = environment
    path = tmp_path / "projects.json"
    first = create_project(path, "Mediocentro", "Necesidad de la plantilla")
    second = create_project(path, "Defensa")
    add_candidate(path, first, frame.iloc[0], meta)
    identity = project_by_id(path, first)["candidates"][0]["key"]
    update_candidate(path, first, identity, "Interesante", "Revisar sin balón")
    moved = frame.iloc[0].copy()
    moved["profile_id"], moved["team_id"], moved["team_name"] = "espn:1:99", 99, "New club"
    add_candidate(path, first, moved, meta)
    stored = project_by_id(path, first)
    assert len(stored["candidates"]) == 1
    assert stored["candidates"][0]["status"] == "Interesante"
    assert stored["candidates"][0]["team_at_save"] == "Club"
    assert not project_by_id(path, second)["candidates"]
    before = path.read_bytes()
    with pytest.raises(ValueError):
        update_candidate(path, first, identity, "Inventado", "")
    assert path.read_bytes() == before


def test_searches_round_trip_and_update_by_name_without_duplicate(tmp_path, environment):
    frame, meta, config = environment
    path = tmp_path / "projects.json"
    pid = create_project(path, "Proyecto")
    save_search(path, pid, "Búsqueda", config, frame, meta)
    config["top_k"] = 3
    save_search(path, pid, "Búsqueda", config, frame, meta)
    saved = project_by_id(path, pid)["searches"]
    assert len(saved) == 1
    state = prepare_search_state(saved[0]["config"], frame, meta, saved[0]["scope"])
    assert state["top_k"] == 3
    assert state["custom_weights"] is True
    assert state["candidate_max_minutes"] == 1000
    assert state["candidate_teams_include"] == [83]


def test_target_restores_custom_goals_and_importances(environment):
    frame, meta, _ = environment
    config = {
        "mode": "target",
        "position": "Mediocentro",
        "preset": "Personalizado",
        "minimum_minutes": 600,
        "top_k": 8,
        "goals": {"passes_p90": 85},
        "weights": {"passes_p90": 4},
        "strict": True,
    }
    state = prepare_search_state(config, frame, meta)
    token = "Mediocentro_Personalizado"
    assert state["search_mode"] == "Por objetivo"
    assert state[f"target_features_{token}"] == ["passes_p90"]
    assert state[f"target_goal_{token}_passes_p90"] == 85
    assert state[f"target_weight_{token}_passes_p90"] == 4
    assert state["target_strict"]


def test_reference_follows_player_id_after_transfer_and_unknown_scope_is_rejected(environment):
    frame, meta, config = environment
    moved = frame.assign(profile_id="espn:1:99", team_id=99)
    config["candidate_filters"] = {}
    assert prepare_search_state(config, moved, meta)["reference_player"] == "espn:1:99"
    with pytest.raises(ValueError, match="otra liga"):
        prepare_search_state(config, moved, meta, {**scope_for(frame, meta), "season_id": 2025})
    with pytest.raises(ValueError, match="referencia"):
        prepare_search_state(config, frame.assign(minutes=100), meta)


def test_invalid_saved_search_is_rejected_before_writing(tmp_path, environment):
    frame, meta, config = environment
    path = tmp_path / "projects.json"
    pid = create_project(path, "Proyecto")
    before = path.read_bytes()
    wrong = copy.deepcopy(config)
    wrong["priority"] = "Unknown"
    with pytest.raises(ValueError):
        save_search(path, pid, "No válida", wrong, frame, meta)
    assert path.read_bytes() == before
    wrong = copy.deepcopy(config)
    wrong["candidate_filters"]["include_teams"] = [999]
    with pytest.raises(ValueError, match="club"):
        prepare_search_state(wrong, frame, meta)


def test_project_names_and_notes_are_bounded(tmp_path):
    path = tmp_path / "projects.json"
    with pytest.raises(ValueError):
        create_project(path, " ")
    assert not path.exists()
    create_project(path, "Proyecto")
    with pytest.raises(ValueError):
        create_project(path, "proyecto")
