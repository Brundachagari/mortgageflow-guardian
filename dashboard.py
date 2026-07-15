"""Live web dashboard for MortgageFlow Guardian (local, no AWS, no cost).

Run it with:
    streamlit run dashboard.py

The centerpiece is an animated pipeline: click a document type and watch it flow
through Upload -> S3 -> SQS -> Step Functions -> Lambda -> outcome, with each
stage lighting up in turn. Same pipeline code as demo.py and the tests.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import altair as alt  # noqa: E402  (ships with streamlit)
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from extraction.mock_provider import MockExtractor  # noqa: E402
from notifications.notifier import CollectingNotifier  # noqa: E402
from pipeline import Pipeline  # noqa: E402
from storage.repository import InMemoryRepository  # noqa: E402

st.set_page_config(page_title="MortgageFlow Guardian", page_icon="🛡️", layout="wide")

# --- palette ---------------------------------------------------------------
BLUE = "#185FA5"
STATUS_COLORS = {
    "PROCESSED": ("#EAF3DE", "#173404"),
    "NEEDS_REVIEW": ("#FAEEDA", "#412402"),
    "FAILED": ("#FCEBEB", "#501313"),
    "DUPLICATE": ("#E6F1FB", "#042C53"),
}
STAGES = [
    ("Upload", "📤"),
    ("S3", "🪣"),
    ("SQS", "📨"),
    ("Step Functions", "🔀"),
    ("Lambda", "⚡"),
    ("Result", "●"),
]
CLEAN_CONTENT = b"fictional-clean-paystub-v1"  # reused so a 2nd send = duplicate

st.markdown(
    """
    <style>
      #MainMenu, footer {visibility:hidden;}
      .block-container {padding-top:2rem; max-width:1080px;}
      .stButton>button{border-radius:10px;font-weight:600;border:1px solid #dfe3e8;
        padding:.55rem .25rem;transition:all .15s;}
      .stButton>button:hover{border-color:#185FA5;color:#185FA5;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _reset():
    st.session_state.repo = InMemoryRepository()
    st.session_state.notifier = CollectingNotifier()
    st.session_state.dlq = []
    st.session_state.events = []
    st.session_state.dupes = 0
    st.session_state.last = None


if "repo" not in st.session_state:
    _reset()


def _money(v):
    return f"${v:,.2f}" if isinstance(v, (int, float)) else "—"


# --------------------------------------------------------------------------- #
# Pipeline-flow renderer (the centerpiece)
# --------------------------------------------------------------------------- #
def flow_html(active: int, outcome_key: str | None = None) -> str:
    pills = []
    for i, (label, icon) in enumerate(STAGES):
        is_last = i == len(STAGES) - 1
        if is_last and outcome_key:
            bg, fg = STATUS_COLORS[outcome_key]
            bd = fg
            icon = {"PROCESSED": "✅", "NEEDS_REVIEW": "🟡", "FAILED": "🔴", "DUPLICATE": "🔁"}[outcome_key]
            label = outcome_key.replace("_", " ").title()
        elif i < active:
            bg, fg, bd = "#E6F1FB", BLUE, "#cfe0f3"      # done
        elif i == active:
            bg, fg, bd = BLUE, "#FFFFFF", BLUE            # active (moving highlight)
        else:
            bg, fg, bd = "#eef0f2", "#9aa0a6", "#e4e6e9"  # idle
        pills.append(
            f"<span style='display:inline-flex;align-items:center;gap:6px;"
            f"padding:11px 15px;border-radius:12px;background:{bg};color:{fg};"
            f"border:1px solid {bd};font-weight:600;font-size:.9rem;white-space:nowrap'>"
            f"{icon} {label}</span>"
        )
    arrow = "<span style='color:#c3c8cf;margin:0 4px;font-size:1.15rem'>▸</span>"
    inner = arrow.join(pills)
    return (
        "<div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:center;"
        "gap:4px;padding:22px 16px;background:#F5F7FA;border-radius:18px;"
        f"border:1px solid #ececec'>{inner}</div>"
    )


def run(scenario, content, fail_times, flow_ph, banner_ph):
    """Run the real pipeline, then animate the flow and show the result."""
    pipe = Pipeline(
        extractor=MockExtractor(scenario=scenario, fail_times=fail_times),
        repository=st.session_state.repo,
        notifier=st.session_state.notifier,
        dead_letter_queue=st.session_state.dlq,
        sleep=lambda s: time.sleep(min(s, 0.3)),
    )
    result = pipe.process(content)

    if result.deduplicated:
        st.session_state.dupes += 1
        key, head = "DUPLICATE", "Duplicate detected"
        detail = f"Same content as {result.record['documentId']} — skipped re-processing."
    elif result.dead_lettered:
        dl = result.dead_letter
        key, head = "FAILED", "Failed → dead-letter queue"
        detail = f"{dl.category.value} · {dl.reason} · {dl.attempts} attempt(s)"
    else:
        r = result.record
        key = r["processingStatus"]
        if key == "PROCESSED":
            head = "Processed" + (f" after {r['attemptCount']} attempts" if r["attemptCount"] > 1 else "")
            detail = (
                f"{r['documentId']} · {r.get('employeeName')} · {r.get('employerName')} · "
                f"{_money(r.get('grossPay'))} · {r.get('confidenceScore')}% confidence"
            )
        else:
            head = "Needs human review"
            detail = f"{r['documentId']} · {', '.join(r.get('reviewReasons', []))}"

    st.session_state.last = {"key": key, "head": head, "detail": detail}
    st.session_state.events.insert(0, f"{time.strftime('%H:%M:%S')}  {head}")

    # animate the flow: light up each stage, then reveal the outcome
    for i in range(len(STAGES) - 1):
        flow_ph.markdown(flow_html(i), unsafe_allow_html=True)
        time.sleep(0.22)
    flow_ph.markdown(flow_html(len(STAGES) - 1, key), unsafe_allow_html=True)
    _banner(banner_ph, st.session_state.last)


def _banner(ph, x):
    bg, fg = STATUS_COLORS[x["key"]]
    ph.markdown(
        f"<div style='background:{bg};color:{fg};border-radius:12px;padding:15px 20px;margin-top:10px'>"
        f"<div style='font-size:1.05rem;font-weight:700'>{x['head']}</div>"
        f"<div style='font-size:.9rem;opacity:.85;margin-top:3px'>{x['detail']}</div></div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    "<div style='display:flex;align-items:center;gap:12px'>"
    "<span style='font-size:1.7rem;font-weight:700'>🛡️ MortgageFlow Guardian</span>"
    "<span style='background:#EAF3DE;color:#173404;padding:3px 11px;border-radius:20px;"
    "font-size:.72rem;font-weight:700'>● LIVE</span></div>"
    "<div style='color:#6b7280;font-size:.92rem;margin-top:2px'>"
    "Reliability layer for an AI document workflow · fictional demo, synthetic data</div>",
    unsafe_allow_html=True,
)

kpi_ph = st.empty()  # filled after processing so counts are fresh
st.write("")

# --------------------------------------------------------------------------- #
# Controls
# --------------------------------------------------------------------------- #
st.markdown("**Send a document through the pipeline**")
cols = st.columns(6)
clicked = None
if cols[0].button("🟢 Clean", use_container_width=True):
    clicked = ("clean", CLEAN_CONTENT, 0)
if cols[1].button("🟡 Low confidence", use_container_width=True):
    clicked = ("low_confidence", b"lc-%f" % time.time(), 0)
if cols[2].button("🟡 Missing field", use_container_width=True):
    clicked = ("missing_field", b"mf-%f" % time.time(), 0)
if cols[3].button("🔁 Timeout→retry", use_container_width=True):
    clicked = ("clean", b"rt-%f" % time.time(), 2)
if cols[4].button("🔴 Corrupt", use_container_width=True):
    clicked = ("corrupt", b"cr-%f" % time.time(), 0)
if cols[5].button("♻️ Reset", use_container_width=True):
    _reset()

# --- the animated pipeline flow + result banner ----------------------------
flow_ph = st.empty()
banner_ph = st.empty()

if clicked:
    run(clicked[0], clicked[1], clicked[2], flow_ph, banner_ph)
else:
    last = st.session_state.last
    flow_ph.markdown(flow_html(-1, last["key"] if last else None), unsafe_allow_html=True)
    if last:
        _banner(banner_ph, last)
    else:
        banner_ph.info("Click a document type above to watch it flow through the pipeline.")

# --------------------------------------------------------------------------- #
# KPI cards (filled now, with fresh counts)
# --------------------------------------------------------------------------- #
repo = st.session_state.repo
counts = {
    "Processed": (len(repo.list_by_status("PROCESSED")), "#63C132"),
    "Needs review": (len(repo.list_by_status("NEEDS_REVIEW")), "#EF9F27"),
    "Dead-letter": (len(st.session_state.dlq), "#E24B4A"),
    "Duplicates": (st.session_state.dupes, BLUE),
}
cards = "".join(
    f"<div style='flex:1;background:#fff;border:1px solid #ececec;border-radius:14px;"
    f"padding:14px 18px;border-top:3px solid {color}'>"
    f"<div style='font-size:1.9rem;font-weight:800;line-height:1'>{val}</div>"
    f"<div style='font-size:.75rem;color:#6b7280;text-transform:uppercase;"
    f"letter-spacing:.05em;margin-top:6px'>{label}</div></div>"
    for label, (val, color) in counts.items()
)
kpi_ph.markdown(
    f"<div style='display:flex;gap:14px;margin-top:14px'>{cards}</div>",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Chart + details
# --------------------------------------------------------------------------- #
st.write("")
left, right = st.columns([1, 1.3])

with left:
    st.markdown("**Outcomes**")
    chart_df = pd.DataFrame(
        {"Outcome": list(counts.keys()), "Count": [v for v, _ in counts.values()]}
    )
    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadius=6, size=26)
        .encode(
            x=alt.X("Count:Q", axis=alt.Axis(tickMinStep=1, title=None)),
            y=alt.Y("Outcome:N", sort=list(counts.keys()), title=None),
            color=alt.Color(
                "Outcome:N",
                scale=alt.Scale(
                    domain=list(counts.keys()),
                    range=[c for _, c in counts.values()],
                ),
                legend=None,
            ),
        )
        .properties(height=170)
    )
    st.altair_chart(chart, use_container_width=True)

with right:
    t_rec, t_dlq, t_log = st.tabs(["📄 Records", "🔴 Dead-letter", "📜 Activity"])
    with t_rec:
        records = repo.all()
        if records:
            df = pd.DataFrame(
                [
                    {
                        "Document": r["documentId"],
                        "Status": r["processingStatus"],
                        "Employee": r.get("employeeName") or "—",
                        "Gross pay": _money(r.get("grossPay")),
                        "Conf.": r.get("confidenceScore"),
                        "Tries": r.get("attemptCount"),
                    }
                    for r in records
                ]
            )

            def _badge(v):
                bg, fg = STATUS_COLORS.get(v, ("#f0f0f0", "#333"))
                return f"background-color:{bg};color:{fg};font-weight:600"

            st.dataframe(
                df.style.map(_badge, subset=["Status"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No documents yet.")
    with t_dlq:
        if st.session_state.dlq:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Category": dl.category.value, "Reason": dl.reason, "Tries": dl.attempts}
                        for dl in st.session_state.dlq
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Empty — no permanent failures.")
    with t_log:
        if st.session_state.events:
            st.code("\n".join(st.session_state.events[:15]), language="text")
        else:
            st.caption("No activity yet.")
