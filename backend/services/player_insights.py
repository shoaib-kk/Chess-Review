from __future__ import annotations

import io
import re
from collections import Counter, defaultdict
from functools import lru_cache
from statistics import mean
from typing import Any

import chess
import chess.pgn

from .chesscom_client import get_recent_games

DRAW_RESULTS = {
    "agreed",
    "repetition",
    "stalemate",
    "insufficient",
    "50move",
    "timevsinsufficient",
}


def _safe_mean(values: list[float]) -> float | None:
    return round(mean(values), 1) if values else None


def _pct(part: int | float, whole: int | float) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def _slug_title(value: str | None) -> str:
    if not value:
        return "Unknown"
    tail = value.rstrip("/").split("/")[-1]
    tail = re.sub(r"^\d+-", "", tail)
    return tail.replace("-", " ").replace("_", " ").title() or "Unknown"


def _read_game(pgn: str) -> chess.pgn.Game | None:
    try:
        return chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None


def _mainline(game: chess.pgn.Game | None) -> list[chess.Move]:
    if not game:
        return []
    return list(game.mainline_moves())


def _opening_info(game: chess.pgn.Game | None) -> tuple[str, str]:
    if not game:
        return "Unknown", "?"
    headers = game.headers
    eco = headers.get("ECO", "?")
    opening = headers.get("Opening") or _slug_title(headers.get("ECOUrl"))
    return opening, eco


def _user_color(game: dict[str, Any], username: str) -> str | None:
    normalized = username.casefold()
    if game["white_username"].casefold() == normalized:
        return "White"
    if game["black_username"].casefold() == normalized:
        return "Black"
    return None


def _score_for_result(result: str | None) -> float:
    if result == "win":
        return 1.0
    if result in DRAW_RESULTS:
        return 0.5
    return 0.0


def _estimated_accuracy(score: float, ply_count: int, rating: int | None) -> float:
    base = 73 + score * 14
    if ply_count >= 80:
        base -= 3
    elif ply_count <= 25:
        base += 2
    if rating:
        base += min(6, max(-4, (rating - 1200) / 250))
    return round(max(45, min(96, base)), 1)


def _estimated_cp_loss(accuracy: float) -> float:
    return round(max(8, (100 - accuracy) * 4.7), 1)


def _rating(game: chess.pgn.Game | None, color: str | None) -> int | None:
    if not game or not color:
        return None
    raw = game.headers.get("WhiteElo" if color == "White" else "BlackElo")
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _phase_bucket(ply_count: int, result_score: float) -> str | None:
    if result_score >= 0.5:
        return None
    if ply_count <= 20:
        return "Opening"
    if ply_count <= 60:
        return "Middlegame"
    return "Endgame"


def _move_sans(game: chess.pgn.Game | None, limit: int = 12) -> list[str]:
    if not game:
        return []
    board = game.board()
    sans = []
    for move in game.mainline_moves():
        try:
            sans.append(board.san(move))
            board.push(move)
        except Exception:
            break
        if len(sans) >= limit:
            break
    return sans


def _response_bucket(game: chess.pgn.Game | None) -> tuple[str | None, str | None]:
    sans = _move_sans(game, limit=2)
    if len(sans) < 2:
        return None, None
    first = sans[0].replace("+", "").replace("#", "")
    response = sans[1].replace("+", "").replace("#", "")
    if first in {"e4", "d4"}:
        return first, response
    return first, response


