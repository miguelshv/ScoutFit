"""Comparable raw metrics, within-position percentiles and a self-contained report."""

from html import escape

import numpy as np
import pandas as pd


def compare_players(
    profiles: pd.DataFrame, ids: list[str], features: dict, min_minutes: float = 450
) -> pd.DataFrame:
    if not 1 <= len(ids) <= 3 or len(set(ids)) != len(ids):
        raise ValueError("Selecciona entre uno y tres jugadores distintos")
    selected = profiles.loc[profiles["profile_id"].isin(ids)]
    if len(selected) != len(ids):
        raise ValueError("Algún jugador ya no está disponible")
    grouping = ["competition_id", "season_id", "role"]
    if "provider" in profiles:
        grouping.append("provider")
    if any(selected[column].nunique(dropna=False) != 1 for column in grouping):
        raise ValueError("La comparativa requiere la misma posición, liga, temporada y fuente")
    if (selected["minutes"] < min_minutes).any():
        raise ValueError("Un jugador no alcanza el mínimo de minutos")
    mask = profiles["minutes"] >= min_minutes
    for column in grouping:
        mask &= profiles[column] == selected.iloc[0][column]
    cohort = profiles.loc[mask].set_index("profile_id")
    values = cohort[list(features)]
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("No se calculan percentiles sobre métricas incompletas")
    percentiles = values.rank(method="average", pct=True) * 100
    rows = []
    for pid in ids:
        player = cohort.loc[pid]
        for feature, label in features.items():
            rows.append(
                {
                    "profile_id": pid,
                    "player_name": player["player_name"],
                    "team_name": player["team_name"],
                    "player_label": f"{player['player_name']} · {player['team_name']}",
                    "feature": feature,
                    "metric": label,
                    "value": player[feature],
                    "percentile": percentiles.loc[pid, feature],
                    "cohort_size": len(cohort),
                }
            )
    return pd.DataFrame(rows)


def html_report(
    profiles: pd.DataFrame,
    ids: list[str],
    comparison: pd.DataFrame,
    metadata: dict,
    min_minutes: float,
    note: str = "",
) -> str:
    if len(ids) < 2:
        raise ValueError("El informe comparativo requiere dos o tres jugadores")
    selected = profiles.set_index("profile_id").loc[ids]
    cards = []
    for index, (_, player) in enumerate(selected.iterrows()):
        style = player.get("inferred_role", "")
        style = style if isinstance(style, str) and style else "No asignado"
        cards.append(
            f"<article><p>{'Referencia' if index == 0 else 'Candidato'}</p>"
            f"<h2>{escape(str(player['player_name']))}</h2>"
            f"<p>{escape(str(player['team_name']))} · {escape(str(player['role']))}</p>"
            f"<p>{float(player['minutes']):.0f} minutos · "
            f"Perfil inferido: {escape(style)}</p></article>"
        )
    formatted = comparison.copy()
    formatted["cell"] = formatted.apply(
        lambda r: f"{r['value']:.2f} · P{r['percentile']:.0f}", axis=1
    )
    table = formatted.pivot(index="metric", columns="player_label", values="cell")
    table = table.reindex(
        index=comparison["metric"].drop_duplicates(),
        columns=comparison["player_label"].drop_duplicates(),
    )
    table = table.rename_axis(index="Métrica", columns=None).reset_index()
    highlights = []
    for pid in ids:
        rows = comparison.loc[comparison["profile_id"] == pid].sort_values(
            "percentile", ascending=False
        )
        labels = ", ".join(
            f"{r['metric']} (P{r['percentile']:.0f})" for _, r in rows.head(3).iterrows()
        )
        highlights.append(
            f"<li><strong>{escape(str(rows.iloc[0]['player_name']))}:</strong> "
            f"{escape(labels)}</li>"
        )
    cohort_size = int(comparison.iloc[0]["cohort_size"])
    return f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ScoutFit · Informe comparativo</title>
<style>body{{font:16px system-ui,sans-serif;color:#282d27;background:#f4f0e7;
max-width:1120px;margin:40px auto;padding:0 24px;line-height:1.6}}
h1{{font:normal 36px Georgia,serif;color:#282d27;
border-bottom:2px solid #282d27;padding-bottom:16px}}
h2{{font-family:Georgia,serif;font-weight:400;letter-spacing:-.025em;line-height:1.2}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}
article{{flex:1;min-width:200px;padding:22px;background:#fcfaf5;border:1px solid #d2cec2;
border-radius:2px;border-top:2px solid #ac4b32}}article>p:first-child{{color:#ac4b32;
font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:700}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
th,td{{padding:11px;border-bottom:1px solid #d2cec2;text-align:left}}
th{{background:#eae5d9;color:#345548}}.note{{white-space:pre-wrap;background:#fff;
padding:20px;border:1px solid #d2cec2;border-radius:2px}}
footer{{font-size:12px;color:#62665d;border-top:1px solid #d2cec2;padding-top:18px}}
@media print{{body{{margin:0;font-size:11pt;background:#fff}}article, tr{{break-inside:avoid}}}}
</style>
<h1>ScoutFit · Informe comparativo</h1>
<p>{escape(str(metadata.get("competition", "")))} · {escape(str(metadata.get("season", "")))}</p>
<p>Fuente: {escape(str(metadata.get("source", "")))} ·
Consulta UTC: {escape(str(metadata.get("downloaded_at", "")))}</p>
<div class="cards">{"".join(cards)}</div><h2>Métricas y percentiles</h2>
<p>Valor bruto y percentil dentro de {cohort_size} jugadores de la misma posición,
fuente, liga y temporada,
con al menos {min_minutes:g} minutos. P alto describe estilo o volumen; no implica mayor calidad.
</p>
{table.to_html(index=False, escape=True, border=0)}<h2>Rasgos relativamente altos</h2>
<ul>{"".join(highlights)}</ul>
<h2>Notas del análisis</h2><p class="note">{escape(note or "Sin notas añadidas.")}</p>
<footer><p>Los perfiles son inferidos mediante reglas estadísticas, no posiciones tácticas
confirmadas.
Sin ajuste por posesión, rival o dificultad. El equipo es el de la plantilla consultada;
las estadísticas
pueden incluir un club anterior en la temporada. Este informe no predice el éxito de un fichaje.</p>
<p>Snapshot: {escape(str(metadata.get("snapshot", metadata.get("revision", ""))))}</p>
</footer></html>"""
