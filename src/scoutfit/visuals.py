"""Shared visual language. Every provider/user string is escaped before HTML rendering."""

from html import escape

import pandas as pd
import streamlit as st

from scoutfit.biographies import media_url

COLORS = ["#345548", "#ac4b32", "#5c6e78"]

CSS = """
<style>
:root { --sf-ink:#282d27; --sf-muted:#62665d; --sf-green:#345548;
 --sf-red:#ac4b32; --sf-paper:#f4f0e7; --sf-line:#d2cec2; }
.stApp { background:var(--sf-paper); }
.stMainBlockContainer { max-width:1370px; padding:3.6rem 3rem 3rem; }
[data-testid="stHeader"] { background:rgba(244,240,231,.96); }
h1,h2,h3 { color:var(--sf-ink); font-family:Georgia,'Times New Roman',serif !important;
 font-weight:400 !important; letter-spacing:-.025em; }
h2 { font-size:1.65rem !important; } h3 { font-size:1.25rem !important; }
[data-testid="stCaptionContainer"] { color:var(--sf-muted); }
[data-testid="stWidgetLabel"] p { font-size:.8rem; font-weight:600; }
[data-testid="stSelectbox"] [role="group"], [data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"] { background:#fcfaf5; border-radius:3px; }
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
 border-radius:3px; font-size:.8rem; font-weight:500; min-height:2.35rem;
}
button:focus-visible, a:focus-visible { outline:3px solid var(--sf-red) !important; }
[data-testid="stMetric"] { padding:12px 0; border:0; border-top:1px solid var(--sf-line);
 border-radius:0; background:transparent; }
[data-testid="stMetricLabel"] { color:var(--sf-muted); font-size:.75rem; }
[data-testid="stMetricValue"] { color:var(--sf-ink); font-family:Georgia,serif;
 font-weight:400; font-variant-numeric:tabular-nums; }
[role="tablist"] { gap:20px !important; border-bottom:1px solid var(--sf-line);
 padding:0; overflow-x:auto; flex-wrap:nowrap; }
[data-testid="stTab"] { border-radius:0; padding:10px 0 !important; height:44px;
 white-space:nowrap; color:var(--sf-muted); }
[data-testid="stTab"][aria-selected="true"] { color:var(--sf-red); font-weight:650; }
[data-testid="stTab"] .react-aria-SelectionIndicator { background:var(--sf-red); }
[data-testid="stExpander"] { border-radius:3px; background:transparent; }
[data-testid="stExpander"] details { border-color:var(--sf-line); border-radius:3px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:3px; }
.st-key-search_panel, .st-key-target_search_panel {
 border:0; border-top:2px solid var(--sf-ink); border-bottom:1px solid var(--sf-line);
 background:#f9f6ef; border-radius:0; }
.st-key-search_panel h3 { margin-bottom:0; }
.sf-hero { border-top:3px solid var(--sf-ink); margin-bottom:0; color:var(--sf-ink); }
.sf-masthead { display:flex; align-items:center; justify-content:space-between;
 gap:20px; padding:15px 0; border-bottom:1px solid var(--sf-line); }
.sf-brand { display:flex; align-items:center; gap:10px; font-family:Georgia,serif;
 font-size:30px; letter-spacing:-.055em; }
.sf-mark { border:1px solid var(--sf-red); color:var(--sf-red); width:27px; height:29px;
 display:grid; place-items:center; font-family:Georgia,serif; font-size:17px; font-style:italic; }
.sf-edition { font:10px 'Courier New',monospace; letter-spacing:.09em;
 color:var(--sf-muted); text-transform:uppercase; text-align:right; }
.sf-lead { display:grid; grid-template-columns:1fr 300px; gap:45px; padding:25px 0 22px; }
.sf-overline { font:10px 'Courier New',monospace; letter-spacing:.1em;
 text-transform:uppercase; color:var(--sf-red); }
.sf-hero h1 { color:var(--sf-ink); font-size:clamp(32px,3.7vw,48px);
 line-height:1.13; margin:8px 0 11px; padding:0; }
.sf-hero h1 em { color:var(--sf-red); font-weight:400; }
.sf-hero p { color:var(--sf-muted); max-width:570px; font-size:13px; line-height:1.75; margin:0; }
.sf-field-note { border-left:1px solid var(--sf-line); padding-left:24px; position:relative; }
.sf-field-note p { font-family:Georgia,serif; font-size:18px; font-style:italic;
 color:var(--sf-green); line-height:1.45; margin-top:8px; }
.sf-field-note small { display:block; color:var(--sf-muted); font-size:11px; margin-top:9px; }
.sf-field-sketch { width:80px; height:35px; margin-top:8px; color:var(--sf-red); }
.sf-hero-meta { display:flex; flex-wrap:wrap; gap:0; border-top:1px solid var(--sf-line);
 border-bottom:1px solid var(--sf-ink); font:11px 'Courier New',monospace; }
.sf-hero-meta span { padding:10px 18px 10px 0; margin-right:18px; }
.sf-hero-meta span+span { border-left:1px solid var(--sf-line); padding-left:18px; }
.sf-hero-meta b { font-weight:700; }
.sf-section { margin:12px 0 8px; }
.sf-section .sf-overline { margin-bottom:5px; }
.sf-section h2 { padding:0; margin:0; }
.sf-section p { color:var(--sf-muted); font-size:13px; margin:5px 0 0; }
.sf-section p:empty { display:none; }
.sf-reference { display:grid; grid-template-columns:1.15fr 1fr; gap:24px 35px;
 padding:23px 0; border-top:1px solid var(--sf-ink); border-bottom:1px solid var(--sf-line);
 margin:8px 0 14px; }
.sf-identity { display:flex; align-items:center; gap:18px; }
.sf-identity > div:last-child { min-width:0; }
.sf-avatar { display:grid; place-items:center; flex-shrink:0; width:70px; height:86px;
 border:1px solid var(--sf-line); background:#e5e6db; color:var(--sf-green);
 font:32px Georgia,serif; position:relative; overflow:hidden; }
.sf-avatar img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
.sf-club-logo { width:19px; height:19px; object-fit:contain;
 vertical-align:middle; margin-right:5px; }
.sf-bio { grid-column:1 / -1; border-top:1px dashed var(--sf-line); padding-top:13px;
 display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }
.sf-bio small { display:block; color:var(--sf-muted); font:10px 'Courier New',monospace; }
.sf-bio strong { display:block; margin-top:5px; font-size:13px; font-weight:500; }
.sf-bio-source { grid-column:1 / -1; color:var(--sf-muted); font-size:10px; }
.sf-reference h2 { font-size:32px !important; margin:5px 0 6px; padding:0; }
.sf-reference h2, .sf-candidate h3 { overflow-wrap:anywhere; }
.sf-reference p { font-size:12px; color:var(--sf-muted); margin:4px 0; }
.sf-tag { display:inline-block; border-bottom:1px solid #b8c2b1; color:var(--sf-green);
 padding:4px 0; font-size:11px; margin:6px 12px 0 0; }
.sf-tag.neutral { color:var(--sf-muted); border-color:var(--sf-line); }
.sf-highlights { display:grid; align-content:center; gap:9px; }
.sf-percentile { display:grid; grid-template-columns:minmax(0,1fr) 80px 30px;
 align-items:center; gap:10px; font-size:11px; color:var(--sf-ink); }
.sf-percentile strong { font:11px 'Courier New',monospace; }
.sf-track { height:3px; background:#deded1; overflow:hidden; }
.sf-track span { display:block; height:100%; background:var(--sf-green); }
.sf-candidate { min-height:145px; padding-top:10px; border-top:2px solid var(--sf-red); }
.sf-candidate .sf-rank { color:var(--sf-red); font:10px 'Courier New',monospace;
 letter-spacing:.07em; }
.sf-candidate h3 { margin:12px 0 5px; padding:0; font-size:25px !important; }
.sf-candidate p { color:var(--sf-muted); font-size:12px; margin:4px 0; }
.sf-distance { display:flex; align-items:baseline; gap:8px; margin-top:14px; }
.sf-distance strong { font:26px Georgia,serif; font-variant-numeric:tabular-nums; }
.sf-distance span { color:var(--sf-muted); font:10px 'Courier New',monospace; }
.st-key-shortlist [data-testid="stVerticalBlockBorderWrapper"] {
 border:0; border-radius:0; background:transparent; padding:0; }
.sf-footer { border-top:2px solid var(--sf-ink); margin-top:32px; padding-top:14px;
 display:flex; justify-content:space-between; gap:15px; color:var(--sf-muted); font-size:11px; }
@media (max-width:700px) {
 .stMainBlockContainer { padding:3.4rem 1rem 3rem; }
 .sf-masthead { align-items:flex-start; gap:10px; }
 .sf-brand { font-size:26px; } .sf-edition { max-width:140px; font-size:9px; line-height:1.6; }
 .sf-lead { grid-template-columns:1fr; gap:17px; padding:20px 0; }
 .sf-hero h1 { font-size:35px; }
 .sf-field-note { border-left:2px solid var(--sf-red); padding-left:13px; }
 .sf-field-note p { font-size:16px; margin-top:0; }
 .sf-field-note .sf-overline, .sf-field-note small, .sf-field-sketch { display:none; }
 .sf-hero-meta { font-size:10px; } .sf-hero-meta span { padding:8px 10px 8px 0; margin-right:10px; }
 .sf-hero-meta span+span { padding-left:10px; }
 .sf-reference { grid-template-columns:1fr; gap:20px; padding:20px 0; }
 .sf-reference h2 { font-size:28px !important; }
 .sf-avatar { width:58px; height:73px; font-size:26px; }
 .sf-percentile { grid-template-columns:minmax(0,1fr) 65px 30px; }
 [data-testid="stTab"] { padding:8px 12px !important; }
 .sf-footer { flex-direction:column; }
 .sf-bio { grid-template-columns:repeat(2,minmax(0,1fr)); }
 .st-key-recommendation_summary [data-testid="stHorizontalBlock"],
 .st-key-update_summary [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
 .st-key-recommendation_summary [data-testid="stColumn"],
 .st-key-update_summary [data-testid="stColumn"] {
   flex:1 1 calc(50% - 1rem) !important; min-width:calc(50% - 1rem) !important;
 }
 .st-key-recommendation_summary [data-testid="stMetric"],
 .st-key-update_summary [data-testid="stMetric"] { padding:12px 0; }
}
</style>
"""


