"""A private project notebook and printable single-player dossier."""

import json

import streamlit as st

from scoutfit.dossier import dossier_html, individual_dossier, local_date
from scoutfit.observations import (
    VERDICTS,
    append_observation,
    local_today,
    observation_history,
    save_assessment,
    video_position,
    video_url,
)
from scoutfit.workspace import player_key


def render_observations(path, project, candidate, profiles, metadata):
    token = f"{project['id']}_{candidate['key']}"
    if st.session_state.pop(f"observation_reset_{token}", False):
        for field in ("context", "strengths", "doubts", "next", "video", "position"):
            st.session_state[f"observation_{field}_{token}"] = ""
        st.session_state[f"observation_date_{token}"] = local_today()
    history = observation_history(candidate)
    compatible = any(player_key(p, metadata) == candidate["key"] for _, p in profiles.iterrows())
    snapshot = metadata.get("snapshot", metadata.get("revision", "")) if compatible else ""
    with st.expander(f"Observaciones de campo · {len(history)} entradas", expanded=False):
        st.caption(
            "Cada entrada se añade al historial del candidato. La fecha indica cuándo "
            "lo observaste; la fecha de registro se conserva aparte."
        )
        with st.form(f"observation_form_{token}"):
            observed_on = st.date_input(
                "Fecha de observación",
                value=local_today(),
                max_value=local_today(),
                key=f"observation_date_{token}",
            )
            context = st.text_input(
                "Partido o contexto observado",
                max_chars=200,
                key=f"observation_context_{token}",
                placeholder="Partido, rival, competición o sesión de vídeo",
            )
            left, right = st.columns(2)
            with left:
                strengths = st.text_area(
                    "Fortalezas observadas", max_chars=4000, key=f"observation_strengths_{token}"
                )
            with right:
                doubts = st.text_area(
                    "Dudas por contrastar", max_chars=4000, key=f"observation_doubts_{token}"
                )
            next_step = st.text_area(
                "Qué mirar en la próxima observación",
                max_chars=2000,
                key=f"observation_next_{token}",
            )
            url = st.text_input(
                "Enlace al vídeo (opcional)", max_chars=2000, key=f"observation_video_{token}"
            )
            position = st.text_input(
                "Posición del vídeo (mm:ss o hh:mm:ss, opcional)",
                max_chars=12,
                key=f"observation_position_{token}",
            )
            st.caption(
                "El enlace se guarda tal como lo introduces; la posición queda anotada al lado."
            )
            if st.form_submit_button(
                "Añadir observación al historial", key=f"add_observation_{token}"
            ):
                try:
                    append_observation(
                        path,
                        project["id"],
                        candidate["key"],
                        {
                            "observed_on": observed_on.isoformat(),
                            "context": context,
                            "strengths": strengths,
                            "doubts": doubts,
                            "next_step": next_step,
                            "video_url": url,
                            "video_position": position,
                        },
                        statistics_snapshot=snapshot,
                    )
                    st.session_state["project_notice"] = (
                        "Observación añadida. El historial anterior se conserva."
                    )
                    st.session_state[f"observation_reset_{token}"] = True
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
        if not history:
            st.info("Todavía no hay observaciones de campo para este candidato.")
        for entry in history:
            st.markdown(f"**Observado: {local_date(entry['observed_on'])}**")
            st.text(entry["context"])
            for title, field in (
                ("Fortalezas", "strengths"),
                ("Dudas", "doubts"),
                ("Próxima observación", "next_step"),
            ):
                st.write(f"**{title}**")
                st.text(entry.get(field) or "Sin anotar.")
            try:
                url = video_url(entry.get("video_url", ""))
            except ValueError:
                url = ""
            if url:
                st.link_button("Abrir vídeo de la observación", url)
                if entry.get("video_seconds") is not None:
                    st.caption(f"Posición anotada: {video_position(entry['video_seconds'])}")
            st.caption(f"Registrado: {local_date(entry['created_at'])}")
            st.divider()

    with st.expander("Informe individual · conclusión y firma", expanded=False):
        assessment = candidate.get("assessment", {})
        with st.form(f"assessment_form_{token}"):
            verdict = st.selectbox(
                "Conclusión del informe",
                VERDICTS,
                index=VERDICTS.index(assessment.get("verdict", VERDICTS[0])),
                key=f"assessment_verdict_{token}",
            )
            rationale = st.text_area(
                "Motivos de tu conclusión",
                value=assessment.get("rationale", ""),
                max_chars=6000,
                key=f"assessment_rationale_{token}",
            )
            author = st.text_input(
                "Firma del informe (nombre o alias, opcional)",
                value=assessment.get("author", ""),
                max_chars=100,
                key=f"assessment_author_{token}",
            )
            if st.form_submit_button(
                "Guardar conclusión del informe", key=f"save_assessment_{token}"
            ):
                try:
                    save_assessment(
                        path, project["id"], candidate["key"], verdict, rationale, author
                    )
                    st.session_state["project_notice"] = "Conclusión del informe guardada."
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
        st.caption(
            "La ficha descargable usa la conclusión que has guardado y el historial registrado."
        )
        minimum = st.number_input(
            "Mínimo de minutos para percentiles de la ficha",
            0,
            5000,
            450,
            50,
            key=f"dossier_minimum_{token}",
        )
        report = individual_dossier(profiles, metadata, project, candidate, minimum)
        if report["statistics"] is None:
            st.info(report["statistics_note"])
        else:
            st.caption(report["statistics_note"])
        st.download_button(
            "Descargar ficha individual HTML",
            dossier_html(report),
            file_name="scoutfit-ficha-individual.html",
            mime="text/html",
            key=f"dossier_html_{token}",
        )
        st.download_button(
            "Descargar ficha individual JSON",
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
            file_name="scoutfit-ficha-individual.json",
            mime="application/json",
            key=f"dossier_json_{token}",
        )
        st.caption(
            "El HTML es autónomo: puedes abrirlo sin conexión e imprimirlo o guardarlo "
            "como PDF desde el navegador. La descarga incluye las observaciones "
            "y la firma que hayas añadido."
        )
