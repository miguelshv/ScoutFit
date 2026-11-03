import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scoutfit.datasets import ESPN_FEATURES
from scoutfit.features import FEATURES

APP_SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def app_at(root):
    source = APP_SOURCE.replace(
        "ROOT = Path(__file__).resolve().parent", f"ROOT = Path({str(root)!r})"
    )
    return AppTest.from_string(source, default_timeout=30)


def test_missing_data_explains_setup(tmp_path):
    app = app_at(tmp_path).run()
    assert not app.exception
    assert "Prepara los datos" in app.info[0].value


def test_app_supports_comparison_and_empty_filter(tmp_path):
    data = tmp_path / "data/processed"
    data.mkdir(parents=True)
    rows = [
        {
            "profile_id": f"{pid}:10",
            "player_id": pid,
            "player_name": f"Player {pid}",
            "team_id": pid,
            "team_name": f"Team {pid}",
            "role": "Mediocentro",
            "minutes": 900,
            "matches": 10,
            "role_share": 1,
            "competition_id": 37,
            "season_id": 281,
            **dict.fromkeys(FEATURES, pid),
        }
        for pid in (1, 2, 3)
    ]
    pd.DataFrame(rows).to_csv(data / "profiles.csv", index=False)
    metadata = {
        "partial": False,
        "competition": "Test League",
        "season": "2023/24",
        "match_ids": [1],
        "used_match_ids": [1],
        "excluded_matches": [],
        "revision": "test",
        "downloaded_at": "2026-10-28T00:00:00Z",
    }
    (data / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    app = app_at(tmp_path).run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 2
    app.radio[0].set_value("Defensa").run()
    assert not app.exception
    app.number_input[0].set_value(5000).run()
    assert not app.exception
    assert "No hay perfiles" in app.warning[0].value


def test_current_laliga_labels_team_filter_and_creation_priority(tmp_path):
    data = tmp_path / "data/processed"
    data.mkdir(parents=True)
    rows = [
        {
            "profile_id": f"espn:{pid}:{pid}",
            "player_id": pid,
            "player_name": f"Player {pid}",
            "team_id": pid,
            "team_name": f"Team {pid}",
            "role": "Mediocentro",
            "minutes": 900,
            "matches": 10,
            "role_share": None,
            "competition_id": 740,
            "season_id": 2026,
            **dict.fromkeys(ESPN_FEATURES, pid),
        }
        for pid in (1, 2, 3)
    ]
    pd.DataFrame(rows).to_csv(data / "profiles.csv", index=False)
    metadata = {
        "provider": "espn",
        "source": "ESPN",
        "competition": "LaLiga masculina",
        "season": "2026/2027",
        "partial": False,
        "team_count": 3,
        "profiles": 3,
        "excluded_profiles": [],
        "snapshot": "test",
        "downloaded_at": "2026-10-28T16:00:00Z",
    }
    (data / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    app = app_at(tmp_path).run()
    assert not app.exception
    assert any("LaLiga masculina" in item.value for item in app.markdown)
    assert any("28/10/2026" in item.value for item in app.caption)
    assert "Equipo de plantilla" in app.dataframe[0].value.columns
    assert "Fracción en rol principal" not in app.dataframe[0].value.columns
    next(widget for widget in app.selectbox if widget.label == "Equipo de referencia").set_value(
        "Team 1"
    ).run()
    assert not app.exception
    assert set(app.dataframe[0].value["Equipo de plantilla"]) == {"Team 2", "Team 3"}
    app.radio[0].set_value("Creación").run()
    assert not app.exception


@pytest.fixture
def searchable_app(tmp_path):
    data = tmp_path / "data/processed"
    data.mkdir(parents=True)
    generator = np.random.default_rng(12)
    rows = []
    for pid in range(1, 25):
        team = (pid % 3) + 1
        name = {1: "Pedri", 2: "Jude Bellingham", 3: "Álex Baena"}.get(pid, f"Player {pid:02}")
        rows.append(
            {
                "profile_id": f"espn:{pid}:{team}",
                "player_id": pid,
                "player_name": name,
                "team_id": team,
                "team_name": f"Team {team}",
                "role": "Mediocentro" if pid <= 12 else "Defensa",
                "minutes": 900,
                "matches": 10,
                "role_share": None,
                "competition_id": 740,
                "season_id": 2026,
                **dict(zip(ESPN_FEATURES, generator.uniform(0, 10, len(ESPN_FEATURES)))),
            }
        )
    pd.DataFrame(rows).to_csv(data / "profiles.csv", index=False)
    metadata = {
        "provider": "espn",
        "source": "ESPN",
        "competition": "LaLiga masculina",
        "season": "2026/2027",
        "partial": False,
        "team_count": 3,
        "profiles": 24,
        "excluded_profiles": [],
        "snapshot": "test",
        "downloaded_at": "2026-10-28T16:00:00Z",
    }
    (data / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    app = app_at(tmp_path).run()
    assert not app.exception
    return app


def test_player_selection_survives_priority_count_and_reload(searchable_app):
    app = searchable_app
    app.selectbox(key="reference_player").set_value("espn:2:3").run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:2:3"
    app.radio(key="priority").set_value("Defensa").run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:2:3"
    app.slider(key="top_k").set_value(3).run()
    assert app.selectbox(key="reference_player").value == "espn:2:3"
    next(button for button in app.button if button.label == "Recargar datos locales").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:2:3"


def test_accent_insensitive_search_clear_and_no_results_preserve_player(searchable_app):
    app = searchable_app
    app.text_input(key="player_search").set_value("alex baena").run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:3:1"
    app.text_input(key="player_search").set_value("no such player").run()
    assert not app.exception
    assert any("No hay jugadores" in message.value for message in app.info)
    app.text_input(key="player_search").set_value("").run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:3:1"


def test_dependent_filters_reset_only_an_invalid_selection(searchable_app):
    app = searchable_app
    app.selectbox(key="reference_player").set_value("espn:2:3").run()
    app.selectbox(key="reference_team").set_value("Team 3").run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:2:3"
    app.selectbox(key="reference_team").set_value("Team 1").run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value.endswith(":1")
    app.selectbox(key="reference_position").set_value("Defensa").run()
    assert not app.exception
    selected = app.selectbox(key="reference_player").value
    assert int(selected.split(":")[1]) >= 13


def test_reference_controls_are_in_main_content_and_roles_are_visible(searchable_app):
    app = searchable_app
    assert not app.sidebar.selectbox
    assert app.selectbox(key="reference_player")
    assert any("Perfil inferido" in item.value for item in app.markdown)
    app.checkbox(key="same_profile").uncheck().run()
    assert not app.exception
    assert "Perfil inferido" in app.dataframe[0].value.columns


def test_three_player_comparison_report_and_favorites_persist_across_sessions(
    searchable_app, tmp_path
):
    app = searchable_app
    app.multiselect(key="comparison_extra").set_value(["espn:4:2", "espn:5:3"]).run()
    assert not app.exception
    assert len(app.tabs[1].dataframe[0].value.columns) == 3
    assert any(
        element.proto.label == "Descargar informe HTML" for element in app.get("download_button")
    )
    app.button(key="favorite_comparison").click().run()
    assert not app.exception
    saved = json.loads((tmp_path / "data/user/favorites.json").read_text(encoding="utf-8"))
    assert len(saved) == 3
    second_session = app_at(tmp_path).run()
    assert not second_session.exception
    assert len(second_session.tabs[2].dataframe[0].value) == 3
    next(
        item for item in second_session.text_area if item.label == "Nota de seguimiento"
    ).set_value("Revisar comportamiento sin balón")
    second_session.button(key="favorite_save_note").click().run()
    saved = json.loads((tmp_path / "data/user/favorites.json").read_text(encoding="utf-8"))
    assert any(row["note"] == "Revisar comportamiento sin balón" for row in saved)


def test_evaluation_remains_pending_without_manual_review(searchable_app, tmp_path):
    app = searchable_app
    app.button(key="evaluate_judgments").click().run()
    assert not app.exception
    assert any("Falta revisión suficiente" in item.value for item in app.info)
    assert not (tmp_path / "data/user/judgments.json").exists()


def test_manual_review_enables_only_judged_pool_metrics(searchable_app, tmp_path):
    app = searchable_app
    app.selectbox(key="reference_player").set_value("espn:3:1").run()
    for candidate, grade in [("espn:1:2", "2"), ("espn:2:3", "0")]:
        app.selectbox(key="review_candidate").set_value(candidate).run()
        next(item for item in app.selectbox if item.label == "Relevancia de estilo").set_value(
            grade
        )
        next(
            item for item in app.text_area if item.label == "Justificación de la valoración"
        ).set_value("Justificación sintética para probar el formulario")
        next(item for item in app.button if item.label == "Guardar valoración").click().run()
        assert not app.exception
    records = json.loads((tmp_path / "data/user/judgments.json").read_text(encoding="utf-8"))
    assert len(records) == 2
    app.button(key="evaluate_judgments").click().run()
    assert not app.exception
    assert len(app.tabs[3].dataframe[0].value) == 2
    assert "nDCG@k (revisados)" in app.tabs[3].dataframe[0].value.columns


def test_lab_sensitivity_and_method_comparison_execute_without_changing_reference(searchable_app):
    app = searchable_app
    reference = app.selectbox(key="reference_player").value
    app.button(key="run_sensitivity").click().run()
    assert not app.exception
    assert any("Jaccard" in item.label for item in app.metric)
    app.button(key="compare_methods").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == reference
    assert any("Método" in element.value.columns for element in app.tabs[3].dataframe)


def test_evolution_uses_saved_queries_and_marks_the_interval_as_not_a_match(
    searchable_app, tmp_path
):
    data = tmp_path / "data/processed"
    meta = json.loads((data / "metadata.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(data / "profiles.csv")
    for name, day, added in [("one", 27, 0), ("two", 28, 90)]:
        folder = data / "espn" / name
        folder.mkdir(parents=True)
        source = {**meta, "snapshot": name, "downloaded_at": f"2026-10-{day}T12:00:00Z"}
        (folder / "metadata.json").write_text(json.dumps(source), encoding="utf-8")
        copied = frame.copy()
        copied["minutes"] += added
        copied.to_csv(folder / "profiles.csv", index=False)
    app = searchable_app.run()
    assert not app.exception
    history = app.tabs[4]
    assert len(history.dataframe[0].value) == 2
    assert history.dataframe[1].value["Estado"].str.contains("no es un partido").all()


def test_candidate_shortcut_opens_comparison_with_the_selected_player(searchable_app):
    app = searchable_app
    candidate = next(button for button in app.button if str(button.key).startswith("compare_card_"))
    candidate_id = candidate.key.removeprefix("compare_card_")
    candidate.click().run()
    assert not app.exception
    assert app.session_state["workspace_tab"] == "Comparativa"
    assert app.multiselect(key="comparison_extra").value == [candidate_id]
    assert len(app.tabs[1].dataframe[0].value.columns) == 2


def test_map_can_replace_reference_and_clear_dependent_search_filters(searchable_app):
    app = searchable_app
    app.text_input(key="player_search").set_value("jude").run()
    app.selectbox(key="map_player").set_value("espn:1:2").run()
    app.button(key="map_use_reference").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:1:2"
    assert app.text_input(key="player_search").value == ""
    assert app.selectbox(key="reference_team").value == "Todos"
    assert app.session_state["workspace_tab"] == "Recomendaciones"


def test_custom_weights_zero_guard_and_reset_without_losing_reference(searchable_app):
    app = searchable_app
    reference = app.selectbox(key="reference_player").value
    app.checkbox(key="custom_weights").check().run()
    for feature in ESPN_FEATURES:
        app.slider(key=f"weight_{feature}").set_value(0)
    app.run()
    assert not app.exception
    assert any("Activa al menos una métrica" in item.value for item in app.warning)
    app.button(key="reset_weights").click().run()
    assert not app.exception
    assert app.slider(key="weight_passes_p90").value == 1
    assert app.selectbox(key="reference_player").value == reference
    app.radio(key="priority").set_value("Defensa").run()
    app.button(key="reset_weights").click().run()
    assert app.slider(key="weight_recoveries_p90").value == 3


def test_radar_can_switch_to_exact_standardized_differences(searchable_app):
    app = searchable_app
    next(
        widget for widget in app.get("segmented_control") if widget.key == "recommendation_chart"
    ).set_value("Diferencias por métrica").run()
    assert not app.exception
    assert any("0 = media" in item.value for item in app.caption)


def switch_search_mode(app, mode):
    next(
        widget for widget in app.get("segmented_control") if widget.key == "search_mode"
    ).set_value(mode).run()
    assert not app.exception


def test_candidate_clubs_and_minutes_do_not_change_reference(searchable_app):
    app = searchable_app
    reference = app.selectbox(key="reference_player").value
    app.checkbox(key="same_profile").uncheck().run()
    app.multiselect(key="candidate_teams_include").set_value([1]).run()
    assert not app.exception
    assert set(app.tabs[0].dataframe[0].value["Equipo de plantilla"]) == {"Team 1"}
    assert app.selectbox(key="reference_player").value == reference
    app.multiselect(key="candidate_teams_exclude").set_value([1]).run()
    assert not app.exception
    assert any("No hay candidatos" in message.value for message in app.info)
    assert app.selectbox(key="reference_player").value == reference
    app.button(key="reset_candidate_filters").click().run()
    app.number_input(key="candidate_max_minutes").set_value(800).run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == reference
    assert any("No hay candidatos" in message.value for message in app.info)


def test_target_mode_does_not_need_reference_and_compares_real_players(searchable_app):
    app = searchable_app
    switch_search_mode(app, "Por objetivo")
    assert not any(widget.key == "reference_player" for widget in app.selectbox)
    assert app.selectbox(key="target_position").value == "Mediocentro"
    assert "Brecha objetivo (pp)" in app.tabs[0].dataframe[0].value.columns
    assert len(app.tabs[0].dataframe[0].value) == 5
    assert len(app.multiselect(key="target_comparison_players").value) == 2
    assert any(
        element.proto.label == "Descargar informe de candidatos HTML"
        for element in app.get("download_button")
    )
    assert app.multiselect(key="candidate_teams_include")


def test_target_favorite_and_use_as_reference_keep_real_identity(searchable_app, tmp_path):
    app = searchable_app
    switch_search_mode(app, "Por objetivo")
    inspected = app.selectbox(key="target_inspect").value
    app.button(key="target_favorite").click().run()
    assert not app.exception
    saved = json.loads((tmp_path / "data/user/favorites.json").read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["player_id"] == int(inspected.split(":")[1])
    app.button(key="target_use_reference").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == inspected
    assert app.text_input(key="player_search").value == ""
    assert not any(widget.key == "target_inspect" for widget in app.selectbox)


def test_target_filters_persist_across_modes_and_empty_results_keep_favorites_accessible(
    searchable_app,
):
    app = searchable_app
    app.multiselect(key="candidate_teams_exclude").set_value([1, 2, 3]).run()
    switch_search_mode(app, "Por objetivo")
    assert app.multiselect(key="candidate_teams_exclude").value == [1, 2, 3]
    assert any("No hay candidatos" in message.value for message in app.info)
    assert app.tabs[2].label == "Favoritos"
    app.button(key="reset_candidate_filters").click().run()
    assert not app.exception
    assert len(app.tabs[0].dataframe[0].value) == 5
    assert app.multiselect(key="candidate_teams_exclude").value == []


def test_target_can_be_customized_or_left_empty_without_errors(searchable_app):
    app = searchable_app
    switch_search_mode(app, "Por objetivo")
    app.selectbox(key="target_preset").set_value("Personalizado").run()
    active = next(widget for widget in app.multiselect if widget.key.startswith("target_features_"))
    active.set_value(["passes_p90"]).run()
    goal = next(widget for widget in app.slider if widget.key.startswith("target_goal_"))
    goal.set_value(100)
    app.checkbox(key="target_strict").check().run()
    assert not app.exception
    assert len(app.tabs[0].dataframe[0].value) == 1
    assert app.tabs[0].dataframe[0].value.iloc[0]["Brecha objetivo (pp)"] == 0
    next(
        widget for widget in app.multiselect if widget.key.startswith("target_features_")
    ).set_value([]).run()
    assert not app.exception
    assert any("Selecciona al menos una métrica" in item.value for item in app.info)


def test_invalid_candidate_interval_can_be_reset_in_both_modes(searchable_app):
    app = searchable_app
    for mode in ("Por parecido", "Por objetivo"):
        switch_search_mode(app, mode)
        app.number_input(key="candidate_min_minutes").set_value(1000)
        app.number_input(key="candidate_max_minutes").set_value(500).run()
        assert not app.exception
        assert any("no puede superar el máximo" in item.value for item in app.warning)
        app.button(key="reset_candidate_filters").click().run()
        assert not app.exception


def create_test_project(app):
    app.text_input(key="new_project_name").set_value("Refuerzo de mediocampo")
    app.button(key="create_project").click().run()
    assert not app.exception


def test_project_candidates_status_and_notes_persist_between_sessions(searchable_app, tmp_path):
    app = searchable_app
    create_test_project(app)
    app.button(key="recommendation_project_candidate").click().run()
    assert not app.exception
    next(w for w in app.selectbox if w.label == "Estado de seguimiento").set_value("Interesante")
    next(w for w in app.text_area if w.label == "Nota del candidato en el proyecto").set_value(
        "Revisar movimientos sin balón"
    )
    app.button(key="save_project_candidate").click().run()
    assert not app.exception
    other = app_at(tmp_path).run()
    assert not other.exception
    assert other.selectbox(key="active_project")
    assert (
        next(w for w in other.selectbox if w.label == "Estado de seguimiento").value
        == "Interesante"
    )
    assert (
        next(w for w in other.text_area if w.label == "Nota del candidato en el proyecto").value
        == "Revisar movimientos sin balón"
    )


def test_saved_reference_search_recovers_exact_filters_and_weights(searchable_app):
    app = searchable_app
    create_test_project(app)
    app.selectbox(key="reference_player").set_value("espn:3:1").run()
    app.checkbox(key="custom_weights").check().run()
    app.slider(key="weight_passes_p90").set_value(4).run()
    app.multiselect(key="candidate_teams_exclude").set_value([2]).run()
    app.text_input(key="save_project_search_name").set_value("Pases y creación")
    app.button(key="save_project_search").click().run()
    assert not app.exception
    app.selectbox(key="reference_player").set_value("espn:1:2").run()
    app.button(key="reset_candidate_filters").click().run()
    app.slider(key="weight_passes_p90").set_value(1).run()
    app.button(key="restore_project_search").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:3:1"
    assert app.slider(key="weight_passes_p90").value == 4
    assert app.multiselect(key="candidate_teams_exclude").value == [2]


def test_saved_target_search_recovers_from_reference_mode(searchable_app):
    app = searchable_app
    create_test_project(app)
    switch_search_mode(app, "Por objetivo")
    app.selectbox(key="target_preset").set_value("Personalizado").run()
    next(w for w in app.multiselect if w.key.startswith("target_features_")).set_value(
        ["passes_p90"]
    ).run()
    next(w for w in app.slider if w.key.startswith("target_goal_")).set_value(85).run()
    app.checkbox(key="target_strict").check().run()
    app.text_input(key="save_project_search_name").set_value("Organización")
    app.button(key="save_project_search").click().run()
    assert not app.exception
    switch_search_mode(app, "Por parecido")
    app.button(key="restore_project_search").click().run()
    assert not app.exception
    assert app.selectbox(key="target_preset").value == "Personalizado"
    assert next(w for w in app.slider if w.key.startswith("target_goal_")).value == 85
    assert app.checkbox(key="target_strict").value


def test_new_biography_card_does_not_invent_missing_details(searchable_app):
    app = searchable_app
    assert any("Pie dominante" in w.value and "No disponible" in w.value for w in app.markdown)


def test_update_failure_keeps_reference_and_project_records(searchable_app, tmp_path, monkeypatch):
    from scoutfit.updates import UpdateError

    app = searchable_app
    create_test_project(app)
    before = (tmp_path / "data/user/projects.json").read_bytes()
    reference = app.selectbox(key="reference_player").value

    def fail(*args, **kwargs):
        raise UpdateError("Sin conexión de prueba")

    monkeypatch.setattr("scoutfit.update_view.update_dataset", fail)
    app.button(key="update_data").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == reference
    assert (tmp_path / "data/user/projects.json").read_bytes() == before
    assert any("Sin conexión" in message.value for message in app.error)
    assert any("consulta válida sigue activa" in message.value for message in app.caption)


def test_update_button_loads_validated_snapshot_and_shows_summary(
    searchable_app, tmp_path, monkeypatch
):
    from scoutfit.datasets import activate, active_directory
    from scoutfit.updates import compare_datasets

    app = searchable_app
    app.selectbox(key="reference_player").set_value("espn:3:1").run()

    def update(root, progress=None):
        folder = active_directory(root / "data/processed")
        frame = pd.read_csv(folder / "profiles.csv")
        old = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        new = {**old, "snapshot": "new-valid", "downloaded_at": "2026-10-29T20:00:00Z"}
        report = compare_datasets(frame, old, frame, new)
        output = root / "data/processed/espn/new-valid"
        output.mkdir(parents=True)
        frame.to_csv(output / "profiles.csv", index=False)
        (output / "metadata.json").write_text(json.dumps(new), encoding="utf-8")
        (output / "update_report.json").write_text(json.dumps(report), encoding="utf-8")
        if progress:
            progress("statistics", 10, 10)
            progress("validation", 1, 1)
        activate(root / "data/processed", output)
        return frame, new, report

    monkeypatch.setattr("scoutfit.update_view.update_dataset", update)
    app.button(key="update_data").click().run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == "espn:3:1"
    assert any("29/10/2026" in message.value for message in app.caption)
    assert any("sin cambios" in message.value for message in app.success)
    assert any(
        item.proto.label == "Descargar resumen de actualización JSON"
        for item in app.get("download_button")
    )


def test_initial_setup_has_update_button(tmp_path, monkeypatch):
    from scoutfit.updates import UpdateError

    def fail(*args, **kwargs):
        raise UpdateError("Fuente no disponible")

    monkeypatch.setattr("scoutfit.update_view.update_dataset", fail)
    app = app_at(tmp_path).run()
    app.button(key="update_data").click().run()
    assert not app.exception
    assert any("Prepara los datos" in message.value for message in app.info)
    assert any("Fuente no disponible" in message.value for message in app.error)


def test_guided_campaign_requires_human_evidence_and_continues_pending_pairs(
    searchable_app, tmp_path
):
    app = searchable_app
    app.button(key="start_campaign").click().run()
    assert not app.exception
    reference = next(w for w in app.selectbox if w.label == "Referencia pendiente").value
    candidate = next(w for w in app.selectbox if w.label == "Pareja pendiente").value
    submit = next(w for w in app.button if w.label == "Guardar y seguir con pendientes")
    submit.click().run()
    assert any("Completa valoración" in w.value for w in app.warning)
    assert not (tmp_path / "data/user/judgments.json").exists()
    next(w for w in app.selectbox if w.label == "Valoración humana").set_value("2")
    next(w for w in app.text_input if w.label == "Nombre o alias del revisor").set_value(
        "Test reviewer"
    )
    next(w for w in app.text_area if w.label == "Evidencias y justificación").set_value(
        "Synthetic test evidence"
    )
    next(w for w in app.button if w.label == "Guardar y seguir con pendientes").click().run()
    assert not app.exception
    rows = json.loads((tmp_path / "data/user/judgments.json").read_text())
    assert len(rows) == 1 and rows[0]["reference_id"] == reference
    assert rows[0]["candidate_id"] == candidate and rows[0]["reviewer"] == "Test reviewer"
    pending_ref = next(w for w in app.selectbox if w.label == "Referencia pendiente").value
    pending_candidate = next(w for w in app.selectbox if w.label == "Pareja pendiente").value
    assert (pending_ref, pending_candidate) != (reference, candidate)


def test_guided_campaign_report_remains_pending_without_reviews(searchable_app):
    app = searchable_app
    app.button(key="start_campaign").click().run()
    app.button(key="campaign_report").click().run()
    assert not app.exception
    report = app.session_state["campaign_evidence"]
    assert report["status"] == "pending_review" and report["summary"] == []
    assert any("Pendiente de revisión humana" in message.value for message in app.info)


def test_sample_context_recalculates_thresholds_and_invalidates_changed_search(searchable_app):
    app = searchable_app
    reference = app.selectbox(key="reference_player").value
    app.button(key="sample_run_similarity").click().run()
    assert not app.exception
    context = next(d.value for d in app.tabs[0].dataframe if "Jaccard del top" in d.value)
    assert context["Mínimo de minutos"].tolist() == [450, 600, 900]
    assert context["Jaccard del top"].eq(1).all()
    app.radio(key="priority").set_value("Defensa").run()
    assert app.selectbox(key="reference_player").value == reference
    assert not any("Jaccard del top" in d.value for d in app.tabs[0].dataframe)


def test_change_dossier_updates_date_constraints_and_player_independently(searchable_app, tmp_path):
    data = tmp_path / "data/processed"
    meta = json.loads((data / "metadata.json").read_text())
    frame = pd.read_csv(data / "profiles.csv")
    for name, day, added in [("old", 26, 0), ("middle", 27, 90), ("test", 28, 180)]:
        folder = data / "espn" / name
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(
            json.dumps({**meta, "snapshot": name, "downloaded_at": f"2026-10-{day}T12:00:00Z"})
        )
        frame.assign(minutes=frame.minutes + added).to_csv(folder / "profiles.csv", index=False)
    app = searchable_app.run()
    reference = app.selectbox(key="reference_player").value
    next(w for w in app.selectbox if w.label == "Jugador de evolución").set_value(1).run()
    assert not app.exception
    assert app.selectbox(key="reference_player").value == reference
    app.selectbox(key="history_delta_1_after").set_value("middle").run()
    assert not app.exception and app.selectbox(key="history_delta_1_before").value == "old"
    assert any("Antes" in d.value and "Después" in d.value for d in app.tabs[4].dataframe)
    assert any(w.label == "Variación de minutos" and w.value == "+90" for w in app.metric)


def test_project_change_tracking_does_not_modify_saved_candidate(searchable_app, tmp_path):
    app = searchable_app
    create_test_project(app)
    app.button(key="recommendation_project_candidate").click().run()
    path = tmp_path / "data/user/projects.json"
    projects = json.loads(path.read_text())
    project = projects[0]
    project["candidates"][0]["snapshot"] = "old"
    path.write_text(json.dumps(projects))
    original = path.read_bytes()
    data = tmp_path / "data/processed"
    meta = json.loads((data / "metadata.json").read_text())
    frame = pd.read_csv(data / "profiles.csv")
    folder = data / "espn/old"
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(
        json.dumps({**meta, "snapshot": "old", "downloaded_at": "2026-10-27T12:00:00Z"})
    )
    frame.assign(minutes=frame.minutes - 200).to_csv(folder / "profiles.csv", index=False)
    app.checkbox(key=f"project_tracking_{project['id']}").check().run()
    assert not app.exception
    changes = next(d.value for d in app.dataframe if "Cambios desde que se guardó" in d.value)
    assert changes.iloc[0]["Δ minutos"] == 200
    assert path.read_bytes() == original


def test_observation_history_persists_and_preserves_general_note(searchable_app, tmp_path):
    app = searchable_app
    create_test_project(app)
    app.button(key="recommendation_project_candidate").click().run()
    path = tmp_path / "data/user/projects.json"
    project = json.loads(path.read_text())[0]
    candidate = project["candidates"][0]
    token = f"{project['id']}_{candidate['key']}"
    app.text_area(key=f"project_note_{token}").set_value("Nota general de prueba")
    app.button(key="save_project_candidate").click().run()
    for context in ("Primera sesión de prueba", "Segunda sesión de prueba"):
        app.text_input(key=f"observation_context_{token}").set_value(context)
        app.text_area(key=f"observation_strengths_{token}").set_value(
            "Observación sintética para test"
        )
        app.text_input(key=f"observation_video_{token}").set_value("javascript:invalid")
        app.button(key=f"add_observation_{token}").click().run()
        assert not app.exception and app.error
        assert app.text_input(key=f"observation_context_{token}").value == context
        assert (
            app.text_area(key=f"observation_strengths_{token}").value
            == "Observación sintética para test"
        )
        app.text_input(key=f"observation_video_{token}").set_value("https://example.test/video")
        app.text_input(key=f"observation_position_{token}").set_value("12:34")
        app.button(key=f"add_observation_{token}").click().run()
        assert not app.exception
    record = json.loads(path.read_text(encoding="utf-8"))[0]["candidates"][0]
    assert record["note"] == "Nota general de prueba" and len(record["observations"]) == 2
    assert [o["context"] for o in record["observations"]] == [
        "Primera sesión de prueba",
        "Segunda sesión de prueba",
    ]
    another = app_at(tmp_path).run()
    assert not another.exception
    assert any(e.label == "Observaciones de campo · 2 entradas" for e in another.expander)


def test_individual_report_requires_saved_human_reason_and_restores_signature(
    searchable_app, tmp_path
):
    app = searchable_app
    create_test_project(app)
    app.button(key="recommendation_project_candidate").click().run()
    path = tmp_path / "data/user/projects.json"
    project = json.loads(path.read_text())[0]
    token = f"{project['id']}_{project['candidates'][0]['key']}"
    assert app.selectbox(key=f"assessment_verdict_{token}").value == "Sin conclusión"
    app.selectbox(key=f"assessment_verdict_{token}").set_value("Encaja parcialmente")
    app.button(key=f"save_assessment_{token}").click().run()
    assert not app.exception and app.error
    assert "assessment" not in json.loads(path.read_text())[0]["candidates"][0]
    app.text_area(key=f"assessment_rationale_{token}").set_value(
        "Justificación sintética para test"
    )
    app.text_input(key=f"assessment_author_{token}").set_value("Firma de prueba")
    app.button(key=f"save_assessment_{token}").click().run()
    assert not app.exception
    another = app_at(tmp_path).run()
    assert not another.exception
    assert another.selectbox(key=f"assessment_verdict_{token}").value == "Encaja parcialmente"
    assert another.text_input(key=f"assessment_author_{token}").value == "Firma de prueba"
    assert any(
        d.proto.label == "Descargar ficha individual HTML" for d in another.get("download_button")
    )
