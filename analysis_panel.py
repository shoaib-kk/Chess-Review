"""
components/analysis_panel.py
Right panel: per-move analysis details + summary stats.
"""

import streamlit as st
from models import GameSummary, MoveClassification, CLASSIFICATION_COLORS, CLASSIFICATION_EMOJIS


def _fmt_eval(cp):
    if cp is None:
        return "—"
    if abs(cp) >= 100_000:
        return "Mate" if cp > 0 else "-Mate"
    return f"{cp / 100:+.2f}"


def _eval_bar(cp: float | None) -> str:
    """Mini horizontal eval bar HTML."""
    if cp is None:
        return ""
    clamped = max(-1000, min(1000, cp))
    # white % = 50 + (clamped/1000)*50
    white_pct = 50 + (clamped / 1000) * 50
    white_pct = max(2, min(98, white_pct))
    black_pct = 100 - white_pct
    return (
        f'<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;margin:6px 0;">'
        f'<div style="width:{white_pct:.1f}%;background:#f0d9b5;"></div>'
        f'<div style="width:{black_pct:.1f}%;background:#2d2d2d;"></div>'
        f'</div>'
    )


def render_analysis_panel(summary: GameSummary, move_index: int) -> None:
    """Render the right analysis panel."""

    analyses = summary.move_analyses

    # ── Game header ───────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:10px;padding:12px 14px;margin-bottom:12px;">
        <div style="font-size:0.8rem;color:#64748b;margin-bottom:2px;">{summary.event} · {summary.date}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <span style="font-size:1rem;font-weight:700;color:#f0d9b5;">⬜ {summary.white_player}</span>
            </div>
            <div style="color:#64748b;font-size:0.85rem;font-weight:600;">{summary.result}</div>
            <div>
                <span style="font-size:1rem;font-weight:700;color:#b58863;">⬛ {summary.black_player}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Per-move analysis ─────────────────────────────────────────────────────
    if move_index >= 0 and move_index < len(analyses):
        ma = analyses[move_index]
        c = CLASSIFICATION_COLORS[ma.classification]
        emoji = CLASSIFICATION_EMOJIS[ma.classification]
        dot = "." if ma.color == "White" else "…"

        # Eval from white's POV for the bar (eval_before, side-to-move POV → white POV)
        eval_white = ma.eval_white_pov * 100 if ma.eval_white_pov is not None else None

        st.markdown(f"""
        <div style="background:#1e293b;border-left:4px solid {c};border-radius:8px;
                    padding:12px 14px;margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:1.15rem;font-weight:700;color:#e2e8f0;font-family:monospace;">
                    {ma.move_number}{dot} {ma.move_played}
                </span>
                <span style="background:{c};color:#000;padding:3px 10px;border-radius:12px;
                             font-size:0.78rem;font-weight:800;">{emoji} {ma.classification.value}</span>
            </div>
            {_eval_bar(eval_white)}
        </div>
        """, unsafe_allow_html=True)

        # Detail grid
        def stat_row(label, val, color="#e2e8f0"):
            return (
                f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
                f'border-bottom:1px solid #ffffff08;">'
                f'<span style="color:#64748b;font-size:0.82rem;">{label}</span>'
                f'<span style="color:{color};font-size:0.82rem;font-weight:600;font-family:monospace;">{val}</span>'
                f'</div>'
            )

        cp_loss_str = f"{ma.cp_loss:.0f} cp" if ma.cp_loss is not None else "—"
        cp_color = c if ma.classification != MoveClassification.EXCELLENT else "#4ade80"

        st.markdown(f"""
        <div style="background:#0f172a;border-radius:8px;padding:10px 14px;margin-bottom:10px;">
            {stat_row("Eval before", _fmt_eval(ma.eval_before))}
            {stat_row("Eval after", _fmt_eval(ma.eval_after))}
            {stat_row("Centipawn loss", cp_loss_str, cp_color)}
            {stat_row("Best move", ma.best_move or "—", "#4ade80")}
            {stat_row("Played by", ma.color)}
        </div>
        """, unsafe_allow_html=True)

        # Principal variation
        if ma.pv:
            pv_str = " ".join(ma.pv)
            st.markdown(f"""
            <div style="background:#0f172a;border-radius:8px;padding:10px 14px;margin-bottom:10px;">
                <div style="color:#64748b;font-size:0.75rem;margin-bottom:4px;">BEST LINE</div>
                <div style="color:#94a3b8;font-size:0.82rem;font-family:monospace;
                            line-height:1.6;word-break:break-all;">{pv_str}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#1e293b;border-radius:8px;padding:16px;margin-bottom:10px;
                    text-align:center;color:#475569;">
            ← Navigate moves to see analysis
        </div>
        """, unsafe_allow_html=True)

    # ── Summary statistics ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="color:#64748b;font-size:0.75rem;font-weight:700;letter-spacing:0.08em;'
        'margin-bottom:8px;">ACCURACY SUMMARY</div>',
        unsafe_allow_html=True,
    )

    def stat_block(label, w_val, b_val, color):
        return (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 0;border-bottom:1px solid #ffffff08;">'
            f'<span style="color:#94a3b8;font-size:0.82rem;width:70px;">{w_val}</span>'
            f'<span style="color:{color};font-size:0.8rem;font-weight:600;">{label}</span>'
            f'<span style="color:#94a3b8;font-size:0.82rem;width:70px;text-align:right;">{b_val}</span>'
            f'</div>'
        )

    st.markdown(f"""
    <div style="background:#0f172a;border-radius:8px;padding:10px 14px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="color:#f0d9b5;font-size:0.78rem;font-weight:700;">White</span>
            <span style="color:#64748b;font-size:0.78rem;"></span>
            <span style="color:#b58863;font-size:0.78rem;font-weight:700;">Black</span>
        </div>
        {stat_block("?! Inaccuracies", summary.white_inaccuracies, summary.black_inaccuracies, "#facc15")}
        {stat_block("?  Mistakes", summary.white_mistakes, summary.black_mistakes, "#f97316")}
        {stat_block("?? Blunders", summary.white_blunders, summary.black_blunders, "#ef4444")}
    </div>
    """, unsafe_allow_html=True)
