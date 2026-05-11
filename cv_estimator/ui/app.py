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
from cv_estimator.salary.role_mapping import UnmappedRoleError

load_dotenv()

# Streamlit Community Cloud delivers secrets via st.secrets; bridge to env
# so `cv_estimator.llm` (which reads os.environ) works in both deploy modes.
if not os.environ.get("ANTHROPIC_API_KEY"):
    try:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass

st.set_page_config(page_title="CV Estimator", page_icon="📄", layout="wide")
st.title("📄 CV Estimator")
st.caption("AI odhad seniority skóre, tržní mzdy a roadmapy růstu z CV.")

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error(
        "Chybí `ANTHROPIC_API_KEY`. Lokálně: `.env` ze `.env.example`. "
        "Cloud: Secrets v Streamlit Cloud."
    )
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
    st.info("👆 Vyber soubor pro analýzu.")
    st.stop()

# Invalidate cached result when EITHER the upload OR the target_role changes.
_state_key = (uploaded.file_id, target_role)
if st.session_state.get("state_key") != _state_key:
    st.session_state.pop("result", None)
    st.session_state["state_key"] = _state_key

run_button = st.button(
    "🚀 Spustit analýzu",
    type="primary",
    help="Po nahrání souboru a (volitelně) vyplnění pozice klikni pro spuštění.",
)

if run_button:
    spinner_label = (
        "Analyzuji CV (5 LLM volání)…" if target_role else "Analyzuji CV (4 LLM volání)…"
    )
    with st.spinner(spinner_label):
        try:
            st.session_state["result"] = analyze_cv(
                uploaded.getvalue(),
                uploaded.name,
                target_role=target_role,
            )
        except UnmappedRoleError as e:
            st.warning(
                f"⚠️ Role **{e.role}** se nepodařilo zmapovat na CZ-ISCO v ISPV databázi. "
                "Použij běžnější název pozice — např. *Senior Backend Engineer*, "
                "*Marketing Manager*, *Lawyer*, *Doctor* — nebo nech pole `Pozice` "
                "prázdné a analýza použije roli auto-detekovanou z CV."
            )
            st.stop()
        except Exception as e:  # noqa: BLE001 — surface anything else to user
            st.error(f"Pipeline error: {e}")
            st.stop()

result: CVAnalysis | None = st.session_state.get("result")
if result is None:
    st.info(
        "📝 Soubor připraven. Pokud chceš, vyplň pole `Pozice` výše a klikni "
        "**Spustit analýzu**."
    )
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
    """Horizontal market range with markers for both tracks.

    Two stacked rows so the baseline and with-inferred markers never
    overlap and each gets a clean value annotation.
    """
    s = result.track_explicit.salary_estimate  # market band identical for both tracks
    explicit_pt = result.track_explicit.salary_estimate.median
    inferred_pt = result.track_with_inferred.salary_estimate.median

    # Two rows: y=1 for baseline, y=-1 for with-inferred. Market band drawn
    # at both rows for visual reference.
    fig = go.Figure()
    for y in (1, -1):
        fig.add_shape(
            type="line",
            x0=s.market_p25,
            x1=s.market_p90,
            y0=y,
            y1=y,
            line=dict(color="#d0d0d0", width=22),
            layer="below",
        )

    # Quartile reference ticks across both rows
    for x_val in (s.market_p50, s.market_p75):
        fig.add_shape(
            type="line",
            x0=x_val,
            x1=x_val,
            y0=-1.8,
            y1=1.8,
            line=dict(color="#aaa", width=1, dash="dot"),
            layer="below",
        )

    # Baseline marker (top row)
    fig.add_trace(
        go.Scatter(
            x=[explicit_pt],
            y=[1],
            mode="markers+text",
            marker=dict(
                symbol="diamond", size=28, color="#1f77b4", line=dict(color="white", width=2)
            ),
            text=[f"{explicit_pt:,} CZK".replace(",", " ")],
            textposition="middle right",
            textfont=dict(size=14, color="#1f77b4"),
            name="🪧 Buzzword baseline",
            hovertemplate="Baseline: %{x:,.0f} CZK<extra></extra>",
        )
    )
    # With-inferred marker (bottom row)
    fig.add_trace(
        go.Scatter(
            x=[inferred_pt],
            y=[-1],
            mode="markers+text",
            marker=dict(symbol="star", size=30, color="#d62728", line=dict(color="white", width=2)),
            text=[f"{inferred_pt:,} CZK".replace(",", " ")],
            textposition="middle right",
            textfont=dict(size=14, color="#d62728"),
            name="🔍 S hidden assets",
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
                f"P25<br>{s.market_p25:,}".replace(",", " "),
                f"P50<br>{s.market_p50:,}".replace(",", " "),
                f"P75<br>{s.market_p75:,}".replace(",", " "),
                f"P90<br>{s.market_p90:,}".replace(",", " "),
            ],
            range=[s.market_p25 * 0.92, s.market_p90 * 1.15],
        ),
        yaxis=dict(
            visible=True,
            tickmode="array",
            tickvals=[1, -1],
            ticktext=["🪧 baseline", "🔍 hidden assets"],
            range=[-2.2, 2.2],
            showgrid=False,
        ),
        height=260,
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False,
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
            theta=[
                "Years exp",
                "Skills coverage",
                "Role progression",
                "Education",
                "Years exp",
            ],
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
    title="🪧 Buzzword baseline",
    caption="Skóre a plat z toho, co CV literálně tvrdí. Inferred capabilities ignorovány.",
    container=col_a,
)
_render_track(
    result.track_with_inferred,
    title="🔍 S hidden assets (potenciál)",
    caption=(
        "Skóre a plat včetně confidence-vážených inferred capabilities. "
        "Scoring rozepsán níže v [Hidden assets](#hidden-assets)."
    ),
    container=col_b,
)

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

