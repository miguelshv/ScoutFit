"""Visible sample context; thresholds are descriptive, never confidence scores."""

import hashlib
import json

import streamlit as st

from scoutfit.sample_context import participation, sample_summary, threshold_comparison


def render_participation(player, label="Jugador"):
    st.caption(
        f"{label}: {player['minutes']:.0f} minutos · {participation(player['minutes'])}. "
        "Describe participación acumulada, no certeza ni calidad."
    )


def render_sample_context(
    profiles, metadata, features, reference, minimum, config, mode="similarity"
):
    summary = sample_summary(profiles, reference, minimum)
    with st.expander("Contexto de muestra · minutos y población", expanded=False):
        st.write(
            f"**{summary['cohort_size']} perfiles de {reference['role']} · "
            f"{summary['clubs']} clubes · mínimo {minimum:g} minutos**"
        )
        st.caption(
            "Esta es la población que fija las escalas y los percentiles, antes de filtrar "
            "clubes, minutos de candidatos o perfil inferido. Solo se compara la misma "
            "posición, liga, temporada y fuente."
        )
        if summary["median_minutes"] is not None:
            st.caption(
                f"Mediana de participación del grupo: {summary['median_minutes']:.0f} minutos."
            )
        if mode == "similarity":
            render_participation(reference, "Referencia")
        if summary["small_cohort"]:
            st.warning(
                "Población reducida: menos de 20 jugadores. Las escalas y percentiles "
                "pueden cambiar sensiblemente al añadir o excluir perfiles."
            )
        if summary["below_450"]:
            st.warning(
                f"Hay {summary['below_450']} perfiles con menos de 450 minutos en la población. "
                "Las tasas /90 con poca participación pueden ser extremas."
            )
        st.caption(
            "Participación: reducida <450 min; intermedia 450–899; mayor ≥900. "
            "Son umbrales orientativos, no intervalos de confianza. "
            "El total acumulado no permite medir regularidad por partido."
        )
        serial = {
            **config,
            "candidate_filters": config["candidate_filters"].to_dict()
            if config.get("candidate_filters")
            else None,
        }
        signature = hashlib.sha256(
            json.dumps(
                [
                    metadata.get("snapshot", metadata.get("revision")),
                    reference["profile_id"],
                    minimum,
                    serial,
                    mode,
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if st.button("Comparar mínimos de minutos", key=f"sample_run_{mode}"):
            frame = threshold_comparison(profiles, features, reference, minimum, config, mode)
            st.session_state[f"sample_result_{mode}"] = (signature, frame)
        stored = st.session_state.get(f"sample_result_{mode}")
        if stored and stored[0] == signature:
            frame = stored[1].rename(
                columns={
                    "minimum": "Mínimo de minutos",
                    "cohort_size": "Población de la posición",
                    "candidates": "Candidatos mostrados",
                    "retained": "Conservados del top actual",
                    "jaccard": "Jaccard del top",
                    "status": "Estado",
                }
            )
            st.dataframe(
                frame,
                hide_index=True,
                width="stretch",
                column_config={"Jaccard del top": st.column_config.NumberColumn(format="%.2f")},
            )
            st.caption(
                "Jaccard mide coincidencia con el top actual (0–1), no precisión. "
                "Cada mínimo recalcula la población manteniendo pesos, objetivos y filtros. "
                "Si la referencia no alcanza un mínimo, se indica y no se relaja el requisito."
            )
            st.download_button(
                "Descargar análisis de muestra CSV",
                frame.to_csv(index=False),
                file_name="scoutfit-muestra.csv",
                mime="text/csv",
                key=f"sample_csv_{mode}",
            )
