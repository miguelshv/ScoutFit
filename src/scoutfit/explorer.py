"""Weighted projection and percentile radar; no invented fit or quality scores."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from scoutfit.comparison import compare_players
from scoutfit.search import keep_valid_selection
from scoutfit.visuals import COLORS, polish_chart, reference_card, section


def project_profiles(profiles, reference_id, features, minimum, weights, candidate_ids=()):
    """Fit PCA on the whole eligible position cohort, not only displayed recommendations."""
    selected = profiles.loc[profiles["profile_id"] == reference_id]
    if len(selected) != 1:
        raise ValueError("Referencia no encontrada")
    reference = selected.iloc[0]
    mask = profiles["minutes"] >= minimum
    for column in ("role", "competition_id", "season_id", "provider"):
        if column in profiles:
            mask &= profiles[column] == reference[column]
    cohort = profiles.loc[mask].sort_values("profile_id").copy()
    if reference_id not in set(cohort["profile_id"]):
        raise ValueError("La referencia no alcanza el mínimo de minutos")
    w = np.array([weights.get(name, 1.0) for name in features], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("Los pesos deben ser finitos, no negativos y sumar más de cero")
    values = cohort[list(features)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("No se proyectan métricas incompletas")
    if len(cohort) < 3 or len(features) < 2:
        return pd.DataFrame(), (0.0, 0.0)
    scaled = StandardScaler().fit_transform(values) * np.sqrt(w / w.sum())
    if np.var(scaled, axis=0).sum() <= 1e-12:
        return pd.DataFrame(), (0.0, 0.0)
    model = PCA(n_components=2, svd_solver="full")
    coordinates = model.fit_transform(scaled)
    cohort["Eje 1"], cohort["Eje 2"] = coordinates.T
    cohort["Grupo"] = np.where(
        cohort["profile_id"].eq(reference_id),
        "Referencia",
        np.where(cohort["profile_id"].isin(candidate_ids), "Candidato", "Resto de la posición"),
    )
    return cohort, tuple(model.explained_variance_ratio_)


def percentile_radar(comparison):
    """One spoke per published metric; percentile population matches compare_players."""
    figure = go.Figure()
    short_labels = {
        "passes_p90": "Pases",
        "completion_pct": "Precisión",
        "key_passes_p90": "Pases de tiro",
        "provider_progressive_carries_p90": "Conducciones",
        "crosses_p90": "Centros",
        "long_balls_p90": "Pases largos",
        "recoveries_p90": "Recuperaciones",
        "tackles_won_p90": "Entradas",
        "interceptions_p90": "Intercepciones",
        "shots_p90": "Tiros",
        "duels_won_p90": "Duelos",
        "box_touches_p90": "Toques en área",
    }
    for index, (_, rows) in enumerate(comparison.groupby("profile_id", sort=False)):
        labels = [label.replace(" (ESPN)", "").replace(" /90", "") for label in rows["metric"]]
        values = rows["percentile"].tolist()
        figure.add_trace(
            go.Scatterpolar(
                r=values + values[:1],
                theta=labels + labels[:1],
                name=rows.iloc[0]["player_name"],
                mode="lines+markers",
                fill="toself",
                opacity=0.8,
                line=dict(color=COLORS[index % len(COLORS)], width=2),
                hovertemplate="%{theta}<br>Percentil %{r:.0f}<extra>%{fullData.name}</extra>",
            )
        )
    polish_chart(figure, 500)
    figure.update_layout(
        margin=dict(l=70, r=70, t=45, b=70),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], tickvals=[25, 50, 75, 100], gridcolor="#dfe8e7"),
            angularaxis=dict(
                gridcolor="#dfe8e7",
                tickfont=dict(size=10),
                tickvals=labels,
                ticktext=[
                    short_labels.get(r["feature"], label)
                    for (_, r), label in zip(rows.iterrows(), labels)
                ],
            ),
        ),
    )
    return figure


def render_map(profiles, reference, features, minimum, weights, ranking, use_reference):
    section(
        "Exploración visual",
        "El mapa de tu búsqueda",
        "Explora la posición completa. Cada punto es un jugador; "
        "pasa el cursor para identificarlo.",
    )
    projected, variance = project_profiles(
        profiles, reference["profile_id"], features, minimum, weights, ranking["profile_id"]
    )
    if projected.empty:
        st.info("El mapa necesita al menos tres perfiles y variación en las métricas activas.")
        return
    figure = px.scatter(
        projected.rename(
            columns={"player_name": "Jugador", "team_name": "Equipo", "minutes": "Minutos"}
        ),
        x="Eje 1",
        y="Eje 2",
        color="Grupo",
        symbol="Grupo",
        hover_name="Jugador",
        hover_data={"Equipo": True, "Minutos": True, "Eje 1": False, "Eje 2": False},
        category_orders={"Grupo": ["Resto de la posición", "Candidato", "Referencia"]},
        color_discrete_map={
            "Resto de la posición": "#b9bdad",
            "Candidato": "#ac4b32",
            "Referencia": "#345548",
        },
        symbol_map={"Resto de la posición": "circle", "Candidato": "diamond", "Referencia": "star"},
    )
    for trace in figure.data:
        trace.update(marker=dict(size=18 if trace.name == "Referencia" else 11, line=dict(width=1)))
    polish_chart(figure, 470)
    figure.update_xaxes(title=f"Componente 1 · {variance[0]:.0%} de variación")
    figure.update_yaxes(title=f"Componente 2 · {variance[1]:.0%} de variación")
    st.plotly_chart(figure, width="stretch", key="profile_map")
    st.caption(
        f"PCA sobre {len(projected)} jugadores de {reference['role']} con ≥{minimum:g} minutos. "
        f"Los dos ejes conservan {sum(variance):.1%} de la variación ponderada. "
        "La cercanía en 2D es aproximada: el ranking usa todas las métricas y tus pesos. "
        "El mapa muestra toda la posición como contexto, incluso clubes excluidos "
        "o jugadores fuera del intervalo de candidatos. Solo se resaltan los resultados filtrados."
    )
    options = projected.sort_values("player_name")
    labels = dict(zip(options["profile_id"], options["player_name"] + " · " + options["team_name"]))
    keep_valid_selection(st.session_state, "map_player", list(labels))
    selected = st.selectbox(
        "Explorar jugador del mapa", list(labels), format_func=labels.get, key="map_player"
    )
    player = projected.loc[projected["profile_id"] == selected].iloc[0]
    reference_card(
        player, compare_players(profiles, [selected], features, minimum), "Perfil en exploración"
    )
    st.button(
        "Usar como referencia",
        key="map_use_reference",
        type="primary",
        disabled=selected == reference["profile_id"],
        on_click=use_reference,
        args=(selected,),
    )
