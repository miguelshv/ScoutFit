import copy
import json
from datetime import timedelta

import pandas as pd
import pytest

from scoutfit.datasets import ESPN_FEATURES
from scoutfit.dossier import dossier_html, individual_dossier
from scoutfit.observations import (
    append_observation,
    local_today,
    observation_history,
    save_assessment,
    video_position,
)
from scoutfit.projects import add_candidate, create_project, project_by_id, update_candidate


@pytest.fixture
def notebook(tmp_path):
    players = pd.DataFrame(
        [
            {
                "profile_id": f"espn:{i}:{i}",
                "player_id": i,
                "player_name": f"Player {i}",
                "team_id": i,
                "team_name": f"Club {i}",
                "role": "Mediocentro",
                "provider": "espn",
                "competition_id": 740,
                "season_id": 2026,
                "minutes": 900,
                "matches": 10,
                "inferred_role": "Mediocentro creador",
                **{
                    f: (70 + i if f == "completion_pct" else float(i + j))
                    for j, f in enumerate(ESPN_FEATURES)
                },
            }
            for i in range(1, 10)
        ]
    )
    meta = {
        "provider": "espn",
        "source": "ESPN",
        "competition": "LaLiga masculina",
        "season": "2026/27",
        "snapshot": "current",
        "downloaded_at": "2026-11-03T12:00:00Z",
    }
    path = tmp_path / "data/user/projects.json"
    project_id = create_project(path, "Cuaderno de prueba")
    add_candidate(path, project_id, players.iloc[0], meta)
    candidate = project_by_id(path, project_id)["candidates"][0]
    return path, project_id, candidate["key"], players, meta


def observation(**patch):
    return {
        "observed_on": "2020-06-01",
        "context": "Vídeo de prueba",
        "strengths": "Texto sintético",
        "doubts": "Pendiente de contraste",
        "next_step": "Segunda revisión",
        **patch,
    }


def test_observations_append_without_overwriting_legacy_note_status_or_assessment(notebook):
    path, pid, key, _, _ = notebook
    update_candidate(path, pid, key, "Interesante", "Nota general anterior")
    save_assessment(path, pid, key, "Seguir mirando", "Motivo de prueba", "Revisor de prueba")
    first = append_observation(path, pid, key, observation(), "old")
    previous = project_by_id(path, pid)["candidates"][0]
    immutable = copy.deepcopy(previous["observations"][0])
    second = append_observation(
        path,
        pid,
        key,
        observation(observed_on="2020-05-01", context="Observación retrospectiva"),
        "current",
    )
    candidate = project_by_id(path, pid)["candidates"][0]
    assert first != second and len(candidate["observations"]) == 2
    assert candidate["observations"][0] == immutable
    assert [r["id"] for r in observation_history(candidate)] == [first, second]
    assert candidate["note"] == "Nota general anterior" and candidate["status"] == "Interesante"
    assert candidate["assessment"]["author"] == "Revisor de prueba"
    assert candidate["observations"][1]["statistics_snapshot"] == "current"


@pytest.mark.parametrize(
    "patch",
    [
        {"observed_on": "not-a-date"},
        {"observed_on": (local_today() + timedelta(days=1)).isoformat()},
        {"context": ""},
        {"context": "x" * 201},
        {"strengths": "", "doubts": "", "next_step": ""},
        {"video_url": "javascript:alert(1)"},
        {"video_url": "file:///private.mp4"},
        {"video_url": "https://user:password@example.test/video"},
        {"video_url": "https://example.test/vid\neo"},
        {"video_position": "12:34"},
        {"video_url": "https://example.test/video", "video_position": "12:90"},
    ],
)
def test_invalid_observation_never_writes_or_changes_previous_records(notebook, patch):
    path, pid, key, _, _ = notebook
    previous = path.read_bytes()
    with pytest.raises(ValueError):
        append_observation(path, pid, key, observation(**patch))
    assert path.read_bytes() == previous


def test_video_position_is_explicit_and_original_url_is_preserved(notebook):
    path, pid, key, _, _ = notebook
    url = "https://example.test/video?t=12&chapter=3#original"
    append_observation(path, pid, key, observation(video_url=url, video_position="01:02:03"))
    entry = project_by_id(path, pid)["candidates"][0]["observations"][0]
    assert entry["video_url"] == url and entry["video_seconds"] == 3723
    assert video_position(entry["video_seconds"]) == "01:02:03"
    assert video_position(None) == ""


