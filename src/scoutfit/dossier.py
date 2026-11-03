"""Self-contained individual reports: source statistics and human notes stay distinct."""

from datetime import datetime
from html import escape
from importlib.resources import files
from string import Template
from zoneinfo import ZoneInfo

import numpy as np

from scoutfit.comparison import compare_players
from scoutfit.datasets import metric_definitions
from scoutfit.observations import observation_history, video_position, video_url
from scoutfit.projects import now
from scoutfit.workspace import player_key


def individual_dossier(profiles, metadata, project, candidate, minimum=450):
    if (
        isinstance(minimum, bool)
        or not isinstance(minimum, (int, float))
        or not np.isfinite(minimum)
        or minimum < 0
    ):
        raise ValueError("El mínimo de minutos de la ficha debe ser finito y no negativo.")
    matches = [p for _, p in profiles.iterrows() if player_key(p, metadata) == candidate["key"]]
    player = matches[0] if len(matches) == 1 else None
    report = {
        "generated_at": now(),
        "project_name": project["name"],
        "player_name": str(player["player_name"])
        if player is not None
        else candidate["player_name"],
        "player_key": candidate["key"],
        "team_at_save": candidate["team_at_save"],
        "saved_snapshot": candidate["snapshot"],
        "status": candidate["status"],
        "general_note": candidate.get("note", ""),
        "observations": observation_history(candidate),
        "assessment": candidate.get("assessment", {}),
        "statistics": None,
        "statistics_note": (
            "No hay un perfil único de esta fuente, liga y temporada en la consulta activa."
        ),
    }
    if player is None:
        return report
    features = metric_definitions(metadata)
    percentiles = {}
    cohort_size = None
    note = "Valores de temporada y percentiles dentro de su posición."
    if player["minutes"] < minimum:
        note = (
            "El jugador no alcanza el mínimo de minutos elegido. "
            "Se muestran valores sin percentiles."
        )
    else:
        try:
            comparison = compare_players(profiles, [player["profile_id"]], features, minimum)
            percentiles = comparison.set_index("feature")["percentile"].to_dict()
            cohort_size = int(comparison.iloc[0]["cohort_size"])
        except ValueError as exc:
            note = f"Percentiles no calculables: {exc}"
    metrics = []
    for feature, label in features.items():
        value = float(player.get(feature, np.nan))
        metrics.append(
            {
                "metric": label,
                "feature": feature,
                "value": value if np.isfinite(value) else None,
                "percentile": float(percentiles[feature]) if feature in percentiles else None,
            }
        )
    report["statistics"] = {
        "source": metadata.get("source", "StatsBomb Open Data"),
        "competition": metadata.get("competition", ""),
        "season": metadata.get("season", ""),
        "snapshot": metadata.get("snapshot", metadata.get("revision", "historical")),
        "consulted_at": metadata["downloaded_at"],
        "team_name": str(player["team_name"]),
        "role": str(player["role"]),
        "inferred_role": str(player.get("inferred_role") or "Sin asignar"),
        "minutes": float(player["minutes"]),
        "matches": int(player["matches"]),
        "minimum_minutes": float(minimum),
        "cohort_size": cohort_size,
        "metrics": metrics,
    }
    report["statistics_note"] = note
    return report


def local_date(value):
    if not value:
        return "Sin fecha"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ZoneInfo("Europe/Madrid"))
            return parsed.strftime("%d/%m/%Y · %H:%M (Madrid)")
        return parsed.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(value)


