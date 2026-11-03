"""Run from the project root: uv run streamlit run app.py."""

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from scoutfit.benchmark_view import render_benchmark
from scoutfit.biographies import enrich_biographies
from scoutfit.comparison import compare_players
from scoutfit.datasets import active_directory, metric_definitions
from scoutfit.explorer import render_map
from scoutfit.panels import render_comparison, render_evaluation, render_favorites, render_history
from scoutfit.project_view import render_projects, save_search_action
from scoutfit.recommendation_view import render_recommendations
from scoutfit.recommender import recommend
from scoutfit.roles import infer_roles
from scoutfit.search import keep_valid_selection, search_players
from scoutfit.search_controls import render_candidate_filters
from scoutfit.target_view import render_target_search
from scoutfit.update_view import render_update_panel
from scoutfit.visuals import footer, hero, inject_style, reference_card, section

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="ScoutFit · LaLiga masculina", page_icon="⚽", layout="wide")
inject_style()


def use_reference(profile_id):
    """Callbacks run before widgets are instantiated, so dependent filters stay valid."""
    st.session_state.update(
        player_search="",
        reference_team="Todos",
        reference_position="Todas",
        reference_player=profile_id,
        workspace_tab="Recomendaciones",
        search_mode="Por parecido",
    )


def reset_weights(preset):
    for feature, weight in preset.items():
        st.session_state[f"weight_{feature}"] = weight


@st.cache_data
def load_profiles(csv_bytes, metadata_text):
    from io import BytesIO

    return pd.read_csv(BytesIO(csv_bytes)), json.loads(metadata_text)


@st.cache_data
def enrich_roles(frame):
    return infer_roles(frame)


directory = active_directory(ROOT / "data/processed")
data_path, metadata_path = directory / "profiles.csv", directory / "metadata.json"
if not data_path.exists() or not metadata_path.exists():
    st.info("Prepara los datos de LaLiga masculina desde la terminal del proyecto:")
    st.code("uv run scoutfit update", language="shell")
    render_update_panel(ROOT)
    st.stop()
profiles, metadata = load_profiles(
    data_path.read_bytes(), metadata_path.read_text(encoding="utf-8")
)
current = metadata.get("provider") == "espn"
features = metric_definitions(metadata)
if current:
    profiles = enrich_roles(profiles)
profiles = profiles[profiles["role"] != "Portería"].copy()
profiles, biography_issues = enrich_biographies(profiles, ROOT, metadata)
consulted = datetime.fromisoformat(metadata["downloaded_at"].replace("Z", "+00:00"))
local_time = consulted.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y · %H:%M")
hero(metadata, profiles)
st.caption(
    f"Fuente: {metadata.get('source', 'StatsBomb Open Data')} · Consultado: {local_time} (Madrid)"
)
with st.expander("Archivo de trabajo · proyectos, datos y revisión", expanded=False):
    st.caption("Lo que guardas y revisas en esta instalación.")
    render_update_panel(ROOT, profiles, metadata)
    render_benchmark(ROOT, profiles, metadata, features)
    render_projects(ROOT, profiles, metadata)
if current:
    if (datetime.now(UTC) - consulted).days > 7:
        st.warning(
            "La consulta tiene más de siete días. Abre Actualizar datos y ver cambios "
            "y pulsa Actualizar desde ESPN para consultar de nuevo."
        )
else:
    st.info(
        "Conjunto histórico de StatsBomb. Ejecuta uv run scoutfit update para activar "
        "LaLiga masculina con plantillas recientes."
    )
    if metadata.get("partial"):
        st.warning(
            f"Muestra parcial: {len(metadata['match_ids'])} de "
            f"{metadata['matches_available']} partidos."
        )
    if metadata.get("excluded_matches"):
        st.warning(
            f"Control de calidad: {len(metadata['excluded_matches'])} partidos excluidos "
            "por intervalos de alineación inconsistentes."
        )

if biography_issues:
    st.caption(
        "Algunas biografías no están disponibles o no superaron la verificación de la consulta."
    )
