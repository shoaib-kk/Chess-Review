from __future__ import annotations

import io
from collections import Counter
from statistics import mean
from typing import Any

import chess.pgn

from opening_recognition import recognise_opening

from .cache import ttl_lru_cache
from .chesscom_client import get_recent_games
from .opening_names import extract_opening_family, extract_variation

DRAW_RESULTS = {
    "agreed",
    "repetition",
    "stalemate",
    "insufficient",
    "50move",
    "timevsinsufficient",
}

CATEGORY_LABELS = {
    "white": "White Repertoire",
    "black_vs_e4": "Black Repertoire vs e4",
    "black_vs_d4": "Black Repertoire vs d4",
    "black_vs_other": "Black Repertoire vs Other",
}


def _safe_mean(values: list[float]) -> float | None:
    return round(mean(values), 1) if values else None


def _pct(part: int | float, whole: int | float) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def _read_game(pgn: str) -> chess.pgn.Game | None:
    try:
        return chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None


def _move_sans(game: chess.pgn.Game | None, limit: int = 30) -> list[str]:
    if not game:
        return []
    board = game.board()
    sans: list[str] = []
    for move in game.mainline_moves():
        if len(sans) >= limit:
            break
        try:
            sans.append(board.san(move).rstrip("!?"))
            board.push(move)
        except Exception:
            break
    return sans


def _opening_info(game: chess.pgn.Game | None) -> tuple[str, str]:
    if not game:
        return "Unknown", "?"
    opening = recognise_opening(game)
    if opening:
        return opening.name, opening.eco or "?"
    return game.headers.get("Opening", "Unknown"), game.headers.get("ECO", "?")


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


def _result_bucket(score: float) -> str:
    if score == 1.0:
        return "win"
    if score == 0.5:
        return "draw"
    return "loss"


def _rating(game: chess.pgn.Game | None, color: str | None) -> int | None:
    if not game or not color:
        return None
    raw = game.headers.get("WhiteElo" if color == "White" else "BlackElo")
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


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


def _category(color: str, sans: list[str]) -> str:
    if color == "White":
        return "white"
    first = sans[0] if sans else ""
    if first == "e4":
        return "black_vs_e4"
    if first == "d4":
        return "black_vs_d4"
    return "black_vs_other"


def _opponent_response(color: str, sans: list[str]) -> str | None:
    if color == "White":
        return sans[1] if len(sans) > 1 else None
    return sans[2] if len(sans) > 2 else None


def _record_from_game(raw: dict[str, Any], username: str) -> dict[str, Any] | None:
    color = _user_color(raw, username)
    if not color:
        return None

    pgn_game = _read_game(raw["pgn"])
    sans = _move_sans(pgn_game, limit=40)
    ply_count = len(list(pgn_game.mainline_moves())) if pgn_game else 0
    opening_name, eco = _opening_info(pgn_game)
    opening_family = extract_opening_family(opening_name)
    variation = extract_variation(opening_name)
    player_result = raw["white_result"] if color == "White" else raw["black_result"]
    score = _score_for_result(player_result)
    result = _result_bucket(score)
    rating = _rating(pgn_game, color)
    accuracy = _estimated_accuracy(score, ply_count, rating)
    cp_loss = _estimated_cp_loss(accuracy)
    opponent = raw["black_username"] if color == "White" else raw["white_username"]

    return {
        "opening_name": opening_name,
        "opening_family": opening_family,
        "variation": variation,
        "eco": eco,
        "category": _category(color, sans),
        "color": color,
        "score": score,
        "result": result,
        "accuracy": accuracy,
        "cp_loss": cp_loss,
        "game_length": round(ply_count / 2, 1),
        "date": raw.get("date"),
        "end_time": raw.get("end_time") or 0,
        "opponent": opponent,
        "url": raw.get("url"),
        "time_class": raw.get("time_class"),
        "rated": raw.get("rated"),
        "opponent_response": _opponent_response(color, sans),
    }


def _new_group(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "opening_name": record["opening_name"],
        "opening_family": record["opening_family"],
        "eco": record["eco"],
        "category": record["category"],
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "score": 0.0,
        "accuracies": [],
        "cp_losses": [],
        "lengths": [],
        "records": [],
        "responses": Counter(),
        "variations": Counter(),
        "variation_ecos": {},
    }


def _example_game(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": record["date"],
        "opponent": record["opponent"],
        "color": record["color"],
        "result": record["result"],
        "accuracy": record["accuracy"],
        "cp_loss": record["cp_loss"],
        "game_length": record["game_length"],
        "url": record["url"],
    }


