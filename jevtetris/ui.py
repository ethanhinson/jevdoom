"""Draw the game in a pygame window, or nowhere at all."""

from __future__ import annotations

import sys

from .board import HEIGHT, LINE_SCORES, ROTATIONS, WIDTH, Cell, Game, Move, spawn_col
from .brain import Decision

CELL = 30
BOARD_W = WIDTH * CELL
BOARD_H = HEIGHT * CELL
PANEL_W = 260
MARGIN = 20
WINDOW = (MARGIN * 3 + BOARD_W + PANEL_W, MARGIN * 2 + BOARD_H)

BACKGROUND = (18, 18, 24)
WELL = (28, 28, 36)
GRID = (40, 40, 52)
TEXT = (225, 225, 235)
DIM = (140, 140, 160)
COLORS = {
    "I": (80, 200, 230),
    "O": (240, 210, 70),
    "T": (170, 90, 220),
    "S": (100, 210, 110),
    "Z": (230, 80, 90),
    "J": (80, 110, 230),
    "L": (240, 150, 60),
}


class Headless:
    """No window: print a line per piece."""

    def __init__(self, speed: float):
        self.speed = speed

    def animate(self, game: Game, decision: Decision, keys: dict[str, Move]) -> bool:
        p = decision.move.placement
        tag = "fallback" if decision.fallback else f"conf={decision.confidence:.2f}"
        hold = "hold, " if decision.move.hold else ""
        print(
            f"[{game.pieces:4d}] {hold}{p.piece} cols {p.columns[0]}-{p.columns[1]} {tag} "
            f"{decision.latency_ms:4.0f}ms | clears={p.cleared} holes={p.holes} height={p.max_height} "
            f"| lines={game.lines + p.cleared} score={game.score + LINE_SCORES[p.cleared] * game.level}"
        )
        return True

    def show(self, game: Game, waiting: bool) -> bool:
        return True

    def close(self) -> None:
        pass


