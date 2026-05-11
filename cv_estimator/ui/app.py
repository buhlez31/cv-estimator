"""Streamlit UI — thin wrapper around `pipeline.analyze_cv`.

Single analysis per run, anchored on either the user-supplied target role
or the auto-detected best-fit role from the CV. Parallel buzzword-baseline
vs hidden-assets-included cards + a market-range chart show where the
candidate's salary point estimate sits within the ISPV P25-P90 band for
the chosen role.
"""

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from cv_estimator.models import CVAnalysis, TrackResult
from cv_estimator.pipeline import analyze_cv

load_dotenv()

st.set_page_config(page_title="CV Estimator", page_icon="📄", layout="wide")
st.title("📄 CV Estimator")
st.caption("AI odhad seniority skóre, tržní mzdy a roadmapy růstu z CV.")

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("Chybí `ANTHROPIC_API_KEY`. Vytvoř `.env` ze `.env.example` a doplň klíč.")
    st.stop()


# -------------------------- Inputs ---------------------------------------

target_role_input = st.text_input(
    "Pozice, na kterou se hlásíš (volitelné)",
    placeholder="např. Senior Python Backend Engineer",
    help=(
        "Když vyplníš, celá analýza (plat, hidden assets, recommendations) "
        "se počítá pro tuto roli a model vyhodnotí match. Když necháš prázdné, "
        "použije se auto-detekovaná best-fit role z CV."
    ),
)
target_role = target_role_input.strip() or None

uploaded = st.file_uploader("Nahraj CV (PDF nebo DOCX)", type=["pdf", "docx"])

if uploaded is None:
    st.info("👈 Vyber soubor pro analýzu.")
    st.stop()

spinner_label = "Analyzuji CV (5 LLM volání)…" if target_role else "Analyzuji CV (4 LLM volání)…"
with st.spinner(spinner_label):
    try:
        result: CVAnalysis = analyze_cv(uploaded.getvalue(), uploaded.name, target_role=target_role)
    except Exception as e:  # noqa: BLE001 — surface anything to user
        st.error(f"Pipeline error: {e}")
        st.stop()


# -------------------------- Header label ---------------------------------

source_badge = "target" if result.role_source == "target" else "auto-detected"
st.subheader(
    f"📌 Analyzováno pro pozici: **{result.analysis_role}** "
    f":blue-badge[{source_badge}] · CZ-ISCO {result.cz_isco_code} · jazyk {result.language.upper()}"
)
if result.role_source == "target":
    st.caption(
        f"💡 Best-fit podle CV: **{result.detected_role}**. Pokud chceš vidět "
        "analýzu pro tuto auto-detekovanou roli, spusť znovu se stejným CV a "
        "prázdným polem `Pozice`."
    )

st.divider()


# -------------------------- Match panel (only with target) ---------------

if result.target:
    t = result.target
    st.subheader(f"🎯 Match na pozici: {t.target_role}")
    tc1, tc2, tc3 = st.columns([1, 1, 2])
    tc1.metric("Match score", f"{t.match_score}/100")
    tc2.metric("CZ-ISCO", t.target_cz_isco)
    tc3.markdown(f"**Hodnocení:** {t.rationale}")
    st.divider()


# -------------------------- Salary range chart ---------------------------


def _range_chart(result: CVAnalysis) -> go.Figure:
    """Horizontal market range with markers for both tracks."""
    s = result.track_explicit.salary_estimate  # market band identical for both tracks
    explicit_pt = result.track_explicit.salary_estimate.median
    inferred_pt = result.track_with_inferred.salary_estimate.median

    fig = go.Figure()
    fig.add_shape(
        type="line",
        x0=s.market_p25,
        x1=s.market_p90,
        y0=0,
        y1=0,
        line=dict(color="#d0d0d0", width=18),
    )
    fig.add_shape(
        type="line",
        x0=s.market_p50,
        x1=s.market_p50,
        y0=-0.4,
        y1=0.4,
        line=dict(color="#888", width=2, dash="dot"),
    )
    fig.add_shape(
        type="line",
        x0=s.market_p75,
        x1=s.market_p75,
        y0=-0.4,
        y1=0.4,
        line=dict(color="#888", width=2, dash="dot"),
    )
    fig.add_trace(
        go.Scatter(
            x=[explicit_pt],
            y=[0],
            mode="markers+text",
            marker=dict(symbol="diamond", size=18, color="#1f77b4"),
            text=["baseline"],
            textposition="top center",
            name="Buzzword baseline",
            hovertemplate="Baseline: %{x:,.0f} CZK<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[inferred_pt],
            y=[0],
            mode="markers+text",
            marker=dict(symbol="star", size=22, color="#d62728"),
            text=["s hidden assets"],
            textposition="bottom center",
            name="S hidden assets",
            hovertemplate="S hidden assets: %{x:,.0f} CZK<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(
            title="Hrubá měsíční mzda (CZK)",
            tickformat=",d",
            tickmode="array",
            tickvals=[s.market_p25, s.market_p50, s.market_p75, s.market_p90],
            ticktext=[
                f"P25<br>{s.market_p25:,}",
                f"P50<br>{s.market_p50:,}",
                f"P75<br>{s.market_p75:,}",
                f"P90<br>{s.market_p90:,}",
            ],
        ),
        yaxis=dict(visible=False, range=[-1, 1]),
        height=220,
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=True,
        legend=dict(orientation="h", y=-0.3),
    )
    return fig


