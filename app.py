"""
app.py — Chess Game Reviewer (Streamlit)

Layout:
  Left   → Interactive board + navigation
  Center → Evaluation graph + move list
  Right  → Analysis panel
"""

import streamlit as st
import tempfile
import os
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Chess Game Reviewer",
    page_icon="♟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Dark theme overrides */
[data-testid="stAppViewContainer"] { background: #0f172a; }
[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { background: #1e293b; }

/* Remove default padding */
.block-container { padding-top: 1rem !important; padding-bottom: 0 !important; }

/* Column borders */
.col-board   { border-right: 1px solid #1e293b; padding-right: 12px; }
.col-moves   { border-right: 1px solid #1e293b; padding: 0 12px; }
.col-analysis { padding-left: 12px; }

/* Button styling */
div[data-testid="stButton"] > button {
    background: #1e293b;
    border: 1px solid #334155;
    color: #cbd5e1;
    border-radius: 6px;
    font-size: 0.82rem;
    padding: 4px 8px;
    transition: background 0.15s;
}
div[data-testid="stButton"] > button:hover {
    background: #334155;
    border-color: #475569;
    color: #f1f5f9;
}
div[data-testid="stButton"] > button:active {
    background: #3b82f6 !important;
    color: white !important;
}

/* Progress bar */
[data-testid="stProgress"] > div { background: #3b82f6; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #1e293b;
    border-radius: 10px;
    border: 2px dashed #334155;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f172a; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Imports (after page config) ───────────────────────────────────────────────
from services.game_analyzer import analyze_pgn
from analysis.stockfish_engine import find_stockfish
from components.board_panel import render_board_panel
from components.move_list import render_move_list
from components.eval_graph import render_eval_graph
from components.analysis_panel import render_analysis_panel


# ── Session state initialisation ──────────────────────────────────────────────
def _init_state():
    defaults = {
        "summary": None,
        "move_index": -1,
        "board_flipped": False,
        "analysis_depth": 16,
        "stockfish_path": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
    <span style="font-size:2rem;">♟</span>
    <div>
        <h1 style="margin:0;font-size:1.4rem;color:#f1f5f9;letter-spacing:-0.02em;">
            Chess Game Reviewer
        </h1>
        <p style="margin:0;color:#64748b;font-size:0.82rem;">
            Powered by Stockfish · Upload a PGN to begin
        </p>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar: settings ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    st.session_state.analysis_depth = st.slider(
        "Analysis depth",
        min_value=8, max_value=24,
        value=st.session_state.analysis_depth,
        help="Higher depth = stronger analysis, but slower.",
    )

    custom_path = st.text_input(
        "Stockfish path (optional)",
        value=st.session_state.stockfish_path or "",
        placeholder="Auto-detect",
    )
    if custom_path.strip():
        st.session_state.stockfish_path = custom_path.strip()

    # Stockfish status
    try:
        sf_path = find_stockfish() if not st.session_state.stockfish_path else st.session_state.stockfish_path
        st.success(f"✅ Stockfish found")
        st.caption(sf_path)
    except RuntimeError:
        st.error("❌ Stockfish not found")
        st.markdown("""
        **Install Stockfish:**
        ```bash
        # Ubuntu/Debian
        sudo apt install stockfish

        # macOS
        brew install stockfish
        ```
        """)

    if st.session_state.summary:
        st.markdown("---")
        if st.button("🗑️ Clear game", use_container_width=True):
            st.session_state.summary = None
            st.session_state.move_index = -1
            st.rerun()


# ── Upload / analyse ──────────────────────────────────────────────────────────
if st.session_state.summary is None:
    st.markdown("""
    <div style="background:#1e293b;border-radius:12px;padding:20px 24px;margin-bottom:20px;">
        <h3 style="color:#e2e8f0;margin:0 0 4px 0;font-size:1rem;">Upload a PGN file</h3>
        <p style="color:#64748b;margin:0;font-size:0.85rem;">
            Paste your PGN below or upload a .pgn file to start the engine analysis.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab_upload, tab_paste, tab_sample = st.tabs(["📂 Upload file", "📋 Paste PGN", "🎯 Sample game"])

    pgn_text = None

    with tab_upload:
        uploaded = st.file_uploader("Choose a PGN file", type=["pgn"], label_visibility="collapsed")
        if uploaded:
            pgn_text = uploaded.read().decode("utf-8")
            st.success(f"✅ Loaded: {uploaded.name}")

    with tab_paste:
        pasted = st.text_area("Paste PGN here", height=200, placeholder="[Event ...]\n1. e4 e5 ...")
        if pasted.strip():
            pgn_text = pasted.strip()

    with tab_sample:
        sample_path = Path(__file__).parent / "sample.pgn"
        if sample_path.exists():
            sample_pgn = sample_path.read_text()
            st.code(sample_pgn[:400] + "...", language="text")
            if st.button("▶ Analyse sample game", use_container_width=True):
                pgn_text = sample_pgn

    if pgn_text:
        st.markdown("---")
        if st.button("🔍 Analyse Game", type="primary", use_container_width=True):
            try:
                sf_path = st.session_state.stockfish_path or None
                find_stockfish() if not sf_path else None  # validate

                progress_bar = st.progress(0, text="Starting engine…")
                status_text = st.empty()

                def progress_cb(current, total, label):
                    pct = current / total
                    progress_bar.progress(pct, text=f"Analysing {label}  ({current}/{total})")

                with st.spinner(""):
                    summary = analyze_pgn(
                        pgn_text=pgn_text,
                        engine_path=sf_path,
                        depth=st.session_state.analysis_depth,
                        progress_cb=progress_cb,
                    )

                progress_bar.progress(1.0, text="✅ Analysis complete!")
                st.session_state.summary = summary
                st.session_state.move_index = -1
                st.rerun()

            except RuntimeError as e:
                st.error(f"Engine error: {e}")
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                raise

else:
    # ── Main review layout ────────────────────────────────────────────────────
    summary = st.session_state.summary
    move_index = st.session_state.move_index

    col_board, col_center, col_right = st.columns([0.32, 0.36, 0.32])

    with col_board:
        st.markdown(
            '<div style="color:#64748b;font-size:0.72rem;font-weight:700;letter-spacing:0.08em;'
            'margin-bottom:8px;">BOARD</div>',
            unsafe_allow_html=True,
        )
        render_board_panel(summary, move_index)

    with col_center:
        st.markdown(
            '<div style="color:#64748b;font-size:0.72rem;font-weight:700;letter-spacing:0.08em;'
            'margin-bottom:4px;">EVALUATION</div>',
            unsafe_allow_html=True,
        )
        render_eval_graph(summary, move_index)

        st.markdown(
            '<div style="color:#64748b;font-size:0.72rem;font-weight:700;letter-spacing:0.08em;'
            'margin-bottom:6px;margin-top:4px;">MOVES</div>',
            unsafe_allow_html=True,
        )
        render_move_list(summary, move_index)

    with col_right:
        render_analysis_panel(summary, move_index)

    # ── Keyboard shortcut hint ────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;color:#1e293b;font-size:0.75rem;margin-top:8px;">
        Use ◀ ▶ buttons or click moves to navigate
    </div>
    """, unsafe_allow_html=True)