def test_assessment_requires_a_human_reason_and_does_not_change_tracking_status(notebook):
    path, pid, key, _, _ = notebook
    previous = path.read_bytes()
    with pytest.raises(ValueError):
        save_assessment(path, pid, key, "Descartar", "")
    with pytest.raises(ValueError):
        save_assessment(path, pid, key, "Automatic model verdict", "Reason")
    assert path.read_bytes() == previous
    save_assessment(path, pid, key, "Descartar", "Motivo de prueba", "Alias de prueba")
    candidate = project_by_id(path, pid)["candidates"][0]
    assert candidate["assessment"]["verdict"] == "Descartar"
    assert candidate["status"] == "Pendiente de revisar"


def test_dossier_uses_scoped_statistics_and_separate_human_fields_after_transfer(notebook):
    path, pid, key, players, meta = notebook
    append_observation(path, pid, key, observation(), "old")
    save_assessment(path, pid, key, "Encaja parcialmente", "Justificación humana", "Firma personal")
    project = project_by_id(path, pid)
    candidate = project["candidates"][0]
    transferred = players.copy()
    transferred.loc[0, ["team_id", "team_name", "profile_id"]] = [99, "New club", "espn:1:99"]
    unchanged = copy.deepcopy(project)
    report = individual_dossier(transferred, meta, project, candidate)
    assert report["statistics"]["team_name"] == "New club" and report["team_at_save"] == "Club 1"
    assert report["statistics"]["cohort_size"] == 9
    assert len(report["statistics"]["metrics"]) == 12
    assert report["assessment"]["rationale"] == "Justificación humana"
    assert len(report["observations"]) == 1 and project == unchanged
    json.dumps(report, allow_nan=False)


def test_dossier_leaves_low_minutes_without_percentiles_until_threshold_is_explicitly_lowered(
    notebook,
):
    path, pid, _, players, meta = notebook
    players.loc[0, "minutes"] = 90
    project = project_by_id(path, pid)
    report = individual_dossier(players, meta, project, project["candidates"][0])
    assert report["statistics"]["minimum_minutes"] == 450
    assert all(m["percentile"] is None for m in report["statistics"]["metrics"])
    assert "no alcanza" in report["statistics_note"]
    explicit = individual_dossier(players, meta, project, project["candidates"][0], minimum=90)
    assert explicit["statistics"]["cohort_size"] == 9
    assert all(m["percentile"] is not None for m in explicit["statistics"]["metrics"])


@pytest.mark.parametrize("change", ["missing", "other_season", "ambiguous"])
def test_dossier_never_mixes_statistics_when_identity_is_not_unique_and_comparable(
    notebook, change
):
    path, pid, _, players, meta = notebook
    project = project_by_id(path, pid)
    if change == "missing":
        players = players.iloc[1:]
    elif change == "other_season":
        players = players.assign(season_id=2027)
    else:
        players = pd.concat([players, players.iloc[[0]]], ignore_index=True)
    report = individual_dossier(players, meta, project, project["candidates"][0])
    assert report["statistics"] is None
    html = dossier_html(report)
    assert "Sin conclusión" in html and "Firma no añadida" in html
    assert "Todavía no hay observaciones registradas" in html


def test_report_escapes_human_and_source_text_and_contains_no_external_assets(notebook):
    path, pid, key, players, meta = notebook
    payload = '<script>alert("test")</script>'
    append_observation(
        path,
        pid,
        key,
        observation(
            context=payload,
            strengths=payload,
            video_url="https://example.test/video?a=1&b=2",
            video_position="12:34",
        ),
    )
    save_assessment(path, pid, key, "Seguir mirando", payload, payload)
    project = project_by_id(path, pid)
    project["name"] = payload
    players.loc[0, "player_name"] = payload
    html = dossier_html(individual_dossier(players, meta, project, project["candidates"][0]))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "src=" not in html and "<iframe" not in html
    assert 'href="https://example.test/video?a=1&amp;b=2"' in html
    assert "Posición anotada: 12:34" in html and "@media print" in html
    assert "Firma:" in html and "Población: 9" in html