def _opening_row(data: dict[str, Any], total_games: int) -> dict[str, Any]:
    records = sorted(data["records"], key=lambda item: item["end_time"], reverse=True)
    result_counts = Counter(item["result"] for item in records)
    best = sorted(records, key=lambda item: (item["score"], item["accuracy"]), reverse=True)[:5]
    worst = sorted(records, key=lambda item: (item["score"], item["accuracy"]))[:5]

    return {
        "id": f"{data['category']}::{data['opening_family']}",
        "opening_name": data["opening_family"],
        "opening_family": data["opening_family"],
        "variation": None,
        "eco": data["eco"],
        "category": data["category"],
        "games": data["games"],
        "frequency": _pct(data["games"], total_games),
        "wins": data["wins"],
        "losses": data["losses"],
        "draws": data["draws"],
        "win_rate": _pct(data["wins"], data["games"]),
        "avg_accuracy": _safe_mean(data["accuracies"]),
        "avg_cp_loss": _safe_mean(data["cp_losses"]),
        "avg_game_length": _safe_mean(data["lengths"]),
        "recent_games": [_example_game(item) for item in records[:8]],
        "common_opponent_responses": [
            {"move": move, "games": count, "frequency": _pct(count, data["games"])}
            for move, count in data["responses"].most_common(8)
        ],
        "variations": [
            {
                "variation": variation,
                "games": count,
                "frequency": _pct(count, data["games"]),
                "eco": data["variation_ecos"].get(variation, data["eco"]),
            }
            for variation, count in data["variations"].most_common()
        ],
        "typical_results": [
            {"result": result, "games": count, "frequency": _pct(count, data["games"])}
            for result, count in result_counts.most_common()
        ],
        "best_example_games": [_example_game(item) for item in best],
        "worst_example_games": [_example_game(item) for item in worst],
    }


def _aggregate(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, dict[str, dict[str, Any]]] = {
        "white": {},
        "black_vs_e4": {},
        "black_vs_d4": {},
        "black_vs_other": {},
    }
    category_totals = Counter(item["category"] for item in records)

    for record in records:
        key = record["opening_family"]
        category_groups = buckets[record["category"]]
        if key not in category_groups:
            category_groups[key] = _new_group(record)

        group = category_groups[key]
        group["games"] += 1
        group["score"] += record["score"]
        if record["result"] == "win":
            group["wins"] += 1
        elif record["result"] == "draw":
            group["draws"] += 1
        else:
            group["losses"] += 1
        group["accuracies"].append(record["accuracy"])
        group["cp_losses"].append(record["cp_loss"])
        group["lengths"].append(record["game_length"])
        group["records"].append(record)
        variation = record["variation"] or "Main line / Other"
        group["variations"][variation] += 1
        group["variation_ecos"].setdefault(variation, record["eco"])
        if record["opponent_response"]:
            group["responses"][record["opponent_response"]] += 1

    return {
        category: sorted(
            (_opening_row(group, max(1, category_totals[category])) for group in groups.values()),
            key=lambda row: (-row["games"], -row["win_rate"], row["opening_name"]),
        )
        for category, groups in buckets.items()
    }


def _aggregate_by_color(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, dict[str, dict[str, Any]]] = {"white": {}, "black": {}}
    color_totals = Counter("white" if item["color"] == "White" else "black" for item in records)

    for record in records:
        color_key = "white" if record["color"] == "White" else "black"
        key = record["opening_family"]
        color_groups = buckets[color_key]
        if key not in color_groups:
            color_groups[key] = _new_group(record)
            color_groups[key]["category"] = color_key

        group = color_groups[key]
        group["games"] += 1
        group["score"] += record["score"]
        if record["result"] == "win":
            group["wins"] += 1
        elif record["result"] == "draw":
            group["draws"] += 1
        else:
            group["losses"] += 1
        group["accuracies"].append(record["accuracy"])
        group["cp_losses"].append(record["cp_loss"])
        group["lengths"].append(record["game_length"])
        group["records"].append(record)
        variation = record["variation"] or "Main line / Other"
        group["variations"][variation] += 1
        group["variation_ecos"].setdefault(variation, record["eco"])
        if record["opponent_response"]:
            group["responses"][record["opponent_response"]] += 1

    return {
        color: sorted(
            (_opening_row(group, max(1, color_totals[color])) for group in groups.values()),
            key=lambda row: (-row["win_rate"], -row["games"], row["opening_name"]),
        )
        for color, groups in buckets.items()
    }


def _qualified(rows: list[dict[str, Any]], minimum_games: int = 10) -> list[dict[str, Any]]:
    return [row for row in rows if row["games"] >= minimum_games]


