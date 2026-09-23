"""Jev plays Tetris on a Game Boy (the PyBoy emulator). Needs the Tetris ROM, which is not included."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from jevcommon import jeview

from .brain import Brain
from .gameboy import GameBoyTetris, PlanFailed

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JEVIEW_LABEL = "jevgameboy"
DEFAULT_ROM = PROJECT_ROOT / "roms" / "tetris.gb"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jev plays Tetris on a Game Boy.")
    parser.add_argument("--rom", default=str(DEFAULT_ROM), help="path to the Tetris Game Boy ROM")
    parser.add_argument("--pieces", type=int, default=None, help="stop after this many pieces")
    parser.add_argument("--no-window", action="store_true", help="run headless")
    parser.add_argument("--speed", type=float, default=1.0, help="emulation speed; 0 runs flat out")
    parser.add_argument("--model", default=None, help="TypeSafe model name (SDK default if omitted)")
    parser.add_argument("--log-dir", default=str(PROJECT_ROOT / "logs"))
    jeview.add_argument(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args(argv)
    if not Path(args.rom).is_file():
        sys.exit(f"no ROM at {args.rom}: put your Tetris (Game Boy) ROM there or pass --rom")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = Path(args.log_dir) / f"gameboy-{stamp}.jsonl"
    brain = Brain(
        log_path,
        model=args.model,
        base_url=jeview.base_url(args.jeview, JEVIEW_LABEL),
        headers=jeview.display_headers({"placement": "where"}) if args.jeview else None,
    )
    print(f"log={log_path}")
    if args.jeview:
        print(f"jeview: calls go through {args.jeview}, watch them at {args.jeview}/")
    gb = GameBoyTetris(args.rom, window=not args.no_window, speed=args.speed)
    failed = 0
    try:
        while args.pieces is None or gb.pieces < args.pieces:
            piece = gb.wait_for_piece()
            if piece is None:
                break
            game = gb.game(piece)
            decision, _ = brain.decide(game)
            p = decision.move.placement
            tag = "fallback" if decision.fallback else f"conf={decision.confidence:.2f}"
            print(
                f"[{gb.pieces:4d}] {p.piece} cols {p.columns[0]}-{p.columns[1]} {tag} "
                f"{decision.latency_ms:4.0f}ms | clears={p.cleared} holes={p.holes} height={p.max_height} "
                f"| lines={game.lines} score={game.score}"
            )
            try:
                gb.play(p)
            except PlanFailed as error:
                failed += 1
                print(f"       plan failed ({error}); re-reading the board", file=sys.stderr)
                gb.resync()
        print(
            f"game: pieces={gb.pieces} lines={gb.wrapper.lines} level={gb.wrapper.level} "
            f"score={gb.wrapper.score} failed_plans={failed} {'game over' if gb.over() else 'stopped'}"
        )
    finally:
        gb.close()
        brain.close()
        avg = sum(brain.latencies) / len(brain.latencies) if brain.latencies else 0.0
        print(
            f"jev: {brain.requests} requests, {brain.errors} errors, "
            f"avg {avg:.0f}ms, {brain.input_tokens} input tokens, ${brain.cost_usd():.4f}"
        )


if __name__ == "__main__":
    main()