def _mistake_categories(game: chess.pgn.Game | None, color: str | None, score: float, ply_count: int) -> Counter:
    counts: Counter[str] = Counter()
    if not game or not color:
        return counts

    if score >= 0.5:
        return counts

    sans = _move_sans(game, limit=80)
    joined = " ".join(sans).lower()

    if ply_count <= 20:
        counts["Opening mistakes"] += 2
    if ply_count >= 70:
        counts["Endgame mistakes"] += 1
    if "o-o" not in joined and "o-o-o" not in joined and ply_count > 20:
        counts["King safety mistakes"] += 1
    if any(token in joined for token in ["x", "+", "#"]):
        counts["Missed tactics"] += 1
    if any(token in joined for token in ["n", "q"]) and score == 0:
        counts["Forks"] += 1
    if any(token in joined for token in ["b", "r", "q"]) and score == 0:
        counts["Pins"] += 1
    if score == 0 and ply_count <= 45:
        counts["Hanging pieces"] += 2
    if score == 0 and ply_count > 45:
        counts["Skewers"] += 1

    return counts


def _counter_rows(counter: Counter[str], ordered_labels: list[str] | None = None) -> list[dict[str, Any]]:
    if ordered_labels is None:
        items = counter.most_common()
    else:
        items = [(label, counter.get(label, 0)) for label in ordered_labels]
    total = sum(count for _, count in items)
    return [
        {"category": category, "count": count, "percentage": _pct(count, total)}
        for category, count in items
    ]


def _opening_rows(groups: dict[str, dict], total_games: int) -> list[dict[str, Any]]:
    rows = []
    for key, data in groups.items():
        rows.append(
            {
                "opening_name": data["opening_name"],
                "eco": data["eco"],
                "games": data["games"],
                "frequency": _pct(data["games"], total_games),
                "win_rate": _pct(data["score"], data["games"]),
                "avg_accuracy": _safe_mean(data["accuracies"]),
                "avg_cp_loss": _safe_mean(data["cp_losses"]),
            }
        )
    return sorted(rows, key=lambda row: (-row["games"], row["opening_name"]))[:12]


def _trend_window(records: list[dict[str, Any]], size: int) -> dict[str, Any]:
    window = records[:size]
    if not window:
        return {"games": 0, "win_rate": 0, "avg_accuracy": None, "avg_cp_loss": None, "blunders": 0}
    return {
        "games": len(window),
        "win_rate": _pct(sum(item["score"] for item in window), len(window)),
        "avg_accuracy": _safe_mean([item["accuracy"] for item in window]),
        "avg_cp_loss": _safe_mean([item["cp_loss"] for item in window]),
        "blunders": sum(item["blunder_proxy"] for item in window),
    }


def _trend_notes(records: list[dict[str, Any]]) -> list[str]:
    last_30 = _trend_window(records, 30)
    previous_30 = _trend_window(records[30:60], 30)
    notes = []
    if previous_30["games"]:
        if (last_30["avg_accuracy"] or 0) > (previous_30["avg_accuracy"] or 0) + 2:
            notes.append("Accuracy improving over the last 30 games.")
        elif (last_30["avg_accuracy"] or 0) + 2 < (previous_30["avg_accuracy"] or 0):
            notes.append("Accuracy declining over the last 30 games.")
        if last_30["blunders"] < previous_30["blunders"]:
            notes.append("Blunders decreasing recently.")
    if not notes:
        notes.append("Performance is relatively stable across recent games.")
    return notes


def _profile(records: list[dict[str, Any]], white_openings: list[dict], black_openings: list[dict], mistake_rows: list[dict]) -> dict[str, Any]:
    avg_length = _safe_mean([item["ply_count"] / 2 for item in records]) or 0
    tactical = sum(item["captures_checks"] for item in records) / max(1, len(records))
    aggression = "aggressive" if tactical > 9 else "balanced" if tactical > 5 else "positional"
    tempo = "longer" if avg_length > 42 else "shorter" if avg_length < 25 else "medium-length"
    preferred = (white_openings[:1] or black_openings[:1] or [{"opening_name": "varied openings"}])[0]["opening_name"]

    summary = (
        f"Prefers {aggression} games with {tempo} battles. "
        f"Most common opening family is {preferred}."
    )

    return {
        "style": aggression,
        "position_preference": "open" if tactical > 7 else "closed",
        "average_game_length": round(avg_length, 1),
        "preferred_openings": [row["opening_name"] for row in white_openings[:3]],
        "summary": summary,
        "top_weakness": mistake_rows[0]["category"] if mistake_rows else None,
    }


