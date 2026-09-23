from jevtetris.board import (
    EMPTY_BOARD,
    HEIGHT,
    ROTATIONS,
    WIDTH,
    Bag,
    Game,
    Move,
    bumpiness,
    can_spawn,
    column_heights,
    count_holes,
    deepest_well,
    place,
    placements,
    shape_rows,
)


def board_from(rows: list[str]) -> tuple[str, ...]:
    """A board given as its bottom rows, top row of the list first."""
    assert all(len(r) == WIDTH for r in rows)
    return tuple(["." * WIDTH] * (HEIGHT - len(rows)) + rows)


def test_rotation_counts_match_the_pieces():
    counts = {p: len(r) for p, r in ROTATIONS.items()}
    assert counts == {"I": 2, "O": 1, "T": 4, "S": 2, "Z": 2, "J": 4, "L": 4}
    assert shape_rows(ROTATIONS["T"][0]) == [".#.", "###"]
    assert shape_rows(ROTATIONS["T"][1]) == ["#.", "##", "#."]


def test_board_features():
    board = board_from(
        [
            "#.........",
            "#.......##",
            "#.#.....##",
        ]
    )
    assert column_heights(board) == [3, 0, 1, 0, 0, 0, 0, 0, 2, 2]
    assert count_holes(board) == 0
    assert bumpiness([3, 0, 1, 0, 0, 0, 0, 0, 2, 2]) == 3 + 1 + 1 + 2
    assert deepest_well([3, 0, 1, 0, 0, 0, 0, 0, 2, 2]) == 1  # column 1 sits 1 below its lower neighbour
    holey = board_from(["##........", ".#........"])
    assert count_holes(holey) == 1


def test_place_clears_full_rows_and_keeps_the_rest():
    board = board_from(["#########.", "#.........", "#########."])
    after, cleared = place(board, "I", ROTATIONS["I"][1], HEIGHT - 4, 9)
    assert cleared == 2
    assert after[-1] == "#........I"
    assert after[-2] == ".........I"
    assert after[0] == "." * WIDTH


def test_placements_drop_straight_down_and_cover_every_column():
    found = placements(EMPTY_BOARD, "O")
    assert len(found) == WIDTH - 1
    assert all(p.landing_height == 1 for p in found)
    assert all(p.cleared == 0 and p.new_holes == 0 for p in found)
    assert {p.columns for p in found} == {(c, c + 1) for c in range(WIDTH - 1)}


def test_placement_that_creates_a_hole_says_so():
    board = board_from(["...#......"])
    over_the_bump = [p for p in placements(board, "I") if p.rotation == 0 and p.columns == (2, 5)]
    assert len(over_the_bump) == 1
    assert over_the_bump[0].new_holes == 3  # the bar rests on the bump, leaving 3 empty cells under it


def test_a_piece_cannot_slide_through_a_wall_that_reaches_the_top():
    board = board_from([".......#.."] * HEIGHT)  # column 7 is full, top to bottom
    reachable = {p.columns for p in placements(board, "O")}
    assert reachable == {(c, c + 1) for c in range(6)}  # spawns at 4-5, can reach left, never past the wall


def test_game_applies_moves_and_ends_when_nothing_can_spawn():
    bag = Bag(seed=7)
    game = Game.new(bag)
    assert len(game.queue) == 3 and game.hold is None
    moves = game.moves()
    hold_moves = [m for m in moves if m.hold]
    assert hold_moves and all(m.placement.piece == game.queue[0] for m in hold_moves)

    played = game.apply(hold_moves[0], bag)
    assert played.hold == game.current
    assert played.pieces == 1 and played.current == game.queue[1]
    assert len(played.queue) == 3

    tall = Game(board=board_from(["#####....."] * HEIGHT), current="I", queue=("O", "T", "S"), hold=None)
    assert not can_spawn(tall.board, "I")


def test_scoring_scales_with_level():
    bag = Bag(seed=3)
    game = Game(board=board_from(["#########."] * 4), current="I", queue=("O", "T", "S"), hold=None, lines=10)
    tetris = next(m for m in game.moves() if not m.hold and m.placement.cleared == 4)
    after = game.apply(tetris, bag)
    assert after.lines == 14 and after.score == 800 * 2
    assert after.board == EMPTY_BOARD
    assert isinstance(tetris, Move)
