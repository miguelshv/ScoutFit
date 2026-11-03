"""Project manager rendered before search widgets so restoration is atomic in the UI."""

import json

import pandas as pd
import streamlit as st

from scoutfit.observation_view import render_observations
from scoutfit.projects import (
    STATUSES,
    add_candidate,
    create_project,
    prepare_search_state,
    project_by_id,
    save_search,
    update_candidate,
)
from scoutfit.search import keep_valid_selection
from scoutfit.tracking_view import render_project_tracking
from scoutfit.workspace import load_records, player_key


def render_projects(root, profiles, metadata):
    path = root / "data/user/projects.json"
    with st.expander("Proyectos de scouting y búsquedas guardadas", expanded=False):
        st.caption("Espacio local de esta instalación. Tus proyectos se conservan entre sesiones.")
        if notice := st.session_state.pop("project_notice", None):
            st.success(notice)
        with st.form("create_project_form", clear_on_submit=True):
            name = st.text_input("Nombre del nuevo proyecto", max_chars=100, key="new_project_name")
            description = st.text_area(
                "Descripción del proyecto", max_chars=4000, key="new_project_description"
            )
            if st.form_submit_button("Crear proyecto", key="create_project"):
                try:
                    project_id = create_project(path, name, description)
                    st.session_state["active_project"] = project_id
                    st.session_state["project_notice"] = (
                        "Proyecto creado. Ya puedes guardar búsquedas y candidatos."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        projects = load_records(path)
        if not projects:
            st.caption(
                "Crea tu primer proyecto, por ejemplo: Mediocentro para la próxima temporada."
            )
            return
        labels = {p["id"]: p["name"] for p in projects}
        keep_valid_selection(st.session_state, "active_project", list(labels))
        active = st.selectbox(
            "Proyecto activo",
            list(labels),
            format_func=labels.get,
            key="active_project",
            persist_state="session",
        )
        project = next(p for p in projects if p["id"] == active)
        if project["description"]:
            st.write(project["description"])
        st.caption(
            f"{len(project['searches'])} búsquedas · {len(project['candidates'])} candidatos"
        )
        if project["searches"]:
            options = {s["id"]: s["name"] for s in project["searches"]}
            key = f"project_search_{active}"
            keep_valid_selection(st.session_state, key, list(options))
            selected = st.selectbox(
                "Búsqueda guardada", list(options), format_func=options.get, key=key
            )
            saved = next(s for s in project["searches"] if s["id"] == selected)
            st.caption(
                f"Consulta de origen: {saved['snapshot']} · Guardada: {saved['saved_at'][:10]}"
            )
            if st.button("Recuperar búsqueda", key="restore_project_search"):
                try:
                    patch = prepare_search_state(
                        saved["config"], profiles, metadata, saved["scope"]
                    )
                    st.session_state.update(patch)
                    if saved["snapshot"] != metadata.get(
                        "snapshot", metadata.get("revision", "historical")
                    ):
                        st.warning(
                            "Búsqueda recuperada sobre la consulta actual. "
                            "Los resultados pueden haber cambiado."
                        )
                    else:
                        st.success("Búsqueda recuperada con todos sus filtros y objetivos.")
                except (ValueError, KeyError, TypeError) as exc:
                    st.error(f"No se puede recuperar esta búsqueda: {exc}")
        render_project_candidates(path, project, profiles, metadata)
        st.download_button(
            "Exportar proyecto JSON",
            json.dumps(project, ensure_ascii=False, indent=2),
            file_name="scoutfit-proyecto.json",
            mime="application/json",
            key="project_export",
        )


def render_project_candidates(path, project, profiles, metadata):
    if not project["candidates"]:
        st.caption("Añade jugadores desde la ficha del candidato en cualquiera de los dos modos.")
        return
    current = {player_key(p, metadata): p for _, p in profiles.iterrows()}
    table = []
    for item in project["candidates"]:
        player = current.get(item["key"])
        table.append(
            {
                "Jugador": item["player_name"],
                "Estado": item["status"],
                "Equipo al guardar": item["team_at_save"],
                "Equipo en consulta activa": player["team_name"]
                if player is not None
                else "No disponible",
                "Temporada": item["season_id"],
                "Nota": item["note"],
            }
        )
    frame = pd.DataFrame(table)
    st.dataframe(frame, hide_index=True, width="stretch")
    st.download_button(
        "Exportar candidatos del proyecto CSV",
        frame.to_csv(index=False),
        file_name="scoutfit-proyecto-candidatos.csv",
        mime="text/csv",
    )
    labels = {
        c["key"]: f"{c['player_name']} · {c['team_at_save']} · {c['season_id']}"
        for c in project["candidates"]
    }
    key = f"project_candidate_{project['id']}"
    keep_valid_selection(st.session_state, key, list(labels))
    selected = st.selectbox(
        "Revisar candidato del proyecto", list(labels), format_func=labels.get, key=key
    )
    candidate = next(c for c in project["candidates"] if c["key"] == selected)
    render_project_tracking(path.parents[2], project, profiles, metadata, candidate)
    token = f"{project['id']}_{selected}"
    status = st.selectbox(
        "Estado de seguimiento",
        STATUSES,
        index=STATUSES.index(candidate["status"]),
        key=f"project_status_{token}",
    )
    note = st.text_area(
        "Nota del candidato en el proyecto",
        value=candidate["note"],
        max_chars=4000,
        key=f"project_note_{token}",
    )
    if st.button("Guardar seguimiento", key="save_project_candidate"):
        update_candidate(path, project["id"], selected, status, note)
        st.session_state["project_notice"] = "Seguimiento actualizado."
        st.rerun()
    render_observations(path, project, candidate, profiles, metadata)


def save_search_action(root, profiles, metadata, config):
    path = root / "data/user/projects.json"
    project = project_by_id(path, st.session_state.get("active_project"))
    if project is None:
        return
    with st.expander(f"Guardar esta búsqueda en {project['name']}", expanded=False):
        name = st.text_input(
            "Nombre de esta búsqueda",
            max_chars=100,
            key="save_project_search_name",
            persist_state="session",
        )
        st.caption("Si el nombre ya existe en este proyecto, se actualiza su configuración.")
        if st.button("Guardar búsqueda en el proyecto", key="save_project_search"):
            try:
                save_search(path, project["id"], name, config, profiles, metadata)
                st.session_state["project_notice"] = (
                    "Búsqueda guardada con sus filtros y objetivos."
                )
                st.rerun()
            except (ValueError, KeyError, TypeError) as exc:
                st.error(str(exc))


def candidate_project_action(root, player, metadata, key):
    path = root / "data/user/projects.json"
    project = project_by_id(path, st.session_state.get("active_project"))
    if project is None:
        st.caption("Crea un proyecto arriba para organizar este candidato por estado.")
        return
    saved = any(c["key"] == player_key(player, metadata) for c in project["candidates"])
    if st.button(
        "Incluido en el proyecto" if saved else f"Añadir a {project['name']}",
        key=key,
        disabled=saved,
    ):
        add_candidate(path, project["id"], player, metadata)
        st.session_state["project_notice"] = f"{player['player_name']} añadido al proyecto."
        st.rerun()