class Window:
    def __init__(self, speed: float):
        import pygame

        pygame.init()
        pygame.display.set_caption("Jev plays Tetris")
        self.pygame = pygame
        self.screen = pygame.display.set_mode(WINDOW)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo, monaco, consolas, monospace", 16)
        self.small = pygame.font.SysFont("menlo, monaco, consolas, monospace", 13)
        self.speed = speed
        self.paused = False
        self.last: Decision | None = None
        self.stats: dict[str, str] = {}

    # Events

    def pump(self) -> bool:
        """Handle window events; False when the person closed the window or pressed Escape."""
        pg = self.pygame
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return False
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    return False
                if event.key == pg.K_SPACE:
                    self.paused = not self.paused
                if event.key in (pg.K_EQUALS, pg.K_PLUS):
                    self.speed = min(self.speed * 1.5, 20)
                if event.key == pg.K_MINUS:
                    self.speed = max(self.speed / 1.5, 0.1)
        return True

    def _frame(self, frames: float) -> bool:
        """Wait `frames` sixtieths of a second at speed 1, drawing and handling events meanwhile."""
        remaining = frames / self.speed
        while True:
            if not self.pump():
                return False
            self.pygame.display.flip()
            self.clock.tick(60)
            if self.paused:
                continue
            remaining -= 1
            if remaining <= 0:
                return True

    # Drawing

    def _cell(self, row: int, col: int, color, alpha: int = 255, inset: int = 1) -> None:
        """A locked or falling cell; a translucent one is drawn as an outline (a ghost)."""
        pg = self.pygame
        x = MARGIN + col * CELL
        y = MARGIN + row * CELL
        rect = pg.Rect(x + inset, y + inset, CELL - 2 * inset, CELL - 2 * inset)
        if alpha >= 255:
            pg.draw.rect(self.screen, color, rect, border_radius=3)
        else:
            surface = pg.Surface(rect.size, pg.SRCALPHA)
            pg.draw.rect(surface, (*color, alpha), surface.get_rect(), width=2, border_radius=3)
            self.screen.blit(surface, rect.topleft)

    def _board(self, game: Game) -> None:
        pg = self.pygame
        pg.draw.rect(self.screen, WELL, pg.Rect(MARGIN, MARGIN, BOARD_W, BOARD_H))
        for row in range(HEIGHT + 1):
            y = MARGIN + row * CELL
            pg.draw.line(self.screen, GRID, (MARGIN, y), (MARGIN + BOARD_W, y))
        for col in range(WIDTH + 1):
            x = MARGIN + col * CELL
            pg.draw.line(self.screen, GRID, (x, MARGIN), (x, MARGIN + BOARD_H))
        for row, line in enumerate(game.board):
            for col, ch in enumerate(line):
                if ch != ".":
                    self._cell(row, col, COLORS[ch])

    def _piece(self, piece: str, cells: tuple[Cell, ...], row: int, col: int, alpha: int = 255) -> None:
        for r, c in cells:
            self._cell(row + r, col + c, COLORS[piece], alpha)

    def _mini(self, piece: str | None, x: int, y: int) -> None:
        if piece is None:
            return
        cells = ROTATIONS[piece][0]
        width = max(c for _, c in cells) + 1
        size = 18
        ox = x + (4 - width) * size // 2
        for r, c in cells:
            rect = self.pygame.Rect(ox + c * size + 1, y + r * size + 1, size - 2, size - 2)
            self.pygame.draw.rect(self.screen, COLORS[piece], rect, border_radius=2)

    def _text(self, text: str, x: int, y: int, color=TEXT, small: bool = False) -> int:
        font = self.small if small else self.font
        self.screen.blit(font.render(text, True, color), (x, y))
        return y + (18 if small else 22)

    def _panel(self, game: Game, waiting: bool) -> None:
        x = MARGIN * 2 + BOARD_W
        y = MARGIN
        y = self._text("HOLD", x, y, DIM)
        self._mini(game.hold, x, y)
        y += 50
        y = self._text("NEXT", x, y, DIM)
        for piece in game.queue:
            self._mini(piece, x, y)
            y += 44
        y += 6
        y = self._text(f"score  {game.score}", x, y)
        y = self._text(f"lines  {game.lines}", x, y)
        y = self._text(f"level  {game.level}", x, y)
        y = self._text(f"pieces {game.pieces}", x, y)
        y += 10
        y = self._text("JEV", x, y, DIM)
        if self.last is not None:
            d = self.last
            p = d.move.placement
            what = ("hold, " if d.move.hold else "") + f"{p.piece} at {p.columns[0]}-{p.columns[1]}"
            y = self._text(what, x, y)
            if d.fallback:
                y = self._text("fallback: Jev did not answer", x, y, (230, 120, 120), small=True)
            else:
                y = self._text(f"confidence {d.confidence:.2f}  {d.latency_ms:.0f}ms", x, y, small=True)
                options = len(d.probabilities)
                y = self._text(f"chose from {options} placements", x, y, DIM, small=True)
        if waiting:
            y = self._text("thinking...", x, y, DIM, small=True)
        y += 10
        for line in self.stats.values():
            y = self._text(line, x, y, DIM, small=True)
        y = WINDOW[1] - MARGIN - 40
        y = self._text(f"speed x{self.speed:.2g}  (+ and - change it)", x, y, DIM, small=True)
        self._text("space pauses, esc quits", x, y, DIM, small=True)
        if game.over:
            self._text("GAME OVER", MARGIN + BOARD_W // 2 - 50, MARGIN + BOARD_H // 2 - 10, (240, 240, 240))

    def show(self, game: Game, waiting: bool) -> bool:
        self.screen.fill(BACKGROUND)
        self._board(game)
        self._panel(game, waiting)
        return self._frame(1)

    def animate(self, game: Game, decision: Decision, keys: dict[str, Move]) -> bool:
        """Show the runners-up as ghosts, then move the chosen piece the way a player would:
        turn at the top, slide across, and drop. Returns False if the window was closed."""
        self.last = decision
        move = decision.move
        p = move.placement
        ghosts = [(m, prob) for m, prob in decision.ranked(keys, 4) if m is not move]

        def draw(cells, row, col):
            self.screen.fill(BACKGROUND)
            self._board(game)
            for ghost, prob in ghosts:
                g = ghost.placement
                self._piece(g.piece, g.cells, g.row, g.col, alpha=int(70 + 180 * prob))
            self._piece(p.piece, cells, row, col)
            self._panel(game, waiting=False)

        # the piece appears at the top in its spawn orientation, then turns
        for turn in range(p.rotation + 1):
            cells = ROTATIONS[p.piece][turn]
            draw(cells, 0, spawn_col(cells))
            if not self._frame(5):
                return False
        # slides across at the top
        col = spawn_col(p.cells)
        step = 1 if p.col > col else -1
        while col != p.col:
            col += step
            draw(p.cells, 0, col)
            if not self._frame(2):
                return False
        # and drops
        for row in range(1, p.row + 1):
            draw(p.cells, row, p.col)
            if not self._frame(1):
                return False
        if p.cleared:
            # flash the rows about to go
            for _ in range(2):
                draw(p.cells, p.row, p.col)
                for r in range(HEIGHT):
                    if "." not in _with(game, p, r):
                        self.pygame.draw.rect(
                            self.screen, (240, 240, 240), (MARGIN, MARGIN + r * CELL, BOARD_W, CELL)
                        )
                if not self._frame(3):
                    return False
                draw(p.cells, p.row, p.col)
                if not self._frame(3):
                    return False
        return True

    def close(self) -> None:
        self.pygame.quit()


def _with(game: Game, p, row: int) -> str:
    """Row `row` of the board with the piece drawn in, before clearing."""
    line = list(game.board[row])
    for r, c in p.cells:
        if p.row + r == row:
            line[p.col + c] = p.piece
    return "".join(line)


def make(window: bool, speed: float) -> Window | Headless:
    if not window:
        return Headless(speed)
    try:
        return Window(speed)
    except Exception as error:  # noqa: BLE001 - no display, for instance
        print(f"no window ({error}); running headless", file=sys.stderr)
        return Headless(speed)
