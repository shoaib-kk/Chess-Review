"""
components/eval_graph.py
Evaluation graph rendered with Plotly.
"""

import streamlit as st
import plotly.graph_objects as go
from models import GameSummary, MoveClassification, CLASSIFICATION_COLORS


def _clamp(val, lo=-10, hi=10):
    if val is None:
        return 0.0
    return max(lo, min(hi, val / 100))


def render_eval_graph(summary: GameSummary, current_index: int) -> None:
    """Render an evaluation chart with move classification markers."""

    analyses = summary.move_analyses
    if not analyses:
        return

    # Build x-axis labels and y values (white's POV, clamped to ±10 pawns)
    x_labels = []
    y_vals = []
    colors_markers = []
    sizes_markers = []
    hover_texts = []

    for i, ma in enumerate(analyses):
        dot = "." if ma.color == "White" else "…"
        x_labels.append(f"{ma.move_number}{dot}{ma.move_played}")
        y = _clamp(ma.eval_white_pov * 100 if ma.eval_white_pov is not None else 0)
        y_vals.append(y)

        c = CLASSIFICATION_COLORS[ma.classification]
        colors_markers.append(c)
        sizes_markers.append(10 if ma.classification != MoveClassification.EXCELLENT else 5)

        cp_str = f"{ma.cp_loss:.0f} cp loss" if ma.cp_loss is not None else ""
        hover_texts.append(
            f"<b>{ma.move_number}{'.' if ma.color == 'White' else '…'}{ma.move_played}</b><br>"
            f"Eval: {ma.eval_white_pov:+.2f}<br>"
            f"{cp_str}<br>"
            f"<b>{ma.classification.value}</b>"
            if ma.eval_white_pov is not None else ma.move_played
        )

    x_nums = list(range(len(analyses)))

    # Area fill: white advantage above 0, black below
    fig = go.Figure()

    # White advantage fill
    fig.add_trace(go.Scatter(
        x=x_nums, y=[max(0, v) for v in y_vals],
        fill="tozeroy",
        fillcolor="rgba(240,217,181,0.35)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Black advantage fill
    fig.add_trace(go.Scatter(
        x=x_nums, y=[min(0, v) for v in y_vals],
        fill="tozeroy",
        fillcolor="rgba(50,50,50,0.55)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Main eval line
    fig.add_trace(go.Scatter(
        x=x_nums, y=y_vals,
        mode="lines",
        line=dict(color="#94a3b8", width=2),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Classification markers
    fig.add_trace(go.Scatter(
        x=x_nums, y=y_vals,
        mode="markers",
        marker=dict(
            color=colors_markers,
            size=sizes_markers,
            line=dict(width=1, color="#1e293b"),
        ),
        text=hover_texts,
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
    ))

    # Current move vertical line
    if 0 <= current_index < len(analyses):
        fig.add_vline(
            x=current_index,
            line_color="#3b82f6",
            line_width=2,
            line_dash="dot",
        )

    # Zero line
    fig.add_hline(y=0, line_color="#ffffff30", line_width=1)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=10, t=10, b=40),
        height=160,
        xaxis=dict(
            showgrid=False,
            tickmode="array",
            tickvals=x_nums[::max(1, len(x_nums)//10)],
            ticktext=x_labels[::max(1, len(x_labels)//10)],
            tickfont=dict(color="#666", size=10),
            tickangle=-30,
        ),
        yaxis=dict(
            range=[-10.5, 10.5],
            showgrid=True,
            gridcolor="#ffffff10",
            tickfont=dict(color="#666", size=10),
            zeroline=False,
            tickvals=[-5, 0, 5],
            ticktext=["-5", "0", "+5"],
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