def safe(value):
    return escape(str(value), quote=True)


def inject_style():
    st.html(CSS)


def hero(metadata, profiles):
    st.markdown(
        '<header class="sf-hero"><div class="sf-masthead">'
        '<div class="sf-brand"><span class="sf-mark">S.</span>ScoutFit</div>'
        '<span class="sf-edition">Fútbol masculino / Archivo de temporada</span></div>'
        '<div class="sf-lead"><div><div class="sf-overline">Observación y datos</div>'
        "<h1>Cuaderno <em>de scouting.</em></h1>"
        "<p>Buscar un jugador, contrastar su perfil y dejar anotado a quién volver a mirar.</p>"
        '</div><aside class="sf-field-note"><div class="sf-overline">Al margen</div>'
        "<p>¿Qué hace cuando<br>no tiene el balón?</p>"
        "<small>Una pregunta para llevar al vídeo.</small>"
        '<svg class="sf-field-sketch" viewBox="0 0 100 40" aria-hidden="true">'
        '<g fill="none" stroke="currentColor" stroke-width="1.3">'
        '<path d="M5 35V5h85v30M60 5v12h30M14 29q28 4 54-13m-9-1 9 1-4 8"/>'
        '<circle cx="14" cy="29" r="3"/></g></svg></aside></div>'
        '<div class="sf-hero-meta">'
        f"<span>{safe(metadata['competition'])} · "
        f"{safe(metadata['season'])}</span>"
        f"<span><b>{profiles['team_name'].nunique()}</b> equipos</span>"
        f"<span><b>{len(profiles)}</b> perfiles de campo</span>"
        "</div></header>",
        unsafe_allow_html=True,
    )


