from jevtetris.board import EMPTY_BOARD, Bag, Game
from jevtetris.brain import safest
from jevtetris.describe import describe_move, describe_state, move_keys, side


def test_side_names_are_sensible():
    assert side(0, 1) == "left side"
    assert side(4, 5) == "middle"
    assert side(8, 9) == "right side"
    assert side(0, 9) == "the full width"


def test_state_and_options_read_as_words():
    game = Game(board=EMPTY_BOARD, current="T", queue=("I", "O", "S"), hold="L")
    state = describe_state(game)
    assert state["current_piece"] == "T"
    assert state["held_piece"] == "L"
    assert state["board"]["stack_height"] == 0
    assert "hold" in state["hold_rule"] and "L" in state["hold_rule"]

    keys = move_keys(game.moves())
    assert list(keys)[:2] == ["now_1", "now_2"]
    assert any(k.startswith("hold_") for k in keys)
    option = describe_move(keys["now_1"])
    assert option["where"].startswith("T in columns 0-2")
    assert option["shape"] == ".#./###"
    assert option["after"].startswith("clears 0 lines, holes 0 (+0)")
    held = describe_move(next(m for m in keys.values() if m.hold))
    assert held["where"].startswith("hold, play L")


def test_safest_fallback_avoids_holes():
    game = Game.new(Bag(seed=5))
    move = safest(game.moves())
    assert move.placement.new_holes == 0
