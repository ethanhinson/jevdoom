"""Turn a game into the state Jev reads and the options it chooses between."""

from __future__ import annotations

from .board import WIDTH, Game, Move, column_heights, count_holes, shape_rows

PIECE_NAMES = {
    "I": "I (the straight four-long bar)",
    "O": "O (the 2x2 square)",
    "T": "T",
    "S": "S",
    "Z": "Z",
    "J": "J",
    "L": "L",
}


def side(low: int, high: int) -> str:
    centre = (low + high) / 2
    if high == WIDTH - 1 and low == 0:
        return "the full width"
    if centre < 3:
        return "left side"
    if centre > WIDTH - 4:
        return "right side"
    return "middle"


def describe_move(move: Move) -> dict:
    p = move.placement
    low, high = p.columns
    where = f"{p.piece} in columns {low}-{high} ({side(low, high)})"
    if move.hold:
        where = f"hold, play {where}"
    result = (
        f"clears {p.cleared} line{'s' if p.cleared != 1 else ''}, "
        f"holes {p.holes} ({p.new_holes:+d}), stack height {p.max_height}, "
        f"bumpiness {p.bumpiness}, deepest well {p.well}"
    )
    return {
        "where": where,
        "shape": "/".join(shape_rows(p.cells)),
        "lands": f"resting {p.landing_height} row{'s' if p.landing_height != 1 else ''} above the floor",
        "after": result,
    }


def describe_state(game: Game) -> dict:
    heights = column_heights(game.board)
    return {
        "board": {
            "rows_top_to_bottom": list(game.board),
            "legend": "'.' is empty; a letter is a locked cell of that piece",
            "column_heights_left_to_right": heights,
            "stack_height": max(heights),
            "holes": count_holes(game.board),
            "rows_free_above_stack": len(game.board) - max(heights),
        },
        "current_piece": PIECE_NAMES[game.current],
        "held_piece": PIECE_NAMES[game.hold] if game.hold else None,
        "next_pieces": [PIECE_NAMES[p] for p in game.queue],
        "hold_rule": (
            f"Options starting with 'hold' put the current piece in hold and play "
            f"{PIECE_NAMES[game.alternate]} instead"
            + ("" if game.hold else " (the next piece, since nothing is held yet)")
        ),
        "score": game.score,
        "lines": game.lines,
        "level": game.level,
    }


def move_keys(moves: list[Move]) -> dict[str, Move]:
    """Option keys for a Choice, in the order the moves were listed."""
    keys: dict[str, Move] = {}
    now = held = 0
    for move in moves:
        if move.hold:
            held += 1
            keys[f"hold_{held}"] = move
        else:
            now += 1
            keys[f"now_{now}"] = move
    return keys
