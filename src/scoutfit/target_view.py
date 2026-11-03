"""Define a statistical brief without creating a fictional player or fake labels."""

import json

import plotly.graph_objects as go
import streamlit as st

from scoutfit.comparison import compare_players, html_report
from scoutfit.explorer import percentile_radar
from scoutfit.panels import favorite_action, render_favorites
from scoutfit.project_view import candidate_project_action, save_search_action
from scoutfit.sample_view import render_participation, render_sample_context
from scoutfit.search import keep_valid_selection
from scoutfit.search_controls import render_candidate_filters
from scoutfit.target_search import available_presets, recommend_target
from scoutfit.visuals import polish_chart, reference_card, section


def render_target_search(root, profiles, metadata, features, use_reference):
    with st.container(border=True, key="target_search_panel"):
        section(
            "01 / Define la necesidad",
            "Busca un perfil objetivo",
            "Elige una posición y los mínimos estadísticos que deseas. "
            "No necesitas un jugador de referencia.",
        )
        left, right = st.columns(2)
        positions = sorted(profiles["role"].unique())
        with left:
            position = st.selectbox(
                "Posición del objetivo",
                positions,
                index=positions.index("Mediocentro") if "Mediocentro" in positions else 0,
                key="target_position",
                persist_state="session",
            )
            minimum = st.number_input(
                "Mínimo de muestra para percentiles",
                0,
                5000,
                450,
                50,
                key="target_min_minutes",
                persist_state="session",
            )
        presets = available_presets(position, features)
        keep_valid_selection(st.session_state, "target_preset", list(presets))
        with right:
            preset = st.selectbox(
                "Necesidad del equipo", list(presets), key="target_preset", persist_state="session"
            )
            top_k = st.slider(
                "Resultados del objetivo", 1, 20, 5, key="target_top_k", persist_state="session"
            )
        token = f"{position}_{preset}"
        with st.expander("Ajustar métricas, percentiles e importancia", expanded=False):
            selected = st.multiselect(
                "Métricas del objetivo",
                list(features),
                default=list(presets[preset]),
                format_func=features.get,
                key=f"target_features_{token}",
                persist_state="session",
            )
            goals, weights = {}, {}
            for feature in selected:
                goal_column, weight_column = st.columns([3, 1])
                with goal_column:
                    goals[feature] = st.slider(
                        f"Percentil mínimo · {features[feature]}",
                        0,
                        100,
                        int(presets[preset].get(feature, 75)),
                        5,
                        key=f"target_goal_{token}_{feature}",
                        persist_state="session",
                    )
                with weight_column:
                    weights[feature] = st.number_input(
                        f"Importancia · {features[feature]}",
                        1,
                        5,
                        1,
                        1,
                        key=f"target_weight_{token}_{feature}",
                        persist_state="session",
                    )
        if goals:
            st.caption(" · ".join(f"{features[f]} ≥ P{p:g}" for f, p in goals.items()))
        strict = st.checkbox(
            "Exigir que se cumplan todos los objetivos",
            key="target_strict",
            persist_state="session",
            help="Si nadie cumple todo, la lista queda vacía. No se relajan los requisitos.",
        )
        st.caption(
            "Sin esta opción se ordena por la brecha respecto a los mínimos deseados. "
            "Superar un objetivo no compensa incumplir otro ni penaliza al jugador."
        )
    filters = render_candidate_filters(profiles, minimum)
    config = {
        "mode": "target",
        "snapshot": metadata.get("snapshot", metadata.get("revision")),
        "position": position,
        "preset": preset,
        "minimum_minutes": minimum,
        "top_k": top_k,
        "goals": goals,
        "weights": weights,
        "strict": strict,
        "candidate_filters": filters.to_dict(),
        "metric": "weighted_rms_percentile_shortfall_v1",
    }
    st.download_button(
        "Exportar configuración del objetivo",
        json.dumps(config, ensure_ascii=False, indent=2),
        file_name="scoutfit-objetivo.json",
        mime="application/json",
        key="target_config",
    )
    if not goals:
        st.info("Selecciona al menos una métrica del objetivo para buscar candidatos.")
        return
    save_search_action(root, profiles, metadata, config)
    ranking, details = recommend_target(
        profiles, position, features, goals, minimum, top_k, weights, filters, strict
    )
    results_tab, comparison_tab, favorites_tab = st.tabs(
        ["Resultados del objetivo", "Comparar candidatos", "Favoritos"],
        key="target_workspace_tab",
        on_change="rerun",
    )
    with results_tab:
        render_sample_context(
            profiles,
            metadata,
            features,
            profiles.loc[profiles.role.eq(position)].iloc[0],
            minimum,
            {
                "top_k": top_k,
                "goals": goals,
                "weights": weights,
                "strict": strict,
                "candidate_filters": filters,
            },
            mode="target",
        )
        render_target_results(
            root, profiles, metadata, features, ranking, details, minimum, goals, use_reference
        )
    with comparison_tab:
        render_target_comparison(profiles, metadata, features, ranking, minimum, config)
    with favorites_tab:
        render_favorites(root, profiles, metadata)


