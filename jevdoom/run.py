"""Play a ViZDoom scenario with Jev deciding what matters and code doing the rest."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from jevcommon import jeview

from .brain import Brain, Decision
from .control import choose_buttons, resolve_target
from .describe import describe, enemy_summary
from .game import SCENARIOS, DoomSession

TICS_PER_SECOND = 35
PROJECT_ROOT = Path(__file__).resolve().parents[1]
JEVIEW_LABEL = "jevdoom"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jev plays Doom.")
    parser.add_argument("--scenario", default="defend_the_center", choices=sorted(SCENARIOS))
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--no-window", action="store_true", help="run headless")
    parser.add_argument("--sync", action="store_true", help="wait for Jev before every decision")
    parser.add_argument("--decide-every", type=int, default=4, help="tics between requests to Jev")
    parser.add_argument(
        "--speed", type=float, default=1.0, help="game speed multiplier; 0 runs as fast as possible"
    )
    parser.add_argument("--skill", type=int, default=None, help="Doom skill 1-5 (scenario default)")
    parser.add_argument("--model", default=None, help="TypeSafe model name (SDK default if omitted)")
    parser.add_argument("--log-dir", default=str(PROJECT_ROOT / "logs"))
    jeview.add_argument(parser)
    return parser.parse_args(argv)


def status_line(tic: int, decision: Decision, snap) -> str:
    target = resolve_target(decision, snap)
    target_text = enemy_summary(target) if target else "none"
    return (
        f"[{tic:5d}] {decision.mode:<11} conf={decision.mode_confidence:.2f} "
        f"threat={decision.under_threat:.2f} save_ammo={decision.conserve_ammo:.2f} "
        f"{decision.latency_ms:4.0f}ms | hp={snap.health:3d} ammo={snap.ammo:3d} kills={snap.kills:2d} "
        f"| target: {target_text}"
    )


def play_episode(session: DoomSession, brain: Brain, args: argparse.Namespace) -> dict:
    session.new_episode()
    caps = session.capabilities
    tic = 0
    home_angle: float | None = None
    decision: Decision | None = None
    shown: Decision | None = None
    last_damage = 0
    damage_tic = -1000
    tic_seconds = 1.0 / (TICS_PER_SECOND * args.speed) if args.speed > 0 else 0.0
    next_tick = time.perf_counter()
    final = None

    while not session.finished():
        snap = session.snapshot(tic)
        if snap is None:
            break
        final = snap
        if home_angle is None:
            home_angle = snap.angle
        if snap.damage_taken > last_damage:
            damage_tic = tic
            last_damage = snap.damage_taken
        took_damage = tic - damage_tic <= TICS_PER_SECOND

        if tic % args.decide_every == 0:
            described = describe(snap, caps, took_damage)
            if args.sync:
                decision = brain.decide(described, snap, caps) or decision
            else:
                brain.submit(described, snap, caps)
        if not args.sync:
            decision = brain.latest() or decision

        if decision is not None and decision is not shown:
            print(status_line(tic, decision, snap))
            shown = decision

        session.act(choose_buttons(decision, snap, caps, home_angle))
        tic += 1

        if tic_seconds > 0:
            next_tick += tic_seconds
            delay = next_tick - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.perf_counter()

    return {
        "tics": tic,
        "seconds": round(tic / TICS_PER_SECOND, 1),
        "kills": final.kills if final else 0,
        "health": final.health if final else 0,
        "ammo": final.ammo if final else 0,
        "reward": session.game.get_total_reward(),
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    sys.stdout.reconfigure(line_buffering=True)  # status lines show up live even when redirected
    args = parse_args(argv)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = Path(args.log_dir) / f"{args.scenario}-{stamp}.jsonl"
    session = DoomSession(args.scenario, window=not args.no_window, skill=args.skill)
    brain = Brain(log_path, model=args.model, base_url=jeview.base_url(args.jeview, JEVIEW_LABEL))
    print(f"scenario={args.scenario} buttons={[b.name for b in session.buttons]} log={log_path}")
    if args.jeview:
        print(f"jeview: calls go through {args.jeview}, watch them at {args.jeview}/")
    try:
        for episode in range(1, args.episodes + 1):
            result = play_episode(session, brain, args)
            print(f"episode {episode}: {result}")
    finally:
        brain.close()  # joins the worker so the counters below are final
        session.close()
        avg = sum(brain.latencies) / len(brain.latencies) if brain.latencies else 0.0
        print(
            f"jev: {brain.requests} requests, {brain.errors} errors, "
            f"avg {avg:.0f}ms, {brain.input_tokens} input tokens, ${brain.cost_usd():.4f}"
        )


if __name__ == "__main__":
    main()