def dossier_html(report):
    def text(value):
        return escape(str(value), quote=True)

    def paragraph(value, empty="Sin anotar."):
        return f'<p class="prose">{text(value or empty)}</p>'

    assessment = report["assessment"]
    author = assessment.get("author", "")
    verdict = assessment.get("verdict", "Sin conclusión")
    rationale = assessment.get("rationale", "")
    stats = report["statistics"]
    statistics = '<p class="notice">No hay estadísticas actuales comparables para esta ficha.</p>'
    if stats:
        rows = []
        for metric in stats["metrics"]:
            value = f"{metric['value']:.2f}" if metric["value"] is not None else "No disponible"
            percentile = metric["percentile"]
            mark = (
                '<span class="track">'
                f'<i style="width:{max(0, min(100, percentile)):.2f}%"></i></span>'
                f"<span>P{percentile:.0f}</span>"
                if percentile is not None
                else "Sin percentil"
            )
            rows.append(
                f'<tr><th scope="row">{text(metric["metric"])}</th><td>{value}</td>'
                f'<td class="percentile">{mark}</td></tr>'
            )
        cohort = (
            f"Población: {stats['cohort_size']} perfiles de su posición, "
            f"mínimo {stats['minimum_minutes']:g} minutos."
            if stats["cohort_size"] is not None
            else "No se han calculado percentiles."
        )
        statistics = (
            '<div class="facts"><span>Equipo en consulta'
            f"<strong>{text(stats['team_name'])}</strong></span>"
            f"<span>Posición de la fuente<strong>{text(stats['role'])}</strong></span>"
            f"<span>Participación<strong>{stats['minutes']:.0f} min · "
            f"{stats['matches']} partidos</strong></span></div>"
            f'<p class="caption">{text(stats["source"])} · {text(stats["competition"])} · '
            f"{text(stats['season'])}<br>Consulta: {text(local_date(stats['consulted_at']))}</p>"
            f"<p>Perfil inferido: {text(stats['inferred_role'])}.</p>"
            f'<p class="caption">{text(cohort)} {text(report["statistics_note"])}</p>'
            "<table><thead><tr><th>Métrica</th><th>Valor</th>"
            "<th>Percentil en la posición</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            '<p class="caption">Un percentil alto describe estilo o volumen; '
            "no equivale a mayor calidad.</p>"
        )
    entries = []
    for entry in report["observations"]:
        link = ""
        try:
            url = video_url(entry.get("video_url", ""))
        except ValueError:
            url = ""
        if url:
            position = video_position(entry.get("video_seconds"))
            link = (
                f'<p><a href="{text(url)}" target="_blank" '
                'rel="noopener noreferrer">Abrir vídeo ↗</a>'
            )
            if position:
                link += f" · Posición anotada: {text(position)}"
            link += "</p>"
        entries.append(
            f'<article><p class="index">{text(local_date(entry["observed_on"]))} / OBSERVACIÓN</p>'
            f'<h3>{text(entry["context"])}</h3><div class="two-columns"><div><h4>Fortalezas</h4>'
            f"{paragraph(entry['strengths'])}</div><div><h4>Dudas</h4>{paragraph(entry['doubts'])}</div></div>"
            f"<h4>Próxima observación</h4>{paragraph(entry['next_step'])}{link}"
            f'<p class="caption">Registrada: {text(local_date(entry["created_at"]))}'
            " · Base estadística al registrar: "
            f"{text(entry.get('statistics_snapshot') or 'No disponible')}</p></article>"
        )
    observations = (
        "".join(entries) or '<p class="notice">Todavía no hay observaciones registradas.</p>'
    )
    signature = f"Firma: {text(author)}" if author else "Firma no añadida"
    template = files("scoutfit").joinpath("templates/individual.html").read_text(encoding="utf-8")
    return Template(template).substitute(
        player_name=text(report["player_name"]),
        project_name=text(report["project_name"]),
        team_at_save=text(report["team_at_save"]),
        status=text(report["status"]),
        generated_at=text(local_date(report["generated_at"])),
        verdict=text(verdict),
        rationale=paragraph(rationale, "Todavía no se ha añadido una conclusión justificada."),
        signature=signature,
        assessment_date=text(local_date(assessment.get("updated_at")))
        if assessment
        else "Pendiente de valoración humana.",
        statistics=statistics,
        observation_count=len(report["observations"]),
        observations=observations,
        general_note=paragraph(report["general_note"], "Sin nota general."),
        player_key=text(report["player_key"]),
        saved_snapshot=text(report["saved_snapshot"]),
        statistics_snapshot=text(stats["snapshot"]) if stats else "No disponible",
    )
