"""Streamlit UI — thin wrapper around `pipeline.analyze_cv`."""

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from cv_estimator.pipeline import analyze_cv

load_dotenv()

st.set_page_config(page_title="CV Estimator", page_icon="📄", layout="wide")
st.title("📄 CV Estimator")
st.caption("AI odhad seniority skóre, tržní mzdy a roadmapy růstu z CV.")

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("Chybí `ANTHROPIC_API_KEY`. Vytvoř `.env` ze `.env.example` a doplň klíč.")
    st.stop()

uploaded = st.file_uploader("Nahraj CV (PDF nebo DOCX)", type=["pdf", "docx"])

if uploaded is None:
    st.info("👈 Vyber soubor pro analýzu.")
    st.stop()

with st.spinner("Analyzuji CV (4 LLM volání)…"):
    try:
        result = analyze_cv(uploaded.getvalue(), uploaded.name)
    except Exception as e:  # noqa: BLE001 — surface anything to user
        st.error(f"Pipeline error: {e}")
        st.stop()

# --- Header KPIs ---
col1, col2, col3 = st.columns(3)
col1.metric("Seniority skóre", f"{result.seniority_score}/100")
col2.metric(
    "Tržní mzda (medián)",
    f"{result.salary_estimate.median:,} {result.salary_estimate.currency}".replace(",", " "),
    delta=f"P{result.salary_estimate.percentile_position}",
)
col3.metric("Detekovaná role", result.detected_role, delta=f"CZ-ISCO {result.cz_isco_code}")

# --- Score breakdown radar ---
b = result.breakdown
radar = go.Figure(
    data=go.Scatterpolar(
        r=[b.years_experience, b.skills_depth, b.role_progression, b.education, b.years_experience],
        theta=["Years exp", "Skills depth", "Role progression", "Education", "Years exp"],
        fill="toself",
        name="Skóre",
    )
)
radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
    showlegend=False,
    height=400,
)
st.subheader("Breakdown komponent")
st.plotly_chart(radar, use_container_width=True)

# --- Strengths & gaps ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("✅ Silné stránky")
    for s in result.strengths:
        st.markdown(f"- {s}")
with c2:
    st.subheader("⚠️ Mezery")
    for g in result.gaps:
        st.markdown(f"- {g}")

# --- Hidden assets ---
if result.inferred_capabilities:
    st.subheader("🔍 Hidden assets (inferred capabilities)")
    st.caption("Schopnosti odvozené z popisu projektů, nikoli z buzzword seznamů.")
    for cap in result.inferred_capabilities:
        st.markdown(
            f"**{cap.skill}** _(confidence {cap.confidence:.2f})_  \n" f"> {cap.evidence_quote}"
        )

# --- Recommendations ---
st.subheader("🎯 3 doporučení pro růst mzdy (+30 %)")
for i, rec in enumerate(result.recommendations, start=1):
    with st.expander(f"#{i}: {rec.action}"):
        st.markdown(f"**Cílová dovednost:** {rec.target_skill}")
        st.markdown(f"**Časová investice:** {rec.time_investment}")
        st.markdown(f"**Očekávaný dopad:** {rec.expected_impact}")

# --- Raw JSON for debugging ---
with st.expander("🔧 Raw JSON output"):
    st.json(result.model_dump())

st.caption(
    f"Zpracováno za {result.processing_metadata.get('elapsed_seconds', '?')} s "
    f"({result.processing_metadata.get('raw_text_chars', 0)} znaků). "
    f"Mzda: ISPV {result.processing_metadata.get('ispv_period', '?')}, "
    f"sféra {result.processing_metadata.get('ispv_sphere', '?')}."
)
