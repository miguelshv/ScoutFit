"""Recommendation view kept separate from comparison, evaluation and history."""

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from scoutfit.comparison import compare_players
from scoutfit.explorer import percentile_radar
from scoutfit.panels import favorite_action
from scoutfit.project_view import candidate_project_action
from scoutfit.roles import MIN_ROLE_MINUTES, ROLE_MODEL_VERSION
from scoutfit.sample_view import render_participation, render_sample_context
from scoutfit.search import keep_valid_selection
from scoutfit.visuals import COLORS, candidate_card, polish_chart, section


def open_comparison(candidate_id):
    st.session_state["comparison_extra"] = [candidate_id]
    st.session_state["workspace_tab"] = "Comparativa"


def render_recommendations(
    root,
    profiles,
    metadata,
    features,
    reference,
    eligible,
    ranking,
    explanations,
    match_role,
    minimum,
    weights=None,
    exclude_team=True,
    top_k=5,
    candidate_filters=None,
):
    current = metadata.get("provider") == "espn"
    selected_role = reference["role"]
    has_inferred_role = current and bool(reference["inferred_role"])
    favorite_action(
        root, reference, metadata, "favorite_reference", "Guardar referencia en favoritos"
    )
    with st.container(key="recommendation_summary"):
        col1, col2, col3, col4 = st.columns(4)
    col1.metric("Minutos de referencia", f"{reference['minutes']:,.0f}")
    col2.metric("Partidos de referencia", int(reference["matches"]))
    if current:
        col3.metric(
            "Perfiles comparables",
            len(
                eligible[
                    (eligible["role"] == selected_role)
                    & (
                        (eligible["inferred_role"] == reference["inferred_role"])
                        if match_role
                        else True
                    )
                ]
            ),
        )
        col4.metric("Equipos consultados", metadata["team_count"])
    else:
        col3.metric("Tiempo en el rol principal", f"{reference['role_share']:.0%}")
        col4.metric("Partidos utilizados", len(metadata["used_match_ids"]))
        if reference["role_share"] < 0.7:
            st.info("La referencia ha jugado en varios roles: sus métricas mezclan esas funciones.")

    render_sample_context(
        profiles,
        metadata,
        features,
        reference,
        minimum,
        {
            "top_k": top_k,
            "weights": weights,
            "exclude_team": exclude_team,
            "match_role": match_role,
            "candidate_filters": candidate_filters,
        },
    )
    section("02 / Lista de observación", "Otros nombres para mirar")
    st.caption(
        "Menor distancia = mayor parecido dentro del mismo grupo y temporada. "
        "No es una probabilidad de éxito de un fichaje."
    )
    if ranking.empty:
        st.info(
            "No hay candidatos con estos filtros. Reduce el mínimo de minutos, "
            "revisa los clubes y el intervalo de minutos, incluye el mismo equipo "
            "o desactiva la comparación por perfil inferido."
        )
        return
    with st.container(key="shortlist"):
        for column, (index, player) in zip(
            st.columns(min(3, len(ranking))), ranking.head(3).iterrows()
        ):
            with column:
                candidate_card(player, index + 1)
                st.button(
                    "Comparar con referencia",
                    key=f"compare_card_{player['profile_id']}",
                    on_click=open_comparison,
                    args=(player["profile_id"],),
                    width="stretch",
                    icon=":material/compare_arrows:",
                )
    columns = ["player_name", "team_name", "minutes", "distance"]
    if current:
        columns.insert(2, "inferred_role")
        columns.insert(3, "inferred_role_status")
    else:
        columns.insert(3, "role_share")
    display = ranking[columns].rename(
        columns={
            "player_name": "Jugador" if current else "Jugador/a",
            "team_name": "Equipo de plantilla" if current else "Equipo",
            "minutes": "Minutos",
            "role_share": "Fracción en rol principal",
            "inferred_role": "Perfil inferido",
            "inferred_role_status": "Tipo de perfil",
            "distance": "Distancia",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={"Distancia": st.column_config.NumberColumn(format="%.3f")},
    )
    st.download_button(
        "Descargar candidatos CSV",
        ranking.to_csv(index=False).encode("utf-8"),
        file_name="scoutfit-candidatos.csv",
        mime="text/csv",
    )
    candidate_labels = dict(
        zip(ranking["profile_id"], ranking["player_name"] + " · " + ranking["team_name"])
    )
    keep_valid_selection(st.session_state, "candidate_player", list(candidate_labels))
    candidate_id = st.selectbox(
        "Inspeccionar candidato",
        list(candidate_labels),
        format_func=candidate_labels.get,
        index=0,
        key="candidate_player",
    )
    detail = explanations.loc[explanations["profile_id"] == candidate_id].copy()
    candidate = ranking.loc[ranking["profile_id"] == candidate_id].iloc[0]
    render_participation(candidate, "Candidato")
    save_column, compare_column = st.columns(2)
    with save_column:
        favorite_action(
            root, candidate, metadata, "favorite_candidate", "Guardar candidato en favoritos"
        )
    with compare_column:
        st.button(
            "Abrir comparativa detallada",
            key="compare_inspected",
            on_click=open_comparison,
            args=(candidate_id,),
        )
    candidate_project_action(root, candidate, metadata, "recommendation_project_candidate")
    section("03 / Notas de comparación", "Dónde coinciden. Dónde se separan.")
    view = st.segmented_control(
        "Visualización",
        ["Radar de percentiles", "Diferencias por métrica"],
        default="Radar de percentiles",
        key="recommendation_chart",
    )
    chart = detail.melt(
        id_vars=["metric"],
        value_vars=["reference_z", "candidate_z"],
        var_name="Perfil",
        value_name="Desviaciones respecto al grupo",
    )
    chart["Perfil"] = chart["Perfil"].map(
        {
            "reference_z": f"Referencia · {reference['player_name']}",
            "candidate_z": f"Candidato · {candidate['player_name']}",
        }
    )
    figure = px.bar(
        chart,
        x="Desviaciones respecto al grupo",
        y="metric",
        color="Perfil",
        barmode="group",
        orientation="h",
        color_discrete_sequence=COLORS,
    )
    figure.update_layout(
        yaxis_title=None, legend_title=None, height=610, margin=dict(l=0, r=0, t=10, b=0)
    )
    if view == "Diferencias por métrica":
        st.plotly_chart(polish_chart(figure, 610), width="stretch")
        st.caption(
            "0 = media del grupo comparable. Estar por encima describe volumen o estilo, "
            "sin implicar que el jugador sea mejor. "
            "Los pesos afectan a la distancia, no a las barras."
        )
    else:
        comparison = compare_players(
            profiles, [reference["profile_id"], candidate_id], features, minimum
        )
        st.plotly_chart(percentile_radar(comparison), width="stretch")
        st.caption(
            "Percentiles 0–100 sobre toda la posición elegible. Un radio más alto refleja "
            "más volumen o una tasa mayor, no calidad global. Los pesos no alteran el radar."
        )
    left, right = st.columns(2)
    with left:
        st.subheader("Dónde se parecen")
        for _, row in detail.sort_values("squared_contribution").head(3).iterrows():
            st.write(f"**{row['metric']}**: {row['reference']:.2f} frente a {row['candidate']:.2f}")
    with right:
        st.subheader("Qué los diferencia")
        for _, row in (
            detail.sort_values("squared_contribution", ascending=False).head(3).iterrows()
        ):
            st.write(f"**{row['metric']}**: {row['reference']:.2f} frente a {row['candidate']:.2f}")
    with st.expander("Ver todas las métricas y la explicación matemática"):
        st.dataframe(
            detail[["metric", "reference", "candidate", "weight", "squared_contribution"]].rename(
                columns={
                    "metric": "Métrica",
                    "reference": "Referencia",
                    "candidate": "Candidato",
                    "weight": "Peso",
                    "squared_contribution": "Contribución a distancia²",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.latex(r"d(a,b)=\sqrt{\frac{\sum_j w_j(z_{aj}-z_{bj})^2}{\sum_j w_j}}")
        st.write(
            "Cada métrica se estandariza sobre los perfiles elegibles del mismo grupo, liga y "
            "temporada, incluida la referencia. El filtro de equipo solo limita la elección "
            "de referencia. Los filtros de candidatos se aplican tras calcular las distancias, "
            "antes de seleccionar el top-k, sin volver a estandarizar."
        )
    if current:
        with st.expander("Cómo se infieren los perfiles futbolísticos"):
            st.write(
                "Los perfiles se asignan mediante arquetipos estadísticos con reglas explícitas. "
                "Se calculan percentiles dentro de la misma posición, liga y temporada usando "
                "al menos ocho jugadores con 450 minutos. La inferencia no depende de tus "
                "pesos ni de los filtros de búsqueda."
            )
            st.write(
                "Organizador/distribuidor: pases, precisión y pases largos. Recuperador: "
                "recuperaciones, entradas, intercepciones y duelos. Creador/proyección: "
                "pases de tiro, conducciones y llegada al área. Son estilos inferidos: "
                "no distinguen de forma confirmada un central de un lateral ni un extremo "
                "de un delantero centro."
            )
            st.write(
                "Cuando las dos afinidades principales difieren menos de 0,05 se indica "
                "perfil mixto. Sin muestra o señal suficiente no se asigna una etiqueta. "
                "Las afinidades no son probabilidades ni una validación deportiva."
            )
            if has_inferred_role:
                scores = json.loads(reference["inferred_role_scores"])
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Arquetipo": list(scores),
                            "Afinidad relativa (0–1)": list(scores.values()),
                        }
                    ),
                    hide_index=True,
                    width="stretch",
                )
            st.caption(
                f"Modelo de reglas: {ROLE_MODEL_VERSION} · Mínimo: {MIN_ROLE_MINUTES} minutos"
            )

    with st.expander("Metodología, procedencia y límites"):
        if current:
            st.write(
                "Se usan agregados de ESPN de LaLiga y de la temporada indicada, con minutos "
                "del proveedor. Cada conteo se convierte a /90; la precisión de pase se calcula "
                "como completados/intentados × 100. Las conducciones progresivas siguen la "
                "definición de ESPN. No se calculan xT, presiones ni entradas al área."
            )
            st.write(
                "La posición procede de la plantilla, sin minutos por subrol: defensas centrales "
                "y laterales pueden compartir grupo. El equipo indica la plantilla consultada, "
                "mientras las métricas pueden incluir otro club de la misma temporada. "
                "La fecha de consulta no garantiza que todos los fichajes estén ya reflejados."
            )
            st.write(
                f"Perfiles con datos completos: {metadata['profiles']}. "
                f"Registros de campo excluidos: {len(metadata['excluded_profiles'])}. "
                "No se imputan estadísticas ausentes ni se asigna un equipo si es ambiguo."
            )
            st.json(
                {
                    "equipos": metadata.get("roster_teams", []),
                    "exclusiones": metadata["excluded_profiles"],
                },
                expanded=False,
            )
            st.caption(
                f"Descarga: {metadata['snapshot']} · URLs y SHA-256 en el manifiesto local. "
                "Los endpoints públicos de ESPN pueden cambiar."
            )
        else:
            st.write(
                "Eventos de juego abierto; progresión = reducir ≥10 m la distancia a portería. "
                "Minutos desde intervalos, incluido descuento. Se excluyen tandas y partidos "
                "con intervalos inconsistentes."
            )
            st.json(metadata.get("excluded_matches", []), expanded=False)
            st.caption(f"Revisión: {metadata['revision']}")
        st.write(
            "Sin ajustes por posesión, rival o contexto táctico. Los pesos son decisiones "
            "explícitas del baseline. No se han validado resultados de futuros fichajes."
        )
