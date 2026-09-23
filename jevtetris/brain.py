"""Ask Jev which placement to make. One question per piece, over every reachable placement of the
current piece and of the piece that would play if this one were held."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import Choice, RetryPolicy, TypeSafeClient

from jevcommon import cost

from .board import Game, Move
from .describe import describe_move, describe_state, move_keys

PLACEMENT_INSTRUCTIONS = (
    "Which option is the best way to play the next piece, given `board`, `current_piece`, "
    "`held_piece` and `next_pieces`? Judge the board each option leaves behind: clearing lines is "
    "good, especially several at once; new holes are bad because they block future clears; a low, "
    "flat stack is safer; one deep well on an edge is worth keeping for the I piece. Options starting "
    "with 'hold', when there are any, play the alternate piece instead, as `hold_rule` explains."
)


@dataclass(frozen=True)
class Decision:
    move: Move
    key: str
    confidence: float
    probabilities: dict[str, float]
    latency_ms: float
    input_tokens: int
    fallback: bool = False  # Jev could not answer, so code picked the safest-looking move

    def ranked(self, keys: dict[str, Move], top: int) -> list[tuple[Move, float]]:
        best = sorted(self.probabilities.items(), key=lambda kv: kv[1], reverse=True)
        return [(keys[k], p) for k, p in best[:top] if k in keys]


def safest(moves: list[Move]) -> Move:
    """Fallback only: the placement that adds the fewest holes, then keeps the stack lowest."""
    return min(moves, key=lambda m: (m.placement.new_holes, m.placement.max_height, m.placement.bumpiness))


class Brain:
    def __init__(
        self,
        log_path: Path,
        model: str | None = None,
        timeout: float = 4.0,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        kwargs: dict = {"retry": RetryPolicy(max_retries=2, backoff_max=0.3, timeout=timeout)}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url  # e.g. a Jeview gateway, which forwards to TypeSafe
        if headers:
            kwargs["headers"] = headers
        self.client = TypeSafeClient(**kwargs)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(log_path, "a", encoding="utf-8")
        self.requests = 0
        self.errors = 0
        self.input_tokens = 0
        self.latencies: list[float] = []

    def decide(self, game: Game) -> tuple[Decision, dict[str, Move]]:
        moves = game.moves()
        keys = move_keys(moves)
        state = describe_state(game)
        question = Choice(
            instructions=PLACEMENT_INSTRUCTIONS,
            criteria={key: describe_move(move) for key, move in keys.items()},
        )
        started = time.perf_counter()
        try:
            response = self.client.system_one(state, {"placement": question})
        except Exception as error:  # noqa: BLE001 - keep playing on transient API failures
            self.errors += 1
            self._write({"piece": game.pieces, "error": repr(error)})
            move = safest(moves)
            key = next(k for k, m in keys.items() if m is move)
            return Decision(move, key, 0.0, {}, 0.0, 0, fallback=True), keys
        latency_ms = (time.perf_counter() - started) * 1000
        answer = response.answers["placement"]
        decision = Decision(
            move=keys[answer.choice],
            key=answer.choice,
            confidence=answer.confidence,
            probabilities=dict(answer.probabilities),
            latency_ms=latency_ms,
            input_tokens=response.usage.input_tokens,
        )
        self.requests += 1
        self.input_tokens += response.usage.input_tokens
        self.latencies.append(latency_ms)
        self._write(
            {
                "piece": game.pieces,
                "state": state,
                "options": {k: describe_move(m) for k, m in keys.items()},
                "answer": answer.model_dump(mode="json"),
                "chosen": describe_move(decision.move),
                "latency_ms": round(latency_ms),
                "input_tokens": response.usage.input_tokens,
            }
        )
        return decision, keys

    def cost_usd(self) -> float:
        return cost.usd(self.input_tokens)

    def close(self) -> None:
        self._log.close()
        self.client.close()

    def _write(self, record: dict) -> None:
        self._log.write(json.dumps(record, default=str) + "\n")
        self._log.flush()
