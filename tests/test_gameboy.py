from jevtetris.board import ROTATIONS, Game, placements
from jevtetris.gameboy import BLANK, GB_HEIGHT, board_cells, board_from, cells_of, identify


def test_identify_every_orientation_of_every_piece():
    for piece, orientations in ROTATIONS.items():
        for rotation, cells in enumerate(orientations):
            shifted = {(r + 3, c + 5) for r, c in cells}
            assert identify(shifted) == (piece, rotation)


def test_identify_rejects_non_tetrominoes():
    assert identify(set()) is None
    assert identify({(0, 0), (0, 1), (0, 2)}) is None
    assert identify({(0, 0), (0, 2), (1, 0), (1, 2)}) is None


def test_screen_cells_round_trip_through_a_board():
    area = [[BLANK] * 10 for _ in range(GB_HEIGHT)]
    area[17][0] = area[17][1] = 130
    area[16][0] = 131
    cells = cells_of(area)
    assert cells == {(17, 0), (17, 1), (16, 0)}
    board = board_from(cells)
    assert len(board) == GB_HEIGHT
    assert board_cells(board) == cells


def test_game_boy_game_has_no_hold_and_an_18_row_board():
    board = board_from(set())
    game = Game(board=board, current="T", queue=("I",), hold=None, can_hold=False)
    moves = game.moves()
    assert moves and not any(m.hold for m in moves)
    assert all(len(m.placement.board) == GB_HEIGHT for m in moves)
    assert all(m.placement.landing_height == 1 for m in moves)
    floor = placements(board, "I")
    assert all(p.board[-1].count("I") == 4 for p in floor if p.rotation == 0)
