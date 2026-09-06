from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


PALETTE = {
    "navy": "#1e3a5f",
    "blue": "#2a6cb5",
    "emerald": "#047857",
    "teal": "#0f766e",
    "amber": "#d97706",
    "rose": "#be123c",
}


def money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def year_delta(frame, column: str, *, points: bool = False, digits: int = 1) -> str | None:
    if len(frame) < 2:
        return None
    current = float(frame.iloc[-1][column])
    previous = float(frame.iloc[-2][column])
    if points:
        return f"{current - previous:+.{digits}f} pp"
    if previous == 0:
        return None
    return f"{(current - previous) / previous * 100:+.{digits}f}%"


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1240px;}
        h1, h2, h3 {letter-spacing: 0; color: #172033;}
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-top: 3px solid #047857;
            border-radius: 6px;
            padding: 13px 14px;
            box-shadow: 0 5px 16px rgba(30, 58, 95, 0.06);
        }
        div[data-testid="stMetricLabel"] {color: #475569;}
        div[data-testid="stMetricValue"] {color: #172033;}
        section[data-testid="stSidebar"] {background: #eef2f7;}
        .coverage-note {
            border-left: 4px solid #2a6cb5;
            background: #ffffff;
            padding: 10px 13px;
            color: #334155;
        }
        .insight-band {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-left: 4px solid #d97706;
            border-radius: 6px;
            padding: 14px 16px;
            margin: 0.4rem 0 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def prepare_chart(fig: go.Figure, height: int = 390) -> go.Figure:
    title_text = fig.layout.title.text if fig.layout.title else ""
    fig.update_traces(cliponaxis=False, selector=dict(type="bar"))
    fig.update_layout(
        height=height,
        margin=dict(t=112, r=18, b=44, l=18),
        legend=dict(orientation="h", yanchor="top", y=1.08, xanchor="left", x=0),
        title=dict(text=title_text or "", y=0.98, x=0, xanchor="left", font=dict(size=17)),
        font=dict(color="#172033"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e2e8f0")
    return fig