search_mode = st.segmented_control(
    "Cómo quieres buscar",
    ["Por parecido", "Por objetivo"],
    default="Por parecido",
    required=True,
    key="search_mode",
    persist_state="session",
)
if search_mode == "Por objetivo":
    render_target_search(ROOT, profiles, metadata, features, use_reference)
    footer(metadata)
    st.stop()

with st.container(border=True, key="search_panel"):
    section("01 / La búsqueda", "¿A quién estamos mirando?")
    search_column, team_column, position_column, minutes_column = st.columns([2.2, 1.3, 1.3, 1])
    with search_column:
        query = st.text_input(
            "Buscar jugador por nombre",
            placeholder="Ej.: Pedri, Mbappe o Lamine",
            key="player_search",
            persist_state="session",
        )
    with minutes_column:
        minimum = st.number_input(
            "Minutos mínimos",
            min_value=0,
            max_value=5000,
            value=90 if metadata.get("partial") else 450,
            step=90,
            key="min_minutes",
            persist_state="session",
        )
    eligible = profiles[profiles["minutes"] >= minimum]
    if eligible.empty:
        st.warning("No hay perfiles con ese mínimo. Reduce los minutos.")
        st.stop()
    teams = ["Todos", *sorted(eligible["team_name"].unique())]
    keep_valid_selection(st.session_state, "reference_team", teams)
    with team_column:
        team_choice = st.selectbox(
            "Equipo de referencia", teams, index=0, key="reference_team", persist_state="session"
        )
    references = (
        eligible if team_choice == "Todos" else eligible[eligible["team_name"] == team_choice]
    )
    positions = ["Todas", *sorted(references["role"].unique())]
    keep_valid_selection(st.session_state, "reference_position", positions)
    with position_column:
        selected_position = st.selectbox(
            "Posición de la fuente" if current else "Rol predominante",
            positions,
            index=0,
            key="reference_position",
            persist_state="session",
        )
    if selected_position != "Todas":
        references = references[references["role"] == selected_position]
    choices = search_players(references, query).sort_values(["player_name", "team_name"])
    if choices.empty:
        st.info("No hay jugadores que coincidan. Prueba otro nombre o amplía los filtros.")
        st.stop()
    labels = dict(zip(choices["profile_id"], choices["player_name"] + " · " + choices["team_name"]))
    ids = list(labels)
    keep_valid_selection(st.session_state, "reference_player", ids)
    reference_id = st.selectbox(
        "Jugador de referencia" if current else "Jugador/a de referencia",
        ids,
        format_func=labels.get,
        index=0,
        key="reference_player",
        persist_state="session",
    )
    st.caption(
        f"{len(choices)} {'jugador disponible' if len(choices) == 1 else 'jugadores disponibles'} "
        "con estos filtros. "
        "Los candidatos se buscan por separado con los filtros de abajo."
    )

reference = choices.loc[choices["profile_id"] == reference_id].iloc[0]
selected_role = reference["role"]
has_inferred_role = current and bool(reference["inferred_role"])
reference_card(reference, compare_players(profiles, [reference_id], features, minimum))
if current:
    if has_inferred_role:
        if reference["inferred_role_status"] == "Mixto":
            st.caption(
                f"Perfil mixto: también se aproxima a {reference['inferred_role_alternative']}. "
                "La etiqueta describe su estilo estadístico, no una posición confirmada."
            )
    else:
        st.info(
            f"Perfil inferido no asignado: {reference['inferred_role_status']}. "
            "Se comparará por la posición publicada en la fuente."
        )

candidate_filters = render_candidate_filters(profiles, minimum)
with st.expander("Ajustar recomendaciones", expanded=False):
    option_column, priority_column = st.columns(2)
    with option_column:
        exclude_team = st.checkbox(
            "Buscar en otros equipos", value=True, key="exclude_team", persist_state="session"
        )
        if has_inferred_role:
            match_role = st.checkbox(
                "Comparar solo el mismo perfil inferido",
                value=True,
                key="same_profile",
                persist_state="session",
            )
        else:
            match_role = False
        top_k = st.slider("Número de candidatos", 1, 10, 5, key="top_k", persist_state="session")
    with priority_column:
        mode = st.radio(
            "Prioridad",
            ["Equilibrada", "Creación" if current else "Progresión", "Defensa"],
            key="priority",
            horizontal=True,
            persist_state="session",
        )
        if st.button("Recargar datos locales", help="Relee la última descarga validada"):
            st.rerun()

