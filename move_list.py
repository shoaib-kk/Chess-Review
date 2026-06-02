"""
components/move_list.py
Center panel: scrollable move list with classification badges.
"""

import streamlit as st
from models import GameSummary, MoveClassification, CLASSIFICATION_COLORS, CLASSIFICATION_EMOJIS


# Background tints for each move row
ROW_TINTS = {
    MoveClassification.EXCELLENT:  "transparent",
    MoveClassification.INACCURACY: "#facc1510",
    MoveClassification.MISTAKE:    "#f9731618",
    MoveClassification.BLUNDER:    "#ef444420",
}

BORDER_COLORS = {
    MoveClassification.EXCELLENT:  "transparent",
    MoveClassification.INACCURACY: "#facc15",
    MoveClassification.MISTAKE:    "#f97316",
    MoveClassification.BLUNDER:    "#ef4444",
}


def render_move_list(summary: GameSummary, current_index: int) -> None:
    """Render a paired move list (white + black per row) with click navigation."""

    analyses = summary.move_analyses
    if not analyses:
        return

    # Group into pairs: [(white_analysis, black_analysis_or_None), ...]
    pairs = []
    i = 0
    while i < len(analyses):
        white = analyses[i] if analyses[i].color == "White" else None
        black = analyses[i + 1] if (i + 1 < len(analyses) and analyses[i + 1].color == "Black") else None
        if white:
            pairs.append((white, black))
            i += 2
        else:
            # Shouldn't happen, but handle gracefully
            pairs.append((None, analyses[i]))
            i += 1

    # Inject CSS for the move list
    st.markdown("""
    <style>
    .move-row { display:flex; align-items:center; gap:6px; padding:3px 6px;
                border-radius:6px; margin-bottom:2px; cursor:pointer; }
    .move-row:hover { background: #ffffff15 !important; }
    .move-cell { flex:1; padding:3px 6px; border-radius:4px; font-size:0.88rem;
                 font-family: 'Courier New', monospace; font-weight:500; }
    .move-cell.active { background:#3b82f6 !important; color:#fff !important; }
    .move-num { color:#666; font-size:0.8rem; width:28px; text-align:right;
                flex-shrink:0; font-family:monospace; }
    .badge { font-size:0.65rem; font-weight:800; padding:1px 4px; border-radius:3px; }
    </style>
    """, unsafe_allow_html=True)

    # Scrollable container
    with st.container(height=460):
        for move_num, (white_ma, black_ma) in enumerate(pairs):
            col_num, col_w, col_b = st.columns([0.15, 0.42, 0.42])

            pair_num = (white_ma or black_ma).move_number

            with col_num:
                st.markdown(
                    f'<div style="color:#666;font-size:0.8rem;font-family:monospace;'
                    f'padding-top:5px;text-align:right;">{pair_num}.</div>',
                    unsafe_allow_html=True,
                )

            # White move button
            with col_w:
                if white_ma:
                    w_idx = analyses.index(white_ma)
                    w_active = w_idx == current_index
                    w_color = CLASSIFICATION_COLORS[white_ma.classification]
                    w_border = BORDER_COLORS[white_ma.classification]
                    w_badge = CLASSIFICATION_EMOJIS[white_ma.classification]
                    w_bg = "#3b82f6" if w_active else ROW_TINTS[white_ma.classification]
                    w_text_color = "#fff" if w_active else "#e0e0e0"

                    btn_label = f"{white_ma.move_played}"
                    if white_ma.classification != MoveClassification.EXCELLENT:
                        btn_label += f" {w_badge}"

                    if st.button(
                        btn_label,
                        key=f"mv_w_{w_idx}",
                        use_container_width=True,
                    ):
                        st.session_state.move_index = w_idx
                        st.rerun()

            # Black move button
            with col_b:
                if black_ma:
                    b_idx = analyses.index(black_ma)
                    b_active = b_idx == current_index
                    b_badge = CLASSIFICATION_EMOJIS[black_ma.classification]

                    btn_label = f"{black_ma.move_played}"
                    if black_ma.classification != MoveClassification.EXCELLENT:
                        btn_label += f" {b_badge}"

                    if st.button(
                        btn_label,
                        key=f"mv_b_{b_idx}",
                        use_container_width=True,
                    ):
                        st.session_state.move_index = b_idx
                        st.rerun()
