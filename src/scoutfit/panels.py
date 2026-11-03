"""Workspace panels. All local paths are supplied by the app, including in tests."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scoutfit.candidate_filters import filter_candidates
from scoutfit.comparison import compare_players, html_report
from scoutfit.evaluation import benchmark_template, evaluate_judgments, sensitivity_report
from scoutfit.explorer import percentile_radar
from scoutfit.history import discover_snapshots, interval_changes, player_timeline
from scoutfit.recommender import recommend
from scoutfit.search import keep_valid_selection
from scoutfit.tracking_view import render_change_comparison
from scoutfit.visuals import COLORS, polish_chart, section
from scoutfit.workspace import (
    import_reviews,
    load_records,
    player_key,
    remove_favorite,
    save_favorite,
    save_judgment,
)


def favorite_action(root: Path, player: pd.Series, metadata: dict, key: str, label: str):
    path = root / "data/user/favorites.json"
    saved = any(row["key"] == player_key(player, metadata) for row in load_records(path))
    if st.button("En favoritos" if saved else label, key=key, disabled=saved):
        save_favorite(path, player, metadata)
        st.success(f"{player['player_name']} guardado en favoritos.")


def render_comparison(
    root, profiles, metadata, features, reference, ranking, minimum, candidate_filters=None
):
    section(
        "Cara a cara",
        "Comparativa de jugadores",
        "Contrasta el estilo, revisa los valores y prepara un informe para tu seguimiento.",
    )
    pool = profiles.loc[
        (profiles["role"] == reference["role"])
        & (profiles["competition_id"] == reference["competition_id"])
        & (profiles["season_id"] == reference["season_id"])
        & (profiles["minutes"] >= minimum)
        & (profiles["player_id"] != reference["player_id"])
    ].sort_values("player_name")
    pool = filter_candidates(pool, candidate_filters)
    labels = dict(zip(pool["profile_id"], pool["player_name"] + " · " + pool["team_name"]))
    options = list(labels)
    if not options:
        st.info("No hay otros jugadores de esta posición que cumplan los filtros de candidatos.")
        return
    if "comparison_extra" not in st.session_state:
        st.session_state["comparison_extra"] = [
            pid for pid in ranking["profile_id"].head(1) if pid in options
        ]
    st.session_state["comparison_extra"] = [
        pid for pid in st.session_state["comparison_extra"] if pid in options
    ][:2]
    selected = st.multiselect(
        "Añadir hasta dos jugadores",
        options,
        format_func=labels.get,
        max_selections=2,
        key="comparison_extra",
        persist_state="session",
    )
    ids = [reference["profile_id"], *selected]
    st.caption(
        f"Referencia: {reference['player_name']}. Se comparan jugadores de la misma posición, "
        f"liga y temporada con al menos {minimum:g} minutos."
    )
    if len(ids) < 2:
        st.info("Añade uno o dos jugadores para ver la comparativa y descargar el informe.")
        return
    data = compare_players(profiles, ids, features, minimum)
    st.plotly_chart(percentile_radar(data), width="stretch", key="comparison_radar")
    st.caption(
        "ADN estadístico por percentiles de la posición. Cada radio es una métrica; "
        "el área del radar no es una puntuación de calidad."
    )
    raw = data.pivot(index="metric", columns="player_label", values="value").reindex(
        index=features.values(), columns=data["player_label"].drop_duplicates()
    )
    st.dataframe(raw.round(2).rename_axis(index="Métrica", columns="Jugador"), width="stretch")
    chart = px.bar(
        data,
        x="percentile",
        y="metric",
        color="player_label",
        orientation="h",
        barmode="group",
        range_x=[0, 100],
        height=650,
        color_discrete_sequence=COLORS,
        labels={"percentile": "Percentil en la posición", "metric": "", "player_label": "Jugador"},
    )
    chart.update_layout(legend=dict(orientation="h", y=1.16), margin=dict(l=0, r=0, t=70, b=0))
    with st.expander("Desglosar percentiles por métrica"):
        st.plotly_chart(polish_chart(chart, 650), width="stretch")
    st.caption(
        "Un percentil alto describe estilo o volumen. No significa automáticamente que sea mejor. "
        "Los grupos de posición y los perfiles inferidos son conceptos distintos."
    )
    notes = st.text_area(
        "Notas del informe",
        max_chars=4000,
        key="comparison_notes",
        persist_state="session",
        placeholder="Contexto del equipo, ventajas del candidato y dudas pendientes.",
    )
    report = html_report(profiles, ids, data, metadata, minimum, notes)
    st.download_button(
        "Descargar informe HTML",
        report.encode("utf-8"),
        file_name="scoutfit-informe.html",
        mime="text/html",
        key="comparison_report",
    )
    st.caption("Informe autónomo: se puede abrir sin conexión e imprimir desde el navegador.")
    if st.button("Guardar comparados en favoritos", key="favorite_comparison"):
        for pid in ids:
            player = profiles.loc[profiles["profile_id"] == pid].iloc[0]
            save_favorite(root / "data/user/favorites.json", player, metadata)
        st.success(f"{len(ids)} jugadores guardados.")


def render_favorites(root, profiles, metadata):
    section("Tu espacio de trabajo", "Lista de seguimiento", "Guarda talento. Añade contexto.")
    path = root / "data/user/favorites.json"
    rows = load_records(path)
    if not rows:
        st.info("Todavía no hay favoritos. Guarda la referencia, un candidato o una comparativa.")
        return
    st.caption(
        "Favoritos y notas se guardan en este proyecto local. No se envían a ningún servicio."
    )
    current = {
        (
            metadata.get("provider", "statsbomb"),
            int(p["competition_id"]),
            int(p["season_id"]),
            int(p["player_id"]),
        ): p
        for _, p in profiles.iterrows()
    }
    display = []
    for row in rows:
        player = current.get(
            (row["provider"], row["competition_id"], row["season_id"], row["player_id"])
        )
        display.append(
            {
                "Jugador": row["player_name"],
                "Equipo al guardar": row["team_at_save"],
                "Equipo en consulta activa": player["team_name"]
                if player is not None
                else "No disponible",
                "Temporada inicial": row["season_id"],
                "Nota": row["note"],
            }
        )
    table = pd.DataFrame(display)
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button(
        "Exportar favoritos CSV",
        table.to_csv(index=False).encode("utf-8"),
        file_name="scoutfit-favoritos.csv",
        mime="text/csv",
        key="favorites_export",
    )
    labels = {
        row["key"]: f"{row['player_name']} · {row['team_at_save']} · {row['season_id']}"
        for row in rows
    }
    keep_valid_selection(st.session_state, "favorite_edit", list(labels))
    choice = st.selectbox(
        "Editar favorito", list(labels), format_func=labels.get, key="favorite_edit"
    )
    record = next(row for row in rows if row["key"] == choice)
    note = st.text_area(
        "Nota de seguimiento", value=record["note"], max_chars=4000, key=f"favorite_note_{choice}"
    )
    left, right = st.columns(2)
    with left:
        if st.button("Guardar nota", key="favorite_save_note"):
            updated = [{**row, "note": note} if row["key"] == choice else row for row in rows]
            from scoutfit.workspace import write_records

            write_records(path, updated)
            st.success("Nota guardada.")
    with right:
        if st.button("Quitar de favoritos", key="favorite_remove"):
            remove_favorite(path, choice)
            st.rerun()


def render_evaluation(
    root,
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
    candidate_filters=None,
):
    section("Método y evidencia", "Laboratorio de recomendaciones")
    st.caption("La estabilidad técnica y la relevancia futbolística se evalúan por separado.")
    snapshot = metadata.get("snapshot", metadata.get("revision", "historical"))
    configuration = json.dumps(
        [
            snapshot,
            reference["profile_id"],
            minimum,
            weights,
            match_role,
            exclude_team,
            top_k,
            candidate_filters.to_dict() if candidate_filters else None,
        ],
        sort_keys=True,
    )
    config_id = hashlib.sha256(configuration.encode()).hexdigest()[:16]
    with st.expander("Estabilidad y alternativas de distancia", expanded=True):
        if st.button("Ejecutar 30 pruebas de sensibilidad", key="run_sensitivity"):
            try:
                with st.spinner("Variando pesos y mínimos de minutos…"):
                    result = sensitivity_report(
                        profiles,
                        reference["profile_id"],
                        features,
                        minimum,
                        top_k,
                        weights,
                        match_role,
                        exclude_team,
                        candidate_filters=candidate_filters,
                    )
                st.session_state["sensitivity_result"] = (config_id, result)
            except ValueError as exc:
                st.warning(str(exc))
        stored = st.session_state.get("sensitivity_result")
        if stored and stored[0] == config_id:
            runs, frequencies, thresholds = stored[1]
            st.metric("Coincidencia media del top-k (Jaccard)", f"{runs['jaccard'].mean():.2f}")
            st.caption(
                "Pesos perturbados con semilla fija. La frecuencia mide presencia en estas "
                "pruebas; no es probabilidad de éxito ni confianza estadística."
            )
            st.dataframe(
                frequencies[["player_name", "appearances", "trials", "frequency"]].rename(
                    columns={
                        "player_name": "Jugador",
                        "appearances": "Apariciones",
                        "trials": "Pruebas",
                        "frequency": "Frecuencia en las pruebas",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
            st.dataframe(
                thresholds.rename(
                    columns={
                        "min_minutes": "Mínimo de minutos",
                        "candidates": "Candidatos",
                        "jaccard": "Coincidencia con el top base",
                        "status": "Estado",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
        if st.button("Comparar Euclídea y coseno", key="compare_methods"):
            methods = []
            for method, label in (("euclidean", "Euclídea"), ("cosine", "Coseno")):
                try:
                    candidates, _ = recommend(
                        profiles,
                        reference["profile_id"],
                        minimum,
                        top_k,
                        exclude_team,
                        weights,
                        feature_definitions=features,
                        match_inferred_role=match_role,
                        distance_metric=method,
                        candidate_filters=candidate_filters,
                    )
                    methods.extend(
                        {"Método": label, "Puesto": index + 1, "Jugador": row["player_name"]}
                        for index, row in candidates.iterrows()
                    )
                except ValueError as exc:
                    st.warning(f"{label}: {exc}")
            st.session_state["method_result"] = (config_id, methods)
        stored_methods = st.session_state.get("method_result")
        if stored_methods and stored_methods[0] == config_id:
            st.dataframe(pd.DataFrame(stored_methods[1]), hide_index=True, width="stretch")
            st.caption(
                "Las distancias usan escalas distintas. Aquí se comparan los candidatos y el orden."
            )

    judgments_path = root / "data/user/judgments.json"
    judgments = load_records(judgments_path)
    scoped = [row for row in judgments if row["snapshot"] == snapshot]
    st.markdown("**Revisión futbolística manual**")
    st.caption(
        "La revisión manual evalúa el baseline equilibrado de la liga, sin los filtros "
        "de candidatos ni tus pesos personalizados. Las pruebas de estabilidad de arriba "
        "sí usan los filtros de la búsqueda activa."
    )
    st.write(
        f"{len(scoped)} parejas revisadas en esta consulta. "
        "No se generan etiquetas automáticamente."
    )
    st.caption(
        "Rúbrica: 0 = estilo inadecuado; 1 = parecido parcial; 2 = buen sustituto de estilo. "
        "Revisa funciones y diferencias; no valores fama, precio o calidad global."
    )
    pool = profiles.loc[
        (profiles["role"] == reference["role"])
        & (profiles["competition_id"] == reference["competition_id"])
        & (profiles["season_id"] == reference["season_id"])
        & (profiles["minutes"] >= minimum)
        & (profiles["player_id"] != reference["player_id"])
        & (profiles["team_id"] != reference["team_id"])
    ].sort_values("player_name")
    if not pool.empty:
        labels = dict(zip(pool["profile_id"], pool["player_name"] + " · " + pool["team_name"]))
        keep_valid_selection(st.session_state, "review_candidate", list(labels))
        candidate_id = st.selectbox(
            "Candidato para revisar", list(labels), format_func=labels.get, key="review_candidate"
        )
        pair_key = f"{snapshot}:{reference['profile_id']}:{candidate_id}"
        existing = next(
            (
                row
                for row in scoped
                if row["reference_id"] == reference["profile_id"]
                and row["candidate_id"] == candidate_id
            ),
            None,
        )
        with st.form("relevance_form"):
            grade = st.selectbox(
                "Relevancia de estilo",
                ["Sin valorar", "0", "1", "2"],
                index=existing["relevance"] + 1 if existing else 0,
                key=f"grade_{pair_key}",
            )
            note = st.text_area(
                "Justificación de la valoración",
                value=existing["note"] if existing else "",
                max_chars=4000,
                key=f"review_note_{pair_key}",
            )
            if st.form_submit_button("Guardar valoración"):
                if grade == "Sin valorar" or not note.strip():
                    st.warning("Elige una relevancia y añade una justificación.")
                else:
                    save_judgment(
                        judgments_path,
                        {
                            "snapshot": snapshot,
                            "reference_id": reference["profile_id"],
                            "candidate_id": candidate_id,
                            "relevance": int(grade),
                            "note": note.strip(),
                            "reviewer": "Revisión local",
                        },
                    )
                    st.session_state.pop("judgment_result", None)
                    st.success("Valoración guardada. Ya puedes recalcular las métricas.")
    if st.button("Calcular métricas de revisión", key="evaluate_judgments"):
        scored, skipped = evaluate_judgments(
            profiles, features, load_records(judgments_path), snapshot, top_k, minimum
        )
        st.session_state["judgment_result"] = (config_id, scored, skipped)
    stored_review = st.session_state.get("judgment_result")
    if stored_review and stored_review[0] == config_id:
        scored, skipped = stored_review[1:]
        if scored.empty:
            st.info(
                "Falta revisión suficiente: al menos dos candidatos "
                "con relevancias diferentes por referencia."
            )
        else:
            summary = scored.groupby("method").agg(
                references=("reference_id", "nunique"),
                ndcg=("ndcg", "mean"),
                precision=("precision", "mean"),
                recall=("recall", "mean"),
                top_k_reviewed=("judged_top_k_coverage", "mean"),
            )
            st.dataframe(
                summary.rename(
                    columns={
                        "references": "Referencias",
                        "ndcg": "nDCG@k (revisados)",
                        "precision": "Precisión@k (revisados)",
                        "recall": "Recuperación@k (revisados)",
                        "top_k_reviewed": "Cobertura revisada del top-k",
                    }
                ).rename_axis("Método"),
                width="stretch",
            )
            st.download_button(
                "Exportar evaluación CSV",
                scored.to_csv(index=False).encode("utf-8"),
                file_name="scoutfit-evaluacion.csv",
                mime="text/csv",
            )
        if skipped:
            st.caption("Referencias/métodos no evaluables:")
            st.write(skipped)
        st.caption(
            "nDCG, precisión y recuperación se calculan SOLO en el conjunto revisado, "
            "reordenado por cada método, con pesos equilibrados y sin filtro de perfil. "
            "La cobertura informa qué parte del top-k completo ha sido revisada. "
            "Estos resultados no certifican la calidad en toda la liga."
        )
    if st.button("Crear plantilla de 20 referencias", key="prepare_benchmark"):
        with st.spinner("Preparando referencias y candidatos sin etiquetar…"):
            template = benchmark_template(profiles, features, snapshot)
        path = root / "data/evaluation" / f"{snapshot}-template.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        template.to_csv(path, index=False)
        st.session_state["benchmark_template"] = (
            snapshot,
            template.to_csv(index=False).encode("utf-8"),
        )
    template = st.session_state.get("benchmark_template")
    if template and template[0] == snapshot:
        st.download_button(
            "Descargar plantilla CSV sin valorar",
            template[1],
            file_name="scoutfit-benchmark.csv",
            mime="text/csv",
        )
        st.caption(
            "Completa relevancia, nota y revisor. No contiene valoraciones inventadas. "
            "Puedes importarla aquí o con scoutfit import-reviews ARCHIVO.csv."
        )
    uploaded = st.file_uploader("Importar plantilla revisada (CSV)", type=["csv"], key="review_csv")
    if uploaded is not None and st.button("Importar valoraciones del CSV", key="import_reviews"):
        if uploaded.size > 2_000_000:
            st.warning("La plantilla no puede superar 2 MB.")
        else:
            try:
                uploaded.seek(0)
                count = import_reviews(judgments_path, uploaded, snapshot, profiles)
                st.session_state.pop("judgment_result", None)
                st.success(
                    f"{count} valoraciones importadas. Los campos sin valorar se han omitido."
                )
            except (ValueError, OSError) as exc:
                st.warning(str(exc))


def render_history(root, profiles, metadata, features, reference):
    section("Seguimiento temporal", "Evolución entre consultas")
    if metadata.get("provider") != "espn":
        st.info("La evolución está disponible para las consultas guardadas de ESPN.")
        return
    snapshots, errors = discover_snapshots(root / "data/processed", metadata)
    if errors:
        st.warning("Hay consultas que no se han podido leer: " + "; ".join(errors))
    if not snapshots:
        st.info("Todavía no hay consultas guardadas para esta liga y temporada.")
        return
    labels = {int(p.player_id): f"{p.player_name} · {p.team_name}" for p in profiles.itertuples()}
    selection_key = f"history_player_{reference['profile_id']}"
    if st.session_state.get(selection_key) not in labels:
        st.session_state[selection_key] = int(reference["player_id"])
    player_id = st.selectbox(
        "Jugador de evolución", list(labels), format_func=labels.get, key=selection_key
    )
    timeline = player_timeline(snapshots, int(player_id), features)
    st.caption(
        f"{labels[player_id]} · {len(snapshots)} consultas reales guardadas. "
        "Se sigue el ID del jugador aunque cambie de club dentro de la temporada."
    )
    metric = st.selectbox(
        "Métrica de evolución", list(features), format_func=features.get, key="history_metric"
    )
    if len(timeline) < 2:
        st.info(
            "Hace falta otra consulta real para mostrar cambios. "
            "Ejecuta uv run scoutfit update otro día."
        )
    timeline["consulted_at"] = pd.to_datetime(timeline["consulted_at"], utc=True).dt.tz_convert(
        "Europe/Madrid"
    )
    if metric in timeline:
        figure = px.line(
            timeline,
            x="consulted_at",
            y=metric,
            markers=True,
            color_discrete_sequence=COLORS,
            labels={"consulted_at": "Consulta (Madrid)", metric: features[metric]},
        )
        st.plotly_chart(polish_chart(figure, 370), width="stretch")
    columns = [
        name
        for name in (
            "consulted_at",
            "team_name",
            "minutes",
            "matches",
            "inferred_role",
            metric,
            "status",
        )
        if name in timeline
    ]
    st.dataframe(
        timeline[columns].rename(
            columns={
                "consulted_at": "Consulta (Madrid)",
                "team_name": "Equipo de plantilla",
                "minutes": "Minutos",
                "matches": "Partidos",
                "inferred_role": "Perfil inferido",
                "status": "Estado",
                **features,
            }
        ),
        hide_index=True,
        width="stretch",
    )
    changes = interval_changes(timeline, metric)
    if not changes.empty:
        st.markdown("**Contexto del tramo entre consultas**")
        st.dataframe(
            changes.rename(
                columns={
                    "from": "Desde",
                    "to": "Hasta",
                    "minutes_added": "Minutos nuevos",
                    "interval_rate": "Tasa /90 del tramo",
                    "status": "Estado",
                }
            ),
            hide_index=True,
            width="stretch",
        )
    st.download_button(
        "Descargar evolución CSV",
        timeline.to_csv(index=False).encode("utf-8"),
        file_name="scoutfit-evolucion.csv",
        mime="text/csv",
        key="history_export",
    )
    st.caption(
        "Son agregados acumulados de temporada. "
        "Un tramo puede incluir cero, uno o varios partidos. "
        "Las correcciones del proveedor se señalan; no se inventan tasas cuando faltan minutos. "
        "No hay datos por partido ni posesión para medir regularidad "
        "o ajustar por contexto táctico."
    )
    section("Ficha del jugador", "Qué ha cambiado entre dos consultas")
    render_change_comparison(timeline, features, metadata, f"history_delta_{player_id}")