def section(kicker, title, description=""):
    st.markdown(
        f'<div class="sf-section"><div class="sf-overline">{safe(kicker)}</div>'
        f"<h2>{safe(title)}</h2><p>{safe(description)}</p></div>",
        unsafe_allow_html=True,
    )


def reference_card(reference, comparison, label="Tu referencia"):
    top = comparison.sort_values("percentile", ascending=False).head(3)
    bars = "".join(
        '<div class="sf-percentile">'
        f'<span>{safe(row["metric"])}</span><div class="sf-track">'
        f'<span style="width:{row["percentile"]:.2f}%"></span></div>'
        f"<strong>P{row['percentile']:.0f}</strong></div>"
        for _, row in top.iterrows()
    )
    initials = "".join(part[0] for part in str(reference["player_name"]).split()[:2])
    style = reference.get("inferred_role", "")
    style = style if isinstance(style, str) and style else "Estilo sin asignar"

    def fact(column, suffix=""):
        value = reference.get(column)
        if value is None or pd.isna(value) or value == "":
            return "No disponible"
        if column in ("bio_age", "bio_height_cm"):
            value = f"{float(value):.0f}"
        return safe(value) + suffix

    photo = media_url(reference.get("bio_photo_url"))
    logo = media_url(reference.get("bio_team_logo_url"))
    image = (
        f'<img src="{safe(photo)}" alt="Fotografía de {safe(reference["player_name"])}" '
        'loading="lazy">'
        if photo
        else ""
    )
    crest = (
        f'<img class="sf-club-logo" src="{safe(logo)}" alt="Escudo" loading="lazy">' if logo else ""
    )
    biography = (
        '<div class="sf-bio">'
        + "".join(
            f"<div><small>{title}</small><strong>{fact(column, suffix)}</strong></div>"
            for title, column, suffix in (
                ("Edad en la consulta", "bio_age", " años"),
                ("Nacionalidad (fuente)", "bio_nationality", ""),
                ("Altura aproximada", "bio_height_cm", " cm"),
                ("Pie dominante", "bio_foot", ""),
            )
        )
        + "</div>"
    )
    source = (
        '<div class="sf-bio-source">Biografía: consulta de ESPN; '
        "altura convertida de pulgadas a cm. Fotografía cuando la fuente la proporciona.</div>"
        if reference.get("bio_consulted_at")
        else ""
    )
    st.markdown(
        '<div class="sf-reference"><div class="sf-identity">'
        f'<div class="sf-avatar">{safe(initials)}{image}</div><div>'
        f'<div class="sf-overline">{safe(label)}</div>'
        f"<h2>{safe(reference['player_name'])}</h2>"
        f"<p>{crest}{safe(reference['team_name'])} · {safe(reference['role'])}</p>"
        f'<span class="sf-tag">Perfil inferido: {safe(style)}</span>'
        f'<span class="sf-tag neutral">{reference["minutes"]:,.0f} min · '
        f"{int(reference['matches'])} partidos</span></div></div>"
        '<div class="sf-highlights"><div class="sf-overline">Sus percentiles más altos</div>'
        f"{bars}<p>Sobre {int(top.iloc[0]['cohort_size'])} perfiles de su posición; "
        f"describen estilo y volumen.</p></div>{biography}{source}</div>",
        unsafe_allow_html=True,
    )