def _recommendations(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    qualified = _qualified(rows)
    strongest = sorted(
        qualified,
        key=lambda row: (row["win_rate"], row["avg_accuracy"] or 0, row["games"]),
        reverse=True,
    )[:5]
    weakest = sorted(
        qualified,
        key=lambda row: (row["win_rate"], row["avg_accuracy"] or 0, -row["games"]),
    )[:5]
    enough_data = len(qualified) >= 2

    if not enough_data:
        return {
            "enough_data": False,
            "strongest_openings": [],
            "weakest_openings": [],
            "continue_playing": [],
            "needs_improvement": [],
            "consider_reviewing": [],
        }

    review = sorted(
        qualified,
        key=lambda row: (-(row["games"]), row["avg_accuracy"] or 100, row["win_rate"]),
    )[:5]
    return {
        "enough_data": True,
        "strongest_openings": strongest,
        "weakest_openings": weakest,
        "continue_playing": strongest[:3],
        "needs_improvement": weakest[:3],
        "consider_reviewing": review[:3],
    }


def _window_records(records: list[dict[str, Any]], window: str) -> list[dict[str, Any]]:
    if window == "last_30":
        return records[:30]
    if window == "last_90":
        return records[:90]
    if window == "last_180":
        return records[:180]
    return records


def _trend_window(records: list[dict[str, Any]], window: str) -> dict[str, Any]:
    window_records = _window_records(records, window)
    rows = [row for category_rows in _aggregate(window_records).values() for row in category_rows]
    return {
        "games": len(window_records),
        "openings": sorted(rows, key=lambda row: (-row["games"], row["opening_name"]))[:12],
    }


def _trends(records: list[dict[str, Any]]) -> dict[str, Any]:
    points = [
        {
            "date": record["date"],
            "opening_name": record["opening_family"],
            "opening_family": record["opening_family"],
            "variation": record["variation"],
            "eco": record["eco"],
            "category": record["category"],
            "accuracy": record["accuracy"],
            "win_rate": record["score"] * 100,
            "result": record["result"],
            "game_index": index + 1,
        }
        for index, record in enumerate(reversed(records))
    ]
    return {
        "windows": {
            "last_30": _trend_window(records, "last_30"),
            "last_90": _trend_window(records, "last_90"),
            "last_180": _trend_window(records, "last_180"),
            "all": _trend_window(records, "all"),
        },
        "points": points,
    }


def build_opening_repertoire(
    username: str,
    games: list[dict[str, Any]],
    limit: int,
    time_class: str | None = None,
    rated_only: bool = False,
) -> dict[str, Any]:
    filtered = games
    if time_class:
        filtered = [game for game in filtered if game.get("time_class") == time_class]
    if rated_only:
        filtered = [game for game in filtered if game.get("rated")]

    records = []
    for raw in filtered:
        record = _record_from_game(raw, username)
        if record:
            records.append(record)
    records.sort(key=lambda item: item["end_time"], reverse=True)

    repertoire = _aggregate(records)
    color_repertoire = _aggregate_by_color(records)
    all_rows = [row for category_rows in color_repertoire.values() for row in category_rows]
    strongest = max(_qualified(all_rows, minimum_games=1), key=lambda row: (row["win_rate"], row["avg_accuracy"] or 0), default=None)
    weakest = min(_qualified(all_rows, minimum_games=1), key=lambda row: (row["win_rate"], row["avg_accuracy"] or 100), default=None)

    return {
        "username": username,
        "filters": {"limit": limit, "time_class": time_class, "rated_only": rated_only},
        "summary": {
            "total_games": len(records),
            "openings_tracked": len(all_rows),
            "strongest_opening": strongest,
            "weakest_opening": weakest,
        },
        "repertoire": {
            "white": color_repertoire["white"],
            "black": color_repertoire["black"],
            "black_vs_e4": repertoire["black_vs_e4"],
            "black_vs_d4": repertoire["black_vs_d4"],
            "black_vs_other": repertoire["black_vs_other"],
        },
        "recommendations": _recommendations(all_rows),
        "trends": _trends(records),
        "category_labels": CATEGORY_LABELS,
    }


@ttl_lru_cache(maxsize=32, ttl_seconds=300)
def get_opening_repertoire(
    username: str,
    limit: int = 500,
    time_class: str | None = None,
    rated_only: bool = False,
) -> dict[str, Any]:
    normalized = username.strip()
    limit = max(1, min(limit, 500))
    games = get_recent_games(normalized, limit=limit)
    return build_opening_repertoire(
        username=normalized,
        games=games,
        limit=limit,
        time_class=time_class,
        rated_only=rated_only,
    )