st.divider()


# -------------------------- Recommendations ------------------------------

st.subheader("🎯 3 doporučení pro růst mzdy (+30 %)")
for i, rec in enumerate(result.recommendations, start=1):
    with st.expander(f"#{i}: {rec.action}"):
        st.markdown(f"**Cílová dovednost:** {rec.target_skill}")
        st.markdown(f"**Časová investice:** {rec.time_investment}")
        st.markdown(f"**Očekávaný dopad:** {rec.expected_impact}")

st.divider()


# -------------------------- Hidden assets list ---------------------------

if result.inferred_capabilities:
    st.subheader(
        f"🧠 Hidden assets pro roli: {result.analysis_role}",
        anchor="hidden-assets",
    )
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

    # Coverage attribution — only populated for non-tech roles where LLM
    # scored coverage and identified which inputs lifted or undermined it.
    attr = result.track_with_inferred.coverage_attribution
    if attr is not None and (attr.value_adding or attr.concerns):
        st.markdown("#### 📊 Vliv hidden assets na skóre")
        st.caption(
            f"LLM coverage hodnotitel ({result.analysis_role}) označil tyto inputy "
            "jako rozhodující pro pohyb skills_coverage skóre mezi `baseline` a "
            "`s hidden assets`."
        )
        attr_a, attr_b = st.columns(2)
        with attr_a:
            st.markdown("**✅ Capabilities zvedly skóre**")
            if attr.value_adding:
                for name in attr.value_adding:
                    st.markdown(f"- {name}")
            else:
                st.caption("_Žádný value-adding signál._")
        with attr_b:
            st.markdown("**⚠️ Capabilities snížily / nepomohly**")
            if attr.concerns:
                for name in attr.concerns:
                    st.markdown(f"- {name}")
            else:
                st.caption("_Žádné concerns._")

    st.divider()


# -------------------------- Raw JSON -------------------------------------

with st.expander("🔧 Raw JSON output"):
    st.json(result.model_dump())


st.caption(
    f"Zpracováno za {result.processing_metadata.get('elapsed_seconds', '?')} s "
    f"({result.processing_metadata.get('raw_text_chars', 0)} znaků). "
    f"Mzda: ISPV {result.processing_metadata.get('ispv_period', '?')}, "
    f"sféra {result.processing_metadata.get('ispv_sphere', '?')}."
)
