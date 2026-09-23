"""Jev plays Tetris: code lists every placement, Jev picks one, code plays it."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from jevcommon import jeview

from . import ui
from .board import Bag, Game
from .brain import Brain

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JEVIEW_LABEL = "jevtetris"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jev plays Tetris.")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--pieces", type=int, default=None, help="stop a game after this many pieces")
    parser.add_argument("--seed", type=int, default=None, help="piece order seed (random if omitted)")
    parser.add_argument("--no-window", action="store_true", help="run headless")
    parser.add_argument("--speed", type=float, default=1.0, help="animation speed multiplier")
    parser.add_argument("--model", default=None, help="TypeSafe model name (SDK default if omitted)")
    parser.add_argument("--log-dir", default=str(PROJECT_ROOT / "logs"))
    jeview.add_argument(parser)
    return parser.parse_args(argv)


def play(brain: Brain, view, bag: Bag, executor: ThreadPoolExecutor, max_pieces: int | None) -> Game:
    """One game. The next decision is requested as soon as the board it needs is known, so Jev
    thinks while the current piece is still falling."""
    game = Game.new(bag)
    pending: Future = executor.submit(brain.decide, game)
    while not game.over and (max_pieces is None or game.pieces < max_pieces):
        while not pending.done():
            if not view.show(game, waiting=True):
                return game
        decision, keys = pending.result()
        after = game.apply(decision.move, bag)
        if not after.over:
            pending = executor.submit(brain.decide, after)
        if not view.animate(game, decision, keys):
            return game
        game = after
    view.show(game, waiting=False)
    return game


def main(argv: list[str] | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args(argv)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = Path(args.log_dir) / f"tetris-{stamp}.jsonl"
    brain = Brain(
        log_path,
        model=args.model,
        base_url=jeview.base_url(args.jeview, JEVIEW_LABEL),
        headers=jeview.display_headers({"placement": "where"}) if args.jeview else None,
    )
    view = ui.make(window=not args.no_window, speed=args.speed)
    print(f"log={log_path}")
    if args.jeview:
        print(f"jeview: calls go through {args.jeview}, watch them at {args.jeview}/")
    bag = Bag(args.seed)
    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-brain") as executor:
            for number in range(1, args.games + 1):
                game = play(brain, view, bag, executor, args.pieces)
                print(
                    f"game {number}: pieces={game.pieces} lines={game.lines} level={game.level} "
                    f"score={game.score} {'game over' if game.over else 'stopped'}"
                )
                if hasattr(view, "stats"):
                    view.stats[f"game{number}"] = f"game {number}: {game.lines} lines, {game.score} pts"
                if hasattr(view, "pump") and not view.pump():
                    break
    finally:
        view.close()
        brain.close()
        avg = sum(brain.latencies) / len(brain.latencies) if brain.latencies else 0.0
        print(
            f"jev: {brain.requests} requests, {brain.errors} errors, "
            f"avg {avg:.0f}ms, {brain.input_tokens} input tokens, ${brain.cost_usd():.4f}"
        )


if __name__ == "__main__":
    main()
