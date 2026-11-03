"""Shared candidate filters for reference-based and target-based searches."""

import streamlit as st

from scoutfit.candidate_filters import CandidateFilters


def reset_candidate_filters():
    st.session_state.update(
        candidate_teams_include=[],
        candidate_teams_exclude=[],
        candidate_min_minutes=0,
        candidate_max_minutes=5000,
    )


def render_candidate_filters(profiles, minimum):
    teams = profiles[["team_id", "team_name"]].drop_duplicates().sort_values("team_name")
    labels = {int(row.team_id): row.team_name for row in teams.itertuples()}
    with st.expander("Filtrar candidatos · clubes y minutos", expanded=False):
        st.caption(
            "Estos filtros solo restringen los resultados; no cambian tu referencia ni "
            "la población de cálculo. Sin clubes incluidos se busca en todos. "
            "La exclusión tiene prioridad si un club aparece en ambas listas."
        )
        for key in ("candidate_teams_include", "candidate_teams_exclude"):
            if key in st.session_state:
                st.session_state[key] = [pid for pid in st.session_state[key] if pid in labels]
        left, right = st.columns(2)
        with left:
            included = st.multiselect(
                "Buscar candidatos en estos clubes",
                list(labels),
                format_func=labels.get,
                key="candidate_teams_include",
                placeholder="Todos los clubes",
                persist_state="session",
            )
            lower = st.number_input(
                "Minutos mínimos del candidato",
                min_value=0,
                max_value=5000,
                value=0,
                step=50,
                key="candidate_min_minutes",
                persist_state="session",
            )
        with right:
            excluded = st.multiselect(
                "Excluir candidatos de estos clubes",
                list(labels),
                format_func=labels.get,
                key="candidate_teams_exclude",
                persist_state="session",
            )
            upper = st.number_input(
                "Minutos máximos del candidato",
                min_value=0,
                max_value=5000,
                value=5000,
                step=50,
                key="candidate_max_minutes",
                persist_state="session",
            )
        st.caption(
            f"El mínimo de muestra de la búsqueda es {minimum:g} min. "
            "El intervalo de candidatos se aplica además de ese mínimo. "
            "En el ranking por parecido también se respeta la exclusión del equipo de referencia."
        )
        st.button(
            "Limpiar filtros de candidatos",
            key="reset_candidate_filters",
            on_click=reset_candidate_filters,
        )
        if lower > upper:
            st.warning("El mínimo de minutos del candidato no puede superar el máximo.")
            st.stop()
    filters = CandidateFilters(tuple(included), tuple(excluded), lower, upper)
    if included or excluded or lower > 0 or upper < 5000:
        included_text = ", ".join(labels[pid] for pid in included) or "todos los clubes"
        excluded_text = ", ".join(labels[pid] for pid in excluded) or "ninguno"
        st.caption(
            f"Candidatos: {included_text} · Excluidos: {excluded_text} · "
            f"Intervalo: {lower:g}–{upper:g} min (mínimo efectivo {max(lower, minimum):g})."
        )
    return filters
