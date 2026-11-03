"""Guided human review, independent of the active recommendation's filters."""

import json

import pandas as pd
import streamlit as st

from scoutfit.benchmark_review import campaign, campaign_judgments, campaign_report, judgment_digest
from scoutfit.workspace import load_records, save_judgment


def render_benchmark(root, profiles, metadata, features):
    if not metadata.get("snapshot"):
        return
    with st.expander("Evaluación guiada · 20 referencias", expanded=False):
        st.caption(
            "Revisa parejas sin ver su posición en el ranking. La campaña fija la consulta, "
            "450 minutos y pesos equilibrados; tus filtros de búsqueda no la modifican."
        )
        if st.button("Preparar o continuar evaluación", key="start_campaign"):
            st.session_state["campaign_snapshot"] = metadata["snapshot"]
        if st.session_state.get("campaign_snapshot") != metadata["snapshot"]:
            st.info("Prepara la campaña para revisar las 20 referencias de esta consulta.")
            return
        try:
            pairs, config = campaign(root, profiles, metadata, features)
            path = root / "data/user/judgments.json"
            judgments = load_records(path)
            scoped = campaign_judgments(pairs, judgments, metadata["snapshot"])
        except (OSError, ValueError, KeyError) as exc:
            st.error(str(exc))
            return
        reviewed = {(r["reference_id"], r["candidate_id"]) for r in scoped}
        st.progress(
            len(reviewed) / len(pairs), text=f"{len(reviewed)} de {len(pairs)} parejas revisadas"
        )
        st.caption(
            f"{config['references']} referencias · consulta {config['snapshot']} · "
            "0 = inadecuado; 1 = parecido parcial; 2 = buen sustituto de estilo. "
            "Una valoración requiere justificación y revisor. Puedes dejar una pareja sin valorar."
        )
        pending = pairs.loc[
            [(a, b) not in reviewed for a, b in zip(pairs.reference_id, pairs.candidate_id)]
        ]
        references = pending.reference_id.unique().tolist()
        if references:
            names = profiles.set_index("profile_id").player_name.to_dict()
            key = f"campaign_ref_{config['snapshot']}"
            if st.session_state.get(key) not in references:
                st.session_state[key] = references[0]
            reference = st.selectbox(
                "Referencia pendiente", references, format_func=lambda x: names[x], key=key
            )
            candidates = pending.loc[pending.reference_id.eq(reference), "candidate_id"].tolist()
            candidate = st.selectbox(
                "Pareja pendiente",
                candidates,
                format_func=lambda x: names[x],
                key=f"campaign_candidate_{config['snapshot']}_{reference}",
            )
            players = profiles.set_index("profile_id").loc[[reference, candidate]]
            st.write(f"**{names[reference]} ↔ {names[candidate]}**")
            st.caption(
                "Contrasta funciones, uso del balón y diferencias; puedes consultar vídeo externo."
            )
            table = players[["team_name", "minutes", *features]].T
            table.columns = [names[reference], names[candidate]]
            st.dataframe(
                table.rename(index={"team_name": "Equipo", "minutes": "Minutos", **features}),
                width="stretch",
            )
            with st.form(f"campaign_form_{config['snapshot']}_{reference}_{candidate}"):
                relevance = st.selectbox("Valoración humana", ["Sin valorar", "0", "1", "2"])
                reviewer = st.text_input("Nombre o alias del revisor", max_chars=100)
                note = st.text_area("Evidencias y justificación", max_chars=4000)
                if st.form_submit_button("Guardar y seguir con pendientes"):
                    if relevance == "Sin valorar" or not reviewer.strip() or not note.strip():
                        st.warning("Completa valoración, revisor y justificación.")
                    else:
                        save_judgment(
                            path,
                            {
                                "snapshot": config["snapshot"],
                                "reference_id": reference,
                                "candidate_id": candidate,
                                "relevance": int(relevance),
                                "note": note.strip(),
                                "reviewer": reviewer.strip(),
                            },
                        )
                        st.rerun()
        else:
            st.success("Todas las parejas de esta campaña tienen revisión humana.")
        st.download_button(
            "Descargar campaña sin valorar CSV",
            pairs.to_csv(index=False).encode("utf-8"),
            file_name="scoutfit-campana.csv",
            mime="text/csv",
        )
        if st.button("Generar informe de evidencia", key="campaign_report"):
            report = campaign_report(profiles, features, pairs, config, load_records(path))
            st.session_state["campaign_evidence"] = report
        report = st.session_state.get("campaign_evidence")
        if report and report["snapshot"] == config["snapshot"]:
            if report["review_digest"] != judgment_digest(scoped):
                st.info("Las valoraciones han cambiado. Genera de nuevo el informe.")
            else:
                st.write(f"**Estado: {report['status']}**")
                if report["summary"]:
                    st.dataframe(pd.DataFrame(report["summary"]), hide_index=True, width="stretch")
                else:
                    st.info(
                        "Pendiente de revisión humana suficiente; "
                        "no hay cifras de calidad publicables."
                    )
                st.caption(
                    "Resultados solo sobre el conjunto revisado. El informe omite notas y alias."
                )
                st.download_button(
                    "Descargar informe de evidencia JSON",
                    json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
                    file_name="scoutfit-evidencia.json",
                    mime="application/json",
                )