weights = {feature: 1.0 for feature in features}
if mode in ("Creación", "Progresión"):
    emphasized = (
        ("key_passes_p90", "provider_progressive_carries_p90", "box_touches_p90")
        if current
        else ("progressive_passes_p90", "progressive_carries_p90", "final_third_entries_p90")
    )
elif mode == "Defensa":
    emphasized = (
        ("recoveries_p90", "tackles_won_p90", "interceptions_p90")
        if current
        else ("pressures_p90", "defensive_actions_p90")
    )
else:
    emphasized = ()
for feature in emphasized:
    weights[feature] = 3.0
with st.expander("Diseña tu búsqueda · pesos personalizados", expanded=False):
    custom_weights = st.checkbox(
        "Personalizar pesos de las métricas", key="custom_weights", persist_state="session"
    )
    st.caption(
        "La prioridad elegida aplica pesos 1× o 3×. Al personalizarlos, 0× ignora una métrica "
        "y 5× le da más importancia. Los percentiles de las fichas no cambian."
    )
    if custom_weights:
        st.button(
            "Restablecer a la prioridad elegida",
            on_click=reset_weights,
            args=(weights.copy(),),
            key="reset_weights",
        )
        weight_columns = st.columns(3)
        for index, (feature, label) in enumerate(features.items()):
            with weight_columns[index % 3]:
                weights[feature] = st.slider(
                    label,
                    0.0,
                    5.0,
                    float(weights[feature]),
                    0.5,
                    key=f"weight_{feature}",
                    persist_state="session",
                )
    search_config = {
        "mode": "similarity",
        "snapshot": metadata.get("snapshot", metadata.get("revision")),
        "reference_id": reference_id,
        "reference_player_id": int(reference["player_id"]),
        "minimum_minutes": minimum,
        "exclude_team": exclude_team,
        "match_inferred_role": match_role,
        "top_k": top_k,
        "weights": weights,
        "priority": mode,
        "candidate_filters": candidate_filters.to_dict(),
    }
    st.download_button(
        "Exportar configuración de búsqueda",
        json.dumps(
            search_config,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        file_name="scoutfit-busqueda.json",
        mime="application/json",
    )
if sum(weights.values()) <= 0:
    st.warning("Activa al menos una métrica con peso mayor que cero para calcular candidatos.")
    st.stop()
save_search_action(ROOT, profiles, metadata, search_config)
reference = choices.loc[choices["profile_id"] == reference_id].iloc[0]
ranking, explanations = recommend(
    profiles,
    reference_id,
    minimum,
    top_k,
    exclude_team,
    weights,
    feature_definitions=features,
    match_inferred_role=match_role,
    candidate_filters=candidate_filters,
)
recommendations_tab, comparison_tab, favorites_tab, evaluation_tab, history_tab, map_tab = st.tabs(
    ["Recomendaciones", "Comparativa", "Favoritos", "Evaluación", "Evolución", "Mapa de perfiles"],
    key="workspace_tab",
    on_change="rerun",
)
with recommendations_tab:
    render_recommendations(
        ROOT,
        profiles,
        metadata,
        features,
        reference,
        eligible,
        ranking,
        explanations,
        match_role,
        minimum,
        weights=weights,
        exclude_team=exclude_team,
        top_k=top_k,
        candidate_filters=candidate_filters,
    )
with comparison_tab:
    render_comparison(
        ROOT,
        profiles,
        metadata,
        features,
        reference,
        ranking,
        minimum,
        candidate_filters=candidate_filters,
    )
with favorites_tab:
    render_favorites(ROOT, profiles, metadata)
with evaluation_tab:
    render_evaluation(
        ROOT,
        profiles,
        metadata,
        features,
        reference,
        ranking,
        minimum,
        weights,
        match_role,
        exclude_team,
        top_k,
        candidate_filters=candidate_filters,
    )
with history_tab:
    render_history(ROOT, profiles, metadata, features, reference)
with map_tab:
    render_map(profiles, reference, features, minimum, weights, ranking, use_reference)
footer(metadata)
