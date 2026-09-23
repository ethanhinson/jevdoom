"""Play the real Game Boy Tetris in the PyBoy emulator. Everything is read off the screen tiles:
the locked board, the falling piece and the next piece; nothing depends on the game's memory layout
except PyBoy's own preview lookup."""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import ROTATIONS, WIDTH, Board, Cell, Game, Placement, empty_board

GB_HEIGHT = 18
BLANK = 47  # the empty tile in the play field
DEAD = 135  # the black tile the game fills the field with when it is over
SPAWN_ROWS = 2  # a new piece appears within the top rows

FRAMES_PER_INPUT = 3  # press for one frame, then let the game see the release
LOCK_TIMEOUT_FRAMES = 60 * 8  # a piece that has not locked in this long means the plan went wrong


class PlanFailed(Exception):
    """The piece did not end up where the plan said; the board is re-read from the screen."""


def identify(cells: set[Cell]) -> tuple[str, int] | None:
    """Which piece and orientation a set of four cells is, or None if it is not a tetromino."""
    if len(cells) != 4:
        return None
    top = min(r for r, _ in cells)
    left = min(c for _, c in cells)
    shape = tuple(sorted((r - top, c - left) for r, c in cells))
    for piece, orientations in ROTATIONS.items():
        for rotation, known in enumerate(orientations):
            if known == shape:
                return piece, rotation
    return None


def cells_of(area) -> set[Cell]:
    """Every filled cell of the play field (locked blocks and the falling piece alike)."""
    return {(r, c) for r, row in enumerate(area) for c, tile in enumerate(row) if tile != BLANK}


def board_from(cells: set[Cell], height: int = GB_HEIGHT) -> Board:
    rows = [["."] * WIDTH for _ in range(height)]
    for r, c in cells:
        rows[r][c] = "#"
    return tuple("".join(row) for row in rows)


def board_cells(board: Board) -> set[Cell]:
    return {(r, c) for r, row in enumerate(board) for c, ch in enumerate(row) if ch != "."}


@dataclass
class Falling:
    piece: str
    rotation: int
    cells: set[Cell]

    @property
    def left(self) -> int:
        return min(c for _, c in self.cells)


@dataclass
class GameBoyTetris:
    rom: str
    window: bool = True
    speed: float = 1.0  # emulation speed, 1 = real time, 0 = as fast as possible
    locked: Board = field(default_factory=lambda: empty_board(GB_HEIGHT))
    pieces: int = 0
    closed: bool = False

    def __post_init__(self) -> None:
        from pyboy import PyBoy

        self.pyboy = PyBoy(self.rom, window="SDL2" if self.window else "null", scale=3, sound_emulated=False)
        self.pyboy.set_emulation_speed(self.speed)
        self.wrapper = self.pyboy.game_wrapper
        self.wrapper.start_game()

    # Reading the screen

    def area(self):
        return self.wrapper.game_area()

    def over(self) -> bool:
        return self.closed or any(tile == DEAD for row in self.area() for tile in row)

    def falling(self) -> Falling | None:
        """The piece in flight: the filled cells that are not part of the locked board."""
        loose = cells_of(self.area()) - board_cells(self.locked)
        found = identify(loose)
        if found is None:
            return None
        return Falling(found[0], found[1], loose)

    def tick(self, frames: int = 1) -> bool:
        if not self.pyboy.tick(frames, self.window):
            self.closed = True
        return not self.closed

    def wait_for_piece(self, timeout_frames: int = LOCK_TIMEOUT_FRAMES) -> Falling | None:
        """Tick until a new piece is in the spawn rows, or the game ends."""
        for _ in range(timeout_frames):
            if self.over():
                return None
            piece = self.falling()
            if piece is not None and all(r < SPAWN_ROWS for r, _ in piece.cells):
                return piece
            if not self.tick():
                return None
        return None

    def game(self, piece: Falling) -> Game:
        return Game(
            board=self.locked,
            current=piece.piece,
            queue=(self.wrapper.next_tetromino(),),
            hold=None,
            score=self.wrapper.score,
            lines=self.wrapper.lines,
            pieces=self.pieces,
            can_hold=False,
        )

    # Pressing buttons

    def press(self, button: str) -> Falling | None:
        self.pyboy.button(button)
        if not self.tick(FRAMES_PER_INPUT):
            return None
        return self.falling()

    def play(self, placement: Placement) -> None:
        """Turn, slide and drop the falling piece so it lands as the placement says, then wait for it
        to lock and for the next piece to appear. Raises PlanFailed if the screen disagrees."""
        piece = self.falling()
        if piece is None or piece.piece != placement.piece:
            raise PlanFailed("no falling piece of the expected kind")
        for _ in range(4):
            if piece.rotation == placement.rotation:
                break
            piece = self.press("a")  # rotates; the direction does not matter, we look at the result
            if piece is None:
                raise PlanFailed("lost the piece while turning")
        if piece.rotation != placement.rotation:
            raise PlanFailed("could not reach the orientation")
        for _ in range(WIDTH):
            if piece.left == placement.col:
                break
            piece = self.press("right" if placement.col > piece.left else "left")
            if piece is None:
                raise PlanFailed("lost the piece while sliding")
        if piece.left != placement.col:
            raise PlanFailed("could not reach the column")

        expected = board_cells(placement.board)
        self.pyboy.button_press("down")
        try:
            for _ in range(LOCK_TIMEOUT_FRAMES):
                if not self.tick():
                    return
                filled = cells_of(self.area())
                loose = filled - expected
                spawned = identify(loose) is not None and all(r < SPAWN_ROWS for r, _ in loose)
                if expected <= filled and (not loose or spawned):
                    self.locked = placement.board
                    self.pieces += 1
                    return
                if self.over():
                    return
        finally:
            self.pyboy.button_release("down")
        raise PlanFailed("the piece did not lock where the plan said")

    def resync(self) -> None:
        """After a failed plan: treat everything on screen outside the spawn rows as locked."""
        filled = cells_of(self.area())
        self.locked = board_from({(r, c) for r, c in filled if r >= SPAWN_ROWS})
        self.pieces += 1

    def close(self) -> None:
        self.pyboy.stop(save=False)
