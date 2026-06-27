"""Unit tests for the Phase 5 position encoder."""

from __future__ import annotations

import chess
import numpy as np

from player_model.encoding import VECTOR_DIM, encode_position


def test_vector_shape_and_range():
    vec = encode_position(chess.STARTING_FEN)
    assert vec.shape == (VECTOR_DIM,)
    assert vec.dtype == np.float32
    # Everything is normalised to [-1, 1] (only eval_cp can go negative).
    assert vec.min() >= -1.0 - 1e-6
    assert vec.max() <= 1.0 + 1e-6


def test_deterministic():
    a = encode_position(chess.STARTING_FEN)
    b = encode_position(chess.STARTING_FEN)
    assert np.array_equal(a, b)


def test_distinct_positions_differ():
    start = encode_position(chess.STARTING_FEN)
    after_e4 = encode_position("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    assert not np.array_equal(start, after_e4)


def test_material_and_phase_signal():
    # White is a whole queen up -> static eval dimension is clearly positive.
    queen_up = encode_position("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    # eval_context occupies indices 36..39; eval_cp is the first of those.
    eval_idx = 12 + 16 + 4 + 4
    assert queen_up[eval_idx] > 0.0

    # A bare-kings position reads as an endgame (game_phase == 1.0).
    endgame = encode_position("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert endgame[eval_idx + 1] == 1.0


def test_side_to_move_dimension():
    eval_idx = 12 + 16 + 4 + 4
    white_to_move = encode_position(chess.STARTING_FEN)
    black_to_move = encode_position(
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    )
    assert white_to_move[eval_idx + 3] == 1.0
    assert black_to_move[eval_idx + 3] == 0.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