st.subheader(f"💰 Tržní rozmezí pro pozici {result.analysis_role}")
st.plotly_chart(_range_chart(result), width="stretch")


# -------------------------- Parallel track cards -------------------------


def _radar(track: TrackResult, name: str) -> go.Figure:
    b = track.breakdown
    fig = go.Figure(
        data=go.Scatterpolar(
            r=[
                b.years_experience,
                b.skills_depth,
                b.role_progression,
                b.education,
                b.years_experience,
            ],
            theta=["Years exp", "Skills depth", "Role progression", "Education", "Years exp"],
            fill="toself",
            name=name,
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=340,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def _render_track(track: TrackResult, *, title: str, caption: str, container) -> None:
    s = track.salary_estimate
    with container:
        st.markdown(f"### {title}")
        st.caption(caption)
        sub_a, sub_b = st.columns(2)
        sub_a.metric("Seniority score", f"{track.seniority_score}/100")
        sub_b.metric(
            "Plat (medián)",
            f"{s.median:,} {s.currency}".replace(",", " "),
            delta=f"P{s.percentile_position}",
        )
        st.caption(f"Rozsah: {s.low:,} – {s.high:,} {s.currency}".replace(",", " "))
        st.plotly_chart(_radar(track, title), width="stretch")


col_a, col_b = st.columns(2, gap="large")
_render_track(
    result.track_explicit,
    title="🪧 Buzzword baseline (skeptický)",
    caption="Skóre a plat z toho, co CV literálně tvrdí. Inferred capabilities ignorovány.",
    container=col_a,
)
_render_track(
    result.track_with_inferred,
    title="🔍 S hidden assets (potenciál)",
    caption="Skóre a plat včetně confidence-vážených inferred capabilities. Strop, ne pravda.",
    container=col_b,
)

st.divider()


# -------------------------- Hidden assets list ---------------------------

if result.inferred_capabilities:
    st.subheader(f"🧠 Hidden assets pro roli: {result.analysis_role}")
    st.caption(
        "Schopnosti odvozené z celého CV (work, education, hobbies) a relevantní "
        "pro analyzovanou roli. Model je instruován ke skepticismu."
    )

    must_have = [c for c in result.inferred_capabilities if c.relevance == "must_have"]
    nice_to_have = [c for c in result.inferred_capabilities if c.relevance == "nice_to_have"]

    def _render_cap(cap):
        line = f"**{cap.skill}** _(confidence {cap.confidence:.2f})_  \n> {cap.evidence_quote}"
        if cap.caveat:
            line += f"  \n*⚠️ Caveat: {cap.caveat}*"
        st.markdown(line)

    ha_a, ha_b = st.columns(2, gap="large")
    with ha_a:
        st.markdown("### 🎯 Must-have pro tuto roli")
        if must_have:
            for cap in must_have:
                _render_cap(cap)
        else:
            st.caption("_Žádné must-have hidden assets detekovány._")
    with ha_b:
        st.markdown("### 💡 Nice-to-have")
        if nice_to_have:
            for cap in nice_to_have:
                _render_cap(cap)
        else:
            st.caption("_Žádné nice-to-have hidden assets detekovány._")

    st.divider()


# -------------------------- Strengths & gaps -----------------------------

c1, c2 = st.columns(2)
with c1:
    st.subheader("✅ Silné stránky")
    for s in result.strengths:
        st.markdown(f"- {s}")
with c2:
    st.subheader("⚠️ Mezery")
    for g in result.gaps:
        st.markdown(f"- {g}")


# -------------------------- Recommendations ------------------------------

st.subheader("🎯 3 doporučení pro růst mzdy (+30 %)")
for i, rec in enumerate(result.recommendations, start=1):
    with st.expander(f"#{i}: {rec.action}"):
        st.markdown(f"**Cílová dovednost:** {rec.target_skill}")
        st.markdown(f"**Časová investice:** {rec.time_investment}")
        st.markdown(f"**Očekávaný dopad:** {rec.expected_impact}")


# -------------------------- Raw JSON -------------------------------------

with st.expander("🔧 Raw JSON output"):
    st.json(result.model_dump())


st.caption(
    f"Zpracováno za {result.processing_metadata.get('elapsed_seconds', '?')} s "
    f"({result.processing_metadata.get('raw_text_chars', 0)} znaků). "
    f"Mzda: ISPV {result.processing_metadata.get('ispv_period', '?')}, "
    f"sféra {result.processing_metadata.get('ispv_sphere', '?')}."
)
