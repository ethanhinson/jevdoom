"""A plain Tetris engine: pieces, the board, every placement a piece could reach, and what each
placement does to the board. Jev never sees this code; it sees the words in describe.py."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

WIDTH = 10
HEIGHT = 20
PREVIEW = 3

Cell = tuple[int, int]  # (row, col), rows count down from the top of the board

# Spawn orientation of each tetromino.
SHAPES: dict[str, tuple[Cell, ...]] = {
    "I": ((0, 0), (0, 1), (0, 2), (0, 3)),
    "O": ((0, 0), (0, 1), (1, 0), (1, 1)),
    "T": ((0, 1), (1, 0), (1, 1), (1, 2)),
    "S": ((0, 1), (0, 2), (1, 0), (1, 1)),
    "Z": ((0, 0), (0, 1), (1, 1), (1, 2)),
    "J": ((0, 0), (1, 0), (1, 1), (1, 2)),
    "L": ((0, 2), (1, 0), (1, 1), (1, 2)),
}


def _normalize(cells: tuple[Cell, ...]) -> tuple[Cell, ...]:
    top = min(r for r, _ in cells)
    left = min(c for _, c in cells)
    return tuple(sorted((r - top, c - left) for r, c in cells))


def _rotate_clockwise(cells: tuple[Cell, ...]) -> tuple[Cell, ...]:
    return _normalize(tuple((c, -r) for r, c in cells))


def rotations(piece: str) -> list[tuple[Cell, ...]]:
    """The distinct orientations of a piece, index = number of clockwise turns from spawn."""
    seen: list[tuple[Cell, ...]] = []
    cells = _normalize(SHAPES[piece])
    for _ in range(4):
        if cells in seen:
            break
        seen.append(cells)
        cells = _rotate_clockwise(cells)
    return seen


ROTATIONS = {piece: rotations(piece) for piece in SHAPES}


def shape_rows(cells: tuple[Cell, ...]) -> list[str]:
    """The orientation drawn as rows of '#' and '.', top row first."""
    height = max(r for r, _ in cells) + 1
    width = max(c for _, c in cells) + 1
    grid = [["."] * width for _ in range(height)]
    for r, c in cells:
        grid[r][c] = "#"
    return ["".join(row) for row in grid]


Board = tuple[str, ...]  # HEIGHT rows of WIDTH chars, "." empty or a piece letter; row 0 is the top

EMPTY_BOARD: Board = tuple("." * WIDTH for _ in range(HEIGHT))


def column_heights(board: Board) -> list[int]:
    heights = []
    for col in range(WIDTH):
        height = 0
        for row in range(HEIGHT):
            if board[row][col] != ".":
                height = HEIGHT - row
                break
        heights.append(height)
    return heights


def count_holes(board: Board) -> int:
    """Empty cells with something filled above them in the same column."""
    holes = 0
    for col in range(WIDTH):
        covered = False
        for row in range(HEIGHT):
            if board[row][col] != ".":
                covered = True
            elif covered:
                holes += 1
    return holes


def bumpiness(heights: list[int]) -> int:
    return sum(abs(a - b) for a, b in zip(heights, heights[1:], strict=False))


def deepest_well(heights: list[int]) -> int:
    """How far the lowest column sits below both its neighbours (an edge column has one neighbour)."""
    deepest = 0
    for col, height in enumerate(heights):
        neighbours = [heights[i] for i in (col - 1, col + 1) if 0 <= i < WIDTH]
        deepest = max(deepest, min(neighbours) - height)
    return deepest


def fits(board: Board, cells: tuple[Cell, ...], row: int, col: int) -> bool:
    for r, c in cells:
        rr, cc = row + r, col + c
        if cc < 0 or cc >= WIDTH or rr < 0 or rr >= HEIGHT or board[rr][cc] != ".":
            return False
    return True


def spawn_col(cells: tuple[Cell, ...]) -> int:
    width = max(c for _, c in cells) + 1
    return (WIDTH - width) // 2


def place(board: Board, piece: str, cells: tuple[Cell, ...], row: int, col: int) -> tuple[Board, int]:
    """The board with the piece locked in and full rows removed, and how many rows were removed."""
    grid = [list(line) for line in board]
    for r, c in cells:
        grid[row + r][col + c] = piece
    kept = [line for line in grid if "." in line]
    cleared = HEIGHT - len(kept)
    kept = [["."] * WIDTH for _ in range(cleared)] + kept
    return tuple("".join(line) for line in kept), cleared


@dataclass(frozen=True)
class Placement:
    piece: str
    rotation: int  # clockwise turns from spawn
    cells: tuple[Cell, ...]
    row: int  # where the top-left of the orientation ends up
    col: int
    board: Board  # the board after locking and clearing
    cleared: int
    heights: list[int]
    holes: int
    new_holes: int
    max_height: int
    bumpiness: int
    well: int

    @property
    def columns(self) -> tuple[int, int]:
        cols = [self.col + c for _, c in self.cells]
        return min(cols), max(cols)

    @property
    def landing_height(self) -> int:
        """Rows from the floor to the lowest cell of the piece, 1 = resting on the floor."""
        return HEIGHT - (self.row + max(r for r, _ in self.cells))


def placements(board: Board, piece: str) -> list[Placement]:
    """Every placement the piece can reach by turning at the top, sliding sideways at the top, and
    dropping straight down. No tucks or spins: a placement the animation could not show is not offered."""
    holes_before = count_holes(board)
    found: list[Placement] = []
    for rotation, cells in enumerate(ROTATIONS[piece]):
        start = spawn_col(cells)
        if not fits(board, cells, 0, start):
            continue
        width = max(c for _, c in cells) + 1
        for col in range(WIDTH - width + 1):
            step = 1 if col >= start else -1
            if not all(fits(board, cells, 0, c) for c in range(start, col + step, step)):
                continue
            row = 0
            while fits(board, cells, row + 1, col):
                row += 1
            after, cleared = place(board, piece, cells, row, col)
            heights = column_heights(after)
            holes = count_holes(after)
            found.append(
                Placement(
                    piece=piece,
                    rotation=rotation,
                    cells=cells,
                    row=row,
                    col=col,
                    board=after,
                    cleared=cleared,
                    heights=heights,
                    holes=holes,
                    new_holes=holes - holes_before,
                    max_height=max(heights),
                    bumpiness=bumpiness(heights),
                    well=deepest_well(heights),
                )
            )
    return found


def can_spawn(board: Board, piece: str) -> bool:
    cells = ROTATIONS[piece][0]
    return fits(board, cells, 0, spawn_col(cells))


LINE_SCORES = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}


class Bag:
    """The 7-bag randomizer: every piece once per bag, in a random order."""

    def __init__(self, seed: int | None = None):
        self._random = random.Random(seed)
        self._bag: list[str] = []

    def next(self) -> str:
        if not self._bag:
            self._bag = list(SHAPES)
            self._random.shuffle(self._bag)
        return self._bag.pop()


@dataclass(frozen=True)
class Move:
    """What to do with the current piece: play it, or hold it and play the alternate piece."""

    placement: Placement
    hold: bool


@dataclass(frozen=True)
class Game:
    board: Board
    current: str
    queue: tuple[str, ...]  # the next PREVIEW pieces
    hold: str | None
    score: int = 0
    lines: int = 0
    pieces: int = 0
    over: bool = False

    @classmethod
    def new(cls, bag: Bag) -> Game:
        current = bag.next()
        queue = tuple(bag.next() for _ in range(PREVIEW))
        return cls(board=EMPTY_BOARD, current=current, queue=queue, hold=None)

    @property
    def level(self) -> int:
        return self.lines // 10 + 1

    @property
    def alternate(self) -> str:
        """The piece that plays if the current one is held: the held piece, or the next one."""
        return self.hold or self.queue[0]

    def moves(self) -> list[Move]:
        now = [Move(p, hold=False) for p in placements(self.board, self.current)]
        held = [Move(p, hold=True) for p in placements(self.board, self.alternate)]
        return now + held

    def apply(self, move: Move, bag: Bag) -> Game:
        """The game after the move; `bag` supplies the piece that joins the preview queue."""
        placement = move.placement
        if move.hold:
            hold = self.current
            queue = self.queue if self.hold else self.queue[1:] + (bag.next(),)
        else:
            hold = self.hold
            queue = self.queue
        current, queue = queue[0], queue[1:] + (bag.next(),)
        lines = self.lines + placement.cleared
        score = self.score + LINE_SCORES[placement.cleared] * self.level
        return replace(
            self,
            board=placement.board,
            current=current,
            queue=queue,
            hold=hold,
            score=score,
            lines=lines,
            pieces=self.pieces + 1,
            over=not can_spawn(placement.board, current),
        )