def render_target_results(
    root, profiles, metadata, features, ranking, details, minimum, goals, use_reference
):
    section("02 / Alternativas a tu necesidad", "Candidatos para el objetivo")
    st.caption(
        "Menor brecha = menos puntos de percentil pendientes para alcanzar los mínimos. "
        "Brecha 0 significa que cumple los objetivos estadísticos; "
        "no es éxito garantizado de fichaje. "
        "En empate se priorizan más minutos y después nombre e identificador."
    )
    if ranking.empty:
        st.info(
            "No hay candidatos que cumplan estos filtros y requisitos. Amplía los clubes, "
            "el intervalo de minutos o desactiva la exigencia de cumplir todos los objetivos."
        )
        return
    left, middle, right = st.columns(3)
    left.metric("Candidatos mostrados", len(ranking))
    middle.metric("Mejor brecha (pp)", f"{ranking.iloc[0]['target_gap']:.1f}")
    right.metric("Población de percentiles", int(ranking.iloc[0]["cohort_size"]))
    if ranking.iloc[0]["cohort_size"] < 8:
        st.warning(
            "Hay menos de ocho jugadores en la posición elegible. "
            "Interpreta los percentiles con cautela."
        )
    display = ranking[["player_name", "team_name", "minutes", "target_gap", "goals_met"]].copy()
    display["goals_met"] = display["goals_met"].map(lambda n: f"{n}/{len(goals)}")
    display = display.rename(
        columns={
            "player_name": "Jugador",
            "team_name": "Equipo de plantilla",
            "minutes": "Minutos",
            "target_gap": "Brecha objetivo (pp)",
            "goals_met": "Objetivos cumplidos",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Brecha objetivo (pp)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.download_button(
        "Descargar candidatos del objetivo CSV",
        display.to_csv(index=False),
        file_name="scoutfit-candidatos-objetivo.csv",
        mime="text/csv",
    )
    labels = dict(zip(ranking["profile_id"], ranking["player_name"] + " · " + ranking["team_name"]))
    keep_valid_selection(st.session_state, "target_inspect", list(labels))
    selected = st.selectbox(
        "Inspeccionar resultado del objetivo",
        list(labels),
        format_func=labels.get,
        key="target_inspect",
        persist_state="session",
    )
    player = ranking.loc[ranking["profile_id"] == selected].iloc[0]
    render_participation(player, "Candidato del objetivo")
    reference_card(
        player,
        compare_players(profiles, [selected], features, minimum),
        "Candidato para tu objetivo",
    )
    detail = details.loc[details["profile_id"] == selected]
    figure = go.Figure(
        [
            go.Bar(
                x=detail["percentile"],
                y=detail["metric"],
                orientation="h",
                name="Percentil del jugador",
                marker_color="#345548",
            ),
            go.Scatter(
                x=detail["target"],
                y=detail["metric"],
                mode="markers",
                name="Mínimo deseado",
                marker=dict(symbol="diamond", size=12, color="#ac4b32"),
            ),
        ]
    )
    polish_chart(figure, max(310, 65 * len(goals)))
    figure.update_xaxes(range=[0, 105], title="Percentil en la posición")
    st.plotly_chart(figure, width="stretch", key="target_goal_chart")
    st.dataframe(
        detail[["metric", "value", "percentile", "target", "shortfall", "weight"]]
        .rename(
            columns={
                "metric": "Métrica",
                "value": "Valor del jugador",
                "percentile": "Percentil",
                "target": "Objetivo mínimo",
                "shortfall": "Brecha (pp)",
                "weight": "Importancia",
            }
        )
        .round(2),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Los percentiles usan todos los jugadores elegibles de la posición, liga, "
        "temporada y fuente, "
        "antes de filtrar clubes o el intervalo de minutos de candidatos. Las etiquetas de estilo "
        "inferido no son un requisito adicional de este modo."
    )
    left, right = st.columns(2)
    with left:
        favorite_action(root, player, metadata, "target_favorite", "Guardar candidato en favoritos")
    with right:
        st.button(
            "Buscar jugadores parecidos a este",
            key="target_use_reference",
            on_click=use_reference,
            args=(selected,),
        )
    candidate_project_action(root, player, metadata, "target_project_candidate")
    with st.expander("Cómo se calcula la brecha"):
        st.latex(r"b=\sqrt{\frac{\sum_j w_j\max(P_j^{objetivo}-P_j^{jugador},0)^2}{\sum_j w_j}}")
        st.write(
            "Es la raíz media cuadrática ponderada de los déficits, en puntos de percentil. "
            "Solo entran las métricas elegidas. No es una probabilidad, una valoración global "
            "ni una estimación del encaje táctico real."
        )


def render_target_comparison(profiles, metadata, features, ranking, minimum, config):
    section("Cara a cara", "Compara las alternativas del objetivo")
    if len(ranking) < 2:
        st.info("Necesitas al menos dos candidatos en los resultados para compararlos.")
        return
    labels = dict(zip(ranking["profile_id"], ranking["player_name"] + " · " + ranking["team_name"]))
    key = "target_comparison_players"
    if key not in st.session_state:
        st.session_state[key] = list(labels)[:2]
    st.session_state[key] = [pid for pid in st.session_state[key] if pid in labels][:3]
    ids = st.multiselect(
        "Comparar entre dos y tres candidatos",
        list(labels),
        format_func=labels.get,
        max_selections=3,
        key=key,
        persist_state="session",
    )
    if len(ids) < 2:
        st.info("Selecciona dos o tres candidatos para abrir su radar e informe.")
        return
    comparison = compare_players(profiles, ids, features, minimum)
    st.plotly_chart(percentile_radar(comparison), width="stretch", key="target_comparison_radar")
    notes = st.text_area(
        "Notas de la comparativa del objetivo",
        key="target_comparison_notes",
        max_chars=4000,
        persist_state="session",
    )
    context = "Búsqueda por objetivo (sin referencia inicial):\n" + json.dumps(
        config, ensure_ascii=False, indent=2
    )
    report = html_report(profiles, ids, comparison, metadata, minimum, context + "\n\n" + notes)
    st.download_button(
        "Descargar informe de candidatos HTML",
        report,
        file_name="scoutfit-informe-objetivo.html",
        mime="text/html",
    )
    st.caption(
        "Se comparan jugadores reales; el primero actúa como base del informe, "
        "no como origen de la búsqueda."
    )