def _recommendations(strengths: list[str], weaknesses: list[str], mistake_rows: list[dict], worst_opening: str | None) -> list[str]:
    recs = []
    if mistake_rows:
        top = mistake_rows[0]["category"]
        if top == "Endgame mistakes":
            recs.append("Study rook and basic pawn endgames.")
        elif top == "Opening mistakes":
            recs.append("Review your first 10 moves in your most-played openings.")
        elif top == "King safety mistakes":
            recs.append("Prioritize king safety and earlier castling in review sessions.")
        elif top == "Missed tactics":
            recs.append("Add short daily tactical puzzle sessions focused on forcing moves.")
        elif top == "Hanging pieces":
            recs.append("Before moving, scan whether any piece is undefended or newly attacked.")
    if worst_opening:
        recs.append(f"Review model games and common plans in {worst_opening}.")
    if not recs:
        recs.append("Keep reviewing losses and compare your candidate moves with the engine recommendation.")
    return recs[:4]


@lru_cache(maxsize=32)
def get_player_insights(username: str, limit: int = 200, time_class: str | None = None, rated_only: bool = False) -> dict[str, Any]:
    limit = max(1, min(limit, 300))
    normalized = username.strip()
    games = get_recent_games(normalized, limit=limit)

    if time_class:
        games = [game for game in games if game.get("time_class") == time_class]
    if rated_only:
        games = [game for game in games if game.get("rated")]

    records: list[dict[str, Any]] = []
    white_groups: dict[str, dict] = {}
    black_groups: dict[str, dict] = {}
    e4_responses: Counter[str] = Counter()
    d4_responses: Counter[str] = Counter()
    mistake_counts: Counter[str] = Counter()
    phase_losses: Counter[str] = Counter()
    rating_points = []

    for raw in games:
        color = _user_color(raw, normalized)
        if not color:
            continue
        pgn_game = _read_game(raw["pgn"])
        moves = _mainline(pgn_game)
        ply_count = len(moves)
        opening_name, eco = _opening_info(pgn_game)
        player_result = raw["white_result"] if color == "White" else raw["black_result"]
        score = _score_for_result(player_result)
        rating = _rating(pgn_game, color)
        accuracy = _estimated_accuracy(score, ply_count, rating)
        cp_loss = _estimated_cp_loss(accuracy)
        sans = _move_sans(pgn_game, limit=80)
        captures_checks = sum(1 for san in sans if "x" in san or "+" in san or "#" in san)

        record = {
            "date": raw.get("date"),
            "end_time": raw.get("end_time"),
            "color": color,
            "score": score,
            "accuracy": accuracy,
            "cp_loss": cp_loss,
            "ply_count": ply_count,
            "rating": rating,
            "blunder_proxy": 1 if score == 0 and ply_count <= 45 else 0,
            "captures_checks": captures_checks,
            "opening": opening_name,
        }
        records.append(record)

        group_key = f"{eco}:{opening_name}"
        target = white_groups if color == "White" else black_groups
        if group_key not in target:
            target[group_key] = {
                "opening_name": opening_name,
                "eco": eco,
                "games": 0,
                "score": 0.0,
                "accuracies": [],
                "cp_losses": [],
            }
        target[group_key]["games"] += 1
        target[group_key]["score"] += score
        target[group_key]["accuracies"].append(accuracy)
        target[group_key]["cp_losses"].append(cp_loss)

        first, response = _response_bucket(pgn_game)
        if color == "Black" and first == "e4" and response:
            e4_responses[response] += 1
        if color == "Black" and first == "d4" and response:
            d4_responses[response] += 1

        categories = _mistake_categories(pgn_game, color, score, ply_count)
        mistake_counts.update(categories)
        phase = _phase_bucket(ply_count, score)
        if phase:
            phase_losses[phase] += sum(categories.values()) or 1
        if rating and raw.get("date"):
            rating_points.append({"date": raw["date"], "rating": rating})

    total = len(records)
    white_records = [item for item in records if item["color"] == "White"]
    black_records = [item for item in records if item["color"] == "Black"]
    white_openings = _opening_rows(white_groups, max(1, len(white_records)))
    black_openings = _opening_rows(black_groups, max(1, len(black_records)))

    mistake_rows = _counter_rows(mistake_counts)
    phase_rows = _counter_rows(phase_losses, ["Opening", "Middlegame", "Endgame"])

    strongest = max(white_openings + black_openings, key=lambda row: row["win_rate"], default=None)
    weakest = min(white_openings + black_openings, key=lambda row: row["win_rate"], default=None)
    best_color = "White" if _pct(sum(item["score"] for item in white_records), len(white_records)) >= _pct(sum(item["score"] for item in black_records), len(black_records)) else "Black"
    lowest_phase = phase_losses.most_common(1)[0][0] if phase_losses else None

    strengths = [
        f"Best results come from {strongest['opening_name']}." if strongest else "Opening sample is still developing.",
        f"Best color: {best_color}.",
        "Highest accuracy phase appears to be the opening." if not lowest_phase or lowest_phase != "Opening" else "Middlegame resilience is a key strength.",
    ]
    weaknesses = [
        f"Worst opening family: {weakest['opening_name']}." if weakest else "Not enough opening data for a clear weakness.",
        f"Most common mistake: {mistake_rows[0]['category']}." if mistake_rows else "No recurring mistake category found.",
        f"Lowest-performing phase: {lowest_phase}." if lowest_phase else "No clear phase weakness found.",
    ]

    trend_points = [
        {
            "date": item["date"],
            "accuracy": item["accuracy"],
            "cp_loss": item["cp_loss"],
            "blunders": item["blunder_proxy"],
            "rating": item["rating"],
        }
        for item in reversed(records)
    ]

    profile = _profile(records, white_openings, black_openings, mistake_rows)

    return {
        "username": normalized,
        "filters": {"limit": limit, "time_class": time_class, "rated_only": rated_only},
        "summary": {
            "games_analyzed": total,
            "win_rate": _pct(sum(item["score"] for item in records), total),
            "white_win_rate": _pct(sum(item["score"] for item in white_records), len(white_records)),
            "black_win_rate": _pct(sum(item["score"] for item in black_records), len(black_records)),
            "average_accuracy": _safe_mean([item["accuracy"] for item in records]),
            "average_cp_loss": _safe_mean([item["cp_loss"] for item in records]),
            "average_game_length": _safe_mean([item["ply_count"] / 2 for item in records]),
        },
        "openings": {
            "as_white": white_openings,
            "as_black": black_openings,
            "responses_to_e4": [{"move": move, "games": count, "frequency": _pct(count, len(black_records))} for move, count in e4_responses.most_common(8)],
            "responses_to_d4": [{"move": move, "games": count, "frequency": _pct(count, len(black_records))} for move, count in d4_responses.most_common(8)],
        },
        "performance": {
            "last_30": _trend_window(records, 30),
            "last_90": _trend_window(records, 90),
            "last_180": _trend_window(records, 180),
            "trend_notes": _trend_notes(records),
            "trend_points": trend_points,
            "rating_points": list(reversed(rating_points)),
        },
        "mistakes": {
            "categories": mistake_rows,
            "by_phase": phase_rows,
            "by_type": mistake_rows,
            "top_weaknesses": mistake_rows[:3],
        },
        "profile": {
            **profile,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": _recommendations(strengths, weaknesses, mistake_rows, weakest["opening_name"] if weakest else None),
        },
    }
