"""Project watchlist changes and visual before/after player dossiers."""

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from scoutfit.datasets import metric_definitions
from scoutfit.history import player_timeline
from scoutfit.tracking import compare_player, project_changes, snapshot_frames
from scoutfit.update_view import local_date
from scoutfit.visuals import polish_chart


def render_change_comparison(timeline, features, metadata, key, baseline_snapshot=None):
    if len(timeline) < 2:
        st.info("Hace falta otra consulta real para comparar valores anteriores y actuales.")
        return
    ordered = timeline.sort_values("consulted_at")
    labels = {r.snapshot: local_date(r.consulted_at.isoformat()) for r in ordered.itertuples()}
    after_key, before_key = f"{key}_after", f"{key}_before"
    available_after = ordered.snapshot.tolist()[1:]
    if st.session_state.get(after_key) not in available_after:
        st.session_state[after_key] = (
            metadata.get("snapshot")
            if metadata.get("snapshot") in available_after
            else available_after[-1]
        )
    left, right = st.columns(2)
    with right:
        after_id = st.selectbox(
            "Consulta final", available_after, format_func=labels.get, key=after_key
        )
    after = ordered.loc[ordered.snapshot.eq(after_id)].iloc[0]
    available_before = ordered.loc[ordered.consulted_at.lt(after.consulted_at), "snapshot"].tolist()
    if not available_before:
        st.info("No hay otra consulta anterior con fecha distinta.")
        return
    if st.session_state.get(before_key) not in available_before:
        st.session_state[before_key] = (
            baseline_snapshot if baseline_snapshot in available_before else available_before[-1]
        )
    with left:
        before_id = st.selectbox(
            "Consulta inicial", available_before, format_func=labels.get, key=before_key
        )
    before = ordered.loc[ordered.snapshot.eq(before_id)].iloc[0]
    report = compare_player(
        before if before.status == "Disponible" else None,
        after if after.status == "Disponible" else None,
        features,
    )
    st.markdown(f"**{report['status']} · {labels[before_id]} → {labels[after_id]} (Madrid)**")
    if not (report["before_available"] and report["after_available"]):
        st.info(
            "Falta un perfil utilizable en alguna consulta. No se rellenan huecos "
            "ni se interpretan como cero minutos, lesión o traspaso."
        )
        return
    with st.container(key=f"{key}_change_summary"):
        minutes, matches, metrics = st.columns(3)
        minutes.metric(
            "Variación de minutos",
            f"{report['minutes_delta']:+.0f}"
            if report["minutes_delta"] is not None
            else "No disponible",
        )
        matches.metric(
            "Variación de partidos",
            f"{report['matches_delta']:+.0f}"
            if report["matches_delta"] is not None
            else "No disponible",
        )
        metrics.metric("Métricas modificadas", report["changed_metrics"])
    st.caption(f"Equipo publicado: {report['team_before']} → {report['team_after']}.")
    if report["incomplete_values"]:
        st.warning(
            "Hay valores ausentes en estas consultas. Sus variaciones se dejan sin calcular."
        )
    if report["possible_correction"]:
        st.warning(
            "Posible corrección del proveedor: disminuyen minutos, partidos o un conteo "
            "acumulado. No se interpreta como caída de rendimiento."
        )
    table = pd.DataFrame(report["metrics"])
    rates = table.loc[table.unit.eq("/90") & table.delta.notna()].copy()
    if not rates.empty:
        rates["Sentido"] = rates.delta.map(lambda x: "Aumento" if x >= 0 else "Descenso")
        figure = px.bar(
            rates,
            x="delta",
            y="metric",
            orientation="h",
            color="Sentido",
            color_discrete_map={"Aumento": "#345548", "Descenso": "#ac4b32"},
            labels={"delta": "Variación absoluta /90", "metric": "Métrica"},
        )
        figure.update_layout(yaxis_title=None, height=470)
        st.plotly_chart(polish_chart(figure, 470), width="stretch", key=f"{key}_delta_chart")
    display = (
        table[["metric", "before", "after", "delta", "unit"]]
        .rename(
            columns={
                "metric": "Métrica",
                "before": "Antes",
                "after": "Después",
                "delta": "Variación",
                "unit": "Unidad",
            }
        )
        .round(3)
    )
    st.dataframe(display, hide_index=True, width="stretch")
    report.update(
        before_snapshot=before_id,
        after_snapshot=after_id,
        player_id=int(after["player_id"]) if "player_id" in after else None,
    )
    st.download_button(
        "Descargar cambios del jugador CSV",
        display.to_csv(index=False),
        file_name="scoutfit-cambios-jugador.csv",
        mime="text/csv",
        key=f"{key}_csv",
    )
    st.download_button(
        "Descargar ficha de cambios JSON",
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        file_name="scoutfit-cambios-jugador.json",
        mime="application/json",
        key=f"{key}_json",
    )
    st.caption(
        "Una variación positiva no implica mejora. Las barras comparan tasas acumuladas /90; "
        "el porcentaje de pase cambia en puntos porcentuales (pp) y figura solo en la tabla. "
        "Son consultas de temporada, no partidos individuales."
    )


