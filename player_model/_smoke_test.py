"""Ad-hoc smoke test (not part of the package). Run:
    .venv/Scripts/python.exe -m player_model._smoke_test
Exercises the parser, DB layer and a real Stockfish analysis at low depth.
"""

import os
import tempfile

os.environ.setdefault("STOCKFISH_DEPTH", "8")  # keep the test fast
os.environ["PM_DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.gettempdir(), "pm_smoke.db"
)

import chess  # noqa: E402

from player_model.db import SessionLocal, init_db  # noqa: E402
from player_model import repository as repo  # noqa: E402
from player_model.pgn_ingest import parse_pgn  # noqa: E402
from player_model.analyzer import analyse_position, find_stockfish  # noqa: E402
import chess.engine  # noqa: E402

PGN = """[Event "Test"]
[Site "?"]
[Date "2024.01.01"]
[White "alice"]
[Black "bob"]
[Result "1-0"]
[TimeControl "600"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 1-0

[Event "Test2"]
[White "bob"]
[Black "alice"]
[Result "0-1"]
[TimeControl "180+2"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 0-1
"""


def main():
    init_db()

    # --- Parser ---
    games = parse_pgn(PGN, username="alice")
    print(f"parsed games: {len(games)}")
    assert len(games) == 2, games
    g0 = games[0]
    print(f"  game0 color_played={g0.color_played} opp={g0.opponent} "
          f"tc={g0.time_control} result={g0.result} moves={len(g0.moves)}")
    assert g0.color_played == "white"
    assert games[1].color_played == "black"
    assert g0.moves[0].uci == "e2e4"
    assert g0.moves[0].turn == "white"

    # --- DB layer + dedup ---
    db = SessionLocal()
    player = repo.get_or_create_player(db, "alice")
    db.commit()
    game_row = repo.get_or_create_game(db, player.id, g0)
    db.commit()
    again = repo.get_or_create_game(db, player.id, g0)  # same hash -> same row
    assert again.id == game_row.id, "dedup failed"
    print(f"  player_id={player.id} game_id={game_row.id} (dedup ok)")

    # --- Real engine analysis on alice's (white) moves only ---
    eng = chess.engine.SimpleEngine.popen_uci(find_stockfish())
    try:
        batch = []
        for mv in g0.moves:
            if mv.turn != g0.color_played:
                continue  # skip opponent's moves
            board = chess.Board(mv.fen_before)
            res = analyse_position(eng, board, chess.Move.from_uci(mv.uci), depth=8)
            assert isinstance(res.eval_before, int)
            assert res.cpl is None or res.cpl >= 0
            assert len(res.candidates) >= 1
            batch.append((mv.ply, res, mv.clock_seconds))
        repo.flush_positions(db, game_row.id, batch)
    finally:
        eng.quit()

    saved = repo.max_saved_ply(db, game_row.id)
    print(f"  analysed white plies, max_saved_ply={saved}")
    assert saved > 0
    sample = batch[2][1]
    print(f"  sample: move={sample.move_played} best={sample.best_move} "
          f"eval_before={sample.eval_before} eval_after={sample.eval_after} "
          f"cpl={sample.cpl} mistake={sample.is_mistake} blunder={sample.is_blunder}")

    db.close()
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
