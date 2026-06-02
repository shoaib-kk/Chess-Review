"""
components/board_panel.py
Left panel: interactive chess board.
"""

import streamlit as st
from board_renderer import render_board_svg, fen_to_last_move_uci, san_to_uci
from models import GameSummary, MoveClassification, CLASSIFICATION_COLORS


def render_board_panel(summary: GameSummary, move_index: int) -> None:
    """
    Render the interactive board for the current move index.
    move_index: -1 = starting position, 0..n-1 = after move index.
    """
    analyses = summary.move_analyses

    # Determine FEN and move info
    if move_index < 0:
        fen = summary.initial_fen
        last_move_uci = None
        best_move_uci = None
        classification = None
        caption = "Starting position"
    else:
        ma = analyses[move_index]
        # Board AFTER the move
        import chess
        board = chess.Board(ma.fen_before)
        try:
            move = board.parse_san(ma.move_played)
            last_move_uci = move.uci()
            board.push(move)
            fen = board.fen()
        except Exception:
            fen = ma.fen_before
            last_move_uci = None

        best_move_uci = san_to_uci(ma.fen_before, ma.best_move) if ma.best_move else None
        classification = ma.classification.value
        dot = "." if ma.color == "White" else "…"
        caption = f"{ma.move_number}{dot} {ma.move_played}"

    # Flip board toggle
    flipped = st.session_state.get("board_flipped", False)

    svg = render_board_svg(
        fen=fen,
        last_move_uci=last_move_uci,
        best_move_uci=best_move_uci,
        classification=classification,
        flipped=flipped,
        size=420,
    )

    # Render board
    st.markdown(
        f'<div style="display:flex;justify-content:center;">{svg}</div>',
        unsafe_allow_html=True,
    )

    # Caption + badge
    if move_index >= 0:
        ma = analyses[move_index]
        color_hex = CLASSIFICATION_COLORS.get(ma.classification, "#888")
        badge = (
            f'<span style="background:{color_hex};color:#000;padding:2px 8px;'
            f'border-radius:12px;font-size:0.75rem;font-weight:700;">'
            f'{ma.classification.value}</span>'
        )
        st.markdown(
            f'<div style="text-align:center;margin-top:6px;font-size:0.95rem;color:#ccc;">'
            f'{caption} &nbsp;{badge}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="text-align:center;margin-top:6px;font-size:0.95rem;color:#ccc;">{caption}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Navigation controls
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    total = len(analyses)

    with col1:
        if st.button("⏮", key="nav_start", help="Go to start", use_container_width=True):
            st.session_state.move_index = -1
            st.rerun()
    with col2:
        if st.button("◀", key="nav_prev", help="Previous move", use_container_width=True):
            st.session_state.move_index = max(-1, move_index - 1)
            st.rerun()
    with col3:
        st.markdown(
            f'<div style="text-align:center;padding-top:6px;color:#aaa;font-size:0.85rem;">'
            f'{move_index + 1}/{total}</div>',
            unsafe_allow_html=True,
        )
    with col4:
        if st.button("▶", key="nav_next", help="Next move", use_container_width=True):
            st.session_state.move_index = min(total - 1, move_index + 1)
            st.rerun()
    with col5:
        if st.button("⏭", key="nav_end", help="Go to end", use_container_width=True):
            st.session_state.move_index = total - 1
            st.rerun()

    # Flip board button
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("🔄 Flip Board", key="flip_board", use_container_width=True):
        st.session_state.board_flipped = not flipped
        st.rerun()