def render_project_tracking(root, project, profiles, metadata, candidate):
    if metadata.get("provider") != "espn":
        return
    with st.expander("Qué ha cambiado en mis candidatos", expanded=False):
        st.caption(
            "Comparación con la consulta en la que se guardó cada candidato. "
            "Las notas y los estados de seguimiento se conservan."
        )
        if not st.checkbox(
            "Mostrar seguimiento del proyecto", key=f"project_tracking_{project['id']}"
        ):
            return
        snapshots, errors = snapshot_frames(root / "data/processed", metadata)
        if errors:
            st.warning(
                "No se pudieron leer algunas consultas; las bases ausentes no se sustituyen."
            )
        features = metric_definitions(metadata)
        report = project_changes(project, profiles, metadata, snapshots, features)
        display = report[
            [
                "player_name",
                "status",
                "baseline_snapshot",
                "team_before",
                "team_after",
                "minutes_delta",
                "matches_delta",
                "changed_metrics",
                "possible_correction",
            ]
        ].rename(
            columns={
                "player_name": "Jugador",
                "status": "Cambios desde que se guardó",
                "baseline_snapshot": "Consulta de origen",
                "team_before": "Equipo anterior",
                "team_after": "Equipo actual",
                "minutes_delta": "Δ minutos",
                "matches_delta": "Δ partidos",
                "changed_metrics": "Métricas modificadas",
                "possible_correction": "Posible corrección",
            }
        )
        st.dataframe(display, hide_index=True, width="stretch")
        st.download_button(
            "Descargar seguimiento de cambios CSV",
            display.to_csv(index=False),
            file_name="scoutfit-seguimiento-cambios.csv",
            mime="text/csv",
            key=f"project_tracking_csv_{project['id']}",
        )
        st.caption(
            "No disponible significa que falta un perfil estadístico utilizable; "
            "no confirma una baja deportiva. Los equipos son los publicados por la fuente."
        )
        scoped = report.loc[report.key.eq(candidate["key"])].iloc[0]
        if scoped["status"] in (
            "Otra fuente, liga o temporada",
            "Sin consulta de origen comparable",
            "Origen posterior a la consulta activa",
        ):
            st.info(
                "El candidato seleccionado no tiene una base de origen comparable "
                "con la consulta activa."
            )
            return
        if scoped["status"] == "Misma consulta al guardar":
            st.info("Todavía no hay una consulta nueva desde que guardaste este candidato.")
            return
        st.markdown(f"**Ficha de cambios · {candidate['player_name']}**")
        timeline = player_timeline(snapshots, int(candidate["player_id"]), features)
        if not timeline.empty:
            render_change_comparison(
                timeline,
                features,
                metadata,
                f"project_delta_{project['id']}_{candidate['key']}",
                baseline_snapshot=candidate["snapshot"],
            )
