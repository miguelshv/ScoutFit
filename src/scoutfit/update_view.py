"""User-triggered update and a persistent, explicitly scoped change summary."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from scoutfit.datasets import active_directory
from scoutfit.updates import UpdateError, update_dataset

PHASES = {
    "competition": (0.01, 0.03, "Comprobando competición y temporada"),
    "rosters": (0.04, 0.16, "Consultando plantillas"),
    "statistics": (0.20, 0.64, "Consultando estadísticas"),
    "profiles": (0.84, 0.10, "Construyendo perfiles"),
    "validation": (0.95, 0.01, "Validando cobertura e integridad"),
    "publishing": (0.98, 0.01, "Activando la consulta validada"),
}


def local_date(value):
    if not value:
        return "Sin consulta anterior"
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(ZoneInfo("Europe/Madrid"))
        .strftime("%d/%m/%Y · %H:%M")
    )


def preserve_search(state, before, before_meta, after, after_meta):
    """Keep the same real player on roster moves; never touch project/favorite records."""
    same_source = before_meta.get("provider") == after_meta.get("provider")
    if not same_source:
        for key in list(state):
            if key.startswith(("weight_", "target_")):
                del state[key]
        state.update(
            priority="Equilibrada",
            custom_weights=False,
            reference_team="Todos",
            reference_position="Todas",
            player_search="",
        )
    if before is None:
        return
    selected = before.loc[before["profile_id"] == state.get("reference_player")]
    if not same_source or len(selected) != 1:
        return
    choices = after.loc[after["player_id"] == selected.iloc[0]["player_id"]]
    if len(choices) == 1:
        player = choices.iloc[0]
        state["reference_player"] = player["profile_id"]
        if state.get("reference_team", "Todos") not in ("Todos", player["team_name"]):
            state["reference_team"] = "Todos"
        if state.get("reference_position", "Todas") not in ("Todas", player["role"]):
            state["reference_position"] = "Todas"
        state["player_search"] = ""


def render_update_panel(root, profiles=None, metadata=None):
    metadata = metadata or {}
    with st.expander("Actualizar datos y ver cambios", expanded=False):
        st.caption(
            "Consulta las plantillas y estadísticas actuales de LaLiga masculina en ESPN. "
            "La descarga puede tardar unos minutos. Los proyectos, notas y favoritos se conservan."
        )
        if st.button("Actualizar desde ESPN", key="update_data", type="primary"):
            with st.status("Preparando actualización…", expanded=True) as status:
                bar = st.progress(0)
                message = st.empty()

                def progress(phase, done, total):
                    start, span, label = PHASES[phase]
                    fraction = done / total if total else 0
                    bar.progress(min(start + span * fraction, 0.99))
                    message.write(f"{label} · {done}/{total}" if total > 1 else label)

                try:
                    new_profiles, new_metadata, _ = update_dataset(root, progress=progress)
                    preserve_search(
                        st.session_state, profiles, metadata, new_profiles, new_metadata
                    )
                    bar.progress(1.0)
                    status.update(label="Consulta validada y activada", state="complete")
                    st.rerun()
                except (UpdateError, OSError) as exc:
                    status.update(label="No se han activado datos nuevos", state="error")
                    st.error(f"No se pudo actualizar: {exc}")
                    st.caption(
                        "La última consulta válida sigue activa."
                        if metadata
                        else "Puedes volver a intentarlo. No se ha activado una descarga parcial."
                    )
        audit_path = root / "data/updates/last_attempt.json"
        try:
            audit = (
                json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
            )
            report_path = active_directory(root / "data/processed") / "update_report.json"
            report = (
                json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            )
        except (OSError, ValueError, KeyError):
            st.caption("No se ha podido leer el historial de actualizaciones.")
            return
        if audit.get("status") == "failed":
            st.warning(
                "El último intento falló. No se sustituyó la consulta activa por datos sin validar."
            )
            st.caption(f"Intento: {local_date(audit.get('completed_at'))} (Madrid)")
            st.code(audit.get("error", "Error de descarga o validación"), language=None)
        if report:
            render_change_summary(report)


def render_change_summary(report):
    st.markdown("**Última actualización completada**")
    st.caption(
        f"{local_date(report['after_consulted_at'])} (Madrid) · {report['season']} · "
        f"{report['profiles']} perfiles completos · {report['team_count']} clubes · "
        f"{report['excluded_profiles']} registros excluidos por cobertura o calidad."
    )
    if not report["comparable"]:
        st.info(report["comparison_note"])
    else:
        st.caption(
            f"Comparada con la consulta del {local_date(report['before_consulted_at'])} (Madrid)."
        )
        with st.container(key="update_summary"):
            columns = st.columns(4)
            for column, label, key in zip(
                columns,
                (
                    "Altas de perfiles",
                    "Bajas de perfiles",
                    "Cambios de equipo",
                    "Estadísticas modificadas",
                ),
                ("new_profiles", "removed_profiles", "team_changes", "statistics_changes"),
            ):
                column.metric(label, len(report[key]))
        if not any(
            report[k]
            for k in (
                "new_profiles",
                "removed_profiles",
                "team_changes",
                "statistics_changes",
                "identity_changes",
            )
        ):
            st.success(
                "Consulta completada sin cambios en los equipos, perfiles y métricas comparables."
            )
        st.caption(
            "Altas y bajas se refieren a perfiles con estadísticas utilizables, no a fichajes "
            "confirmados. Los cambios de equipo son los publicados en las plantillas de la fuente. "
            "Las variaciones estadísticas pueden incluir nuevos partidos "
            "o correcciones del proveedor."
        )
        tables = [
            ("Perfiles incorporados", "new_profiles"),
            ("Perfiles que ya no están disponibles", "removed_profiles"),
            ("Cambios de equipo en la fuente", "team_changes"),
        ]
        labels = {
            "player_name": "Jugador",
            "team_name": "Equipo",
            "minutes": "Minutos",
            "previous_team": "Equipo anterior",
            "current_team": "Equipo actual",
        }
        for title, key in tables:
            if report[key]:
                st.markdown(f"**{title}**")
                st.dataframe(
                    pd.DataFrame(report[key]).drop(columns="player_id").rename(columns=labels),
                    hide_index=True,
                    width="stretch",
                )
        if report["statistics_changes"]:
            rows = [
                {
                    "Jugador": r["player_name"],
                    "Equipo": r["team_name"],
                    "Minutos anteriores": r["previous_minutes"],
                    "Minutos actuales": r["minutes"],
                    "Δ minutos": r["minutes_delta"],
                    "Campos modificados": len(r["changes"]),
                    "Retroceso de minutos o partidos": r["correction"],
                }
                for r in report["statistics_changes"]
            ]
            st.markdown("**Estadísticas modificadas**")
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if report["identity_changes"]:
            st.caption(
                f"También hay {len(report['identity_changes'])} ajustes de nombre, "
                "posición o denominación de club."
            )
    st.download_button(
        "Descargar resumen de actualización JSON",
        json.dumps(report, ensure_ascii=False, indent=2),
        file_name="scoutfit-actualizacion.json",
        mime="application/json",
        key="update_report_download",
    )