def candidate_card(player, rank):
    st.markdown(
        '<div class="sf-candidate">'
        f'<div class="sf-rank">EN LA LISTA / {rank:02d}</div>'
        f"<h3>{safe(player['player_name'])}</h3><p>{safe(player['team_name'])}</p>"
        f"<p>{safe(player.get('inferred_role', '') or player['role'])}</p>"
        f'<div class="sf-distance"><strong>{player["distance"]:.3f}</strong>'
        f"<span>distancia · {player['minutes']:,.0f} min</span></div></div>",
        unsafe_allow_html=True,
    )


def polish_chart(figure, height=None):
    figure.update_layout(
        font=dict(family="Segoe UI, sans-serif", color="#62665d", size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=COLORS,
        legend=dict(title=None, orientation="h", y=-0.18, x=0),
        margin=dict(l=5, r=15, t=30, b=40),
        **({"height": height} if height else {}),
    )
    figure.update_xaxes(gridcolor="#dedace", zerolinecolor="#b7b6a8")
    figure.update_yaxes(gridcolor="#dedace", zerolinecolor="#b7b6a8")
    return figure


def footer(metadata):
    st.markdown(
        '<div class="sf-footer"><span><b>ScoutFit</b> / Cuaderno de scouting</span>'
        f"<span>Fuente: {safe(metadata.get('source', 'StatsBomb Open Data'))} · "
        "Estilos estadísticos, no predicciones de fichajes.</span></div>",
        unsafe_allow_html=True,
    )
