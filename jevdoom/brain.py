"""Ask Jev what matters right now. Runs in a background thread so the game
keeps ticking at full speed while a request is in flight."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from typesafe_sdk import Choice, Noul, RetryPolicy, TypeSafeClient

from .describe import Described, enemy_summary, pickup_summary
from .game import Capabilities, Snapshot

PRICE_PER_TOKEN = 0.042 / 1_000_000  # jev-1.13 list price, input tokens only

MODE_DESCRIPTIONS = {
    "fight": {
        "action": "Turn to face the priority target and shoot it until it is dead.",
        "when": (
            "An enemy is close enough that shots will land, or it is about to hurt the player, "
            "or the player has plenty of ammunition."
        ),
    },
    "advance": {
        "action": "Move forward through the level toward the objective, leaving enemies alone for now.",
        "when": "No enemy is close, and progress matters more than fighting.",
    },
    "retreat": {
        "action": "Back away from the enemies while keeping the priority target in front.",
        "when": "The player is hurt and a melee enemy is closing in, and there is room to back up.",
    },
    "grab_pickup": {
        "action": "Walk over to the most useful item in `pickups` and pick it up.",
        "when": (
            "An item nearby would fix a real problem, such as low health or no ammunition, "
            "and no enemy is close."
        ),
    },
    "hold": {
        "action": "Do not shoot yet; keep facing the priority target and wait.",
        "when": (
            "Every enemy is still far away and ammunition is scarce, so waiting for them to come closer "
            "saves shots. Never hold when an enemy is very close or already hurting the player."
        ),
    },
}


@dataclass(frozen=True)
class Decision:
    tic: int
    mode: str
    mode_confidence: float
    target_id: int | None
    target_confidence: float
    pickup_id: int | None
    under_threat: float
    conserve_ammo: float
    latency_ms: float
    input_tokens: int
    probabilities: dict = field(default_factory=dict)


def build_questions(described: Described, snap: Snapshot, caps: Capabilities) -> dict:
    enemies = {a.id: a for a in snap.enemies}
    pickups = {a.id: a for a in snap.pickups}
    questions: dict = {}

    if described.enemy_keys:
        criteria = {key: enemy_summary(enemies[aid]) for key, aid in described.enemy_keys.items()}
        criteria["none"] = "No enemy needs attention right now."
        questions["priority_target"] = Choice(
            instructions=(
                "Which enemy in `enemies` should the player deal with first? "
                "Pick the one most likely to hurt the player soonest, considering how close it is, "
                "whether it is moving toward the player, and how it attacks."
            ),
            criteria=criteria,
        )

    modes = {"fight": MODE_DESCRIPTIONS["fight"]}
    if caps.can_move:
        modes["advance"] = MODE_DESCRIPTIONS["advance"]
        modes["retreat"] = MODE_DESCRIPTIONS["retreat"]
        if described.pickup_keys:
            modes["grab_pickup"] = MODE_DESCRIPTIONS["grab_pickup"]
    modes["hold"] = MODE_DESCRIPTIONS["hold"]
    questions["mode"] = Choice(
        instructions=(
            "What should the player do for the next moment, given `player`, `situation`, `enemies` and "
            "`pickups`? Each option says what it does and when it is the right call."
        ),
        criteria=modes,
    )

    if described.pickup_keys and caps.can_move:
        criteria = {key: pickup_summary(pickups[aid]) for key, aid in described.pickup_keys.items()}
        criteria["none"] = "No item is worth going for right now."
        questions["priority_pickup"] = Choice(
            instructions="Which item in `pickups` would help the player most right now, given `player`?",
            criteria=criteria,
        )

    questions["under_threat"] = Noul(
        instructions="Is the player likely to take damage within the next second or two if nothing changes?",
    )
    questions["conserve_ammo"] = Noul(
        instructions=(
            "Given `player.ammo`, should the player hold fire on enemies that are far away "
            "and save ammunition for enemies that get close?"
        ),
    )
    return questions


def _actor_id(choice: str | None, keys: dict[str, int]) -> int | None:
    if choice is None:
        return None
    return keys.get(choice)


class Brain:
    def __init__(
        self,
        log_path: Path,
        model: str | None = None,
        timeout: float = 2.0,
        base_url: str | None = None,
    ):
        kwargs = {"retry": RetryPolicy(max_retries=2, backoff_max=0.2, timeout=timeout)}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url  # e.g. a Jeview gateway, which forwards to TypeSafe
        self.client = TypeSafeClient(**kwargs)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(log_path, "a", encoding="utf-8")
        self._lock = threading.Condition()
        self._pending: tuple[Described, Snapshot, Capabilities] | None = None
        self._latest: Decision | None = None
        self._stop = False
        self.requests = 0
        self.errors = 0
        self.input_tokens = 0
        self.latencies: list[float] = []
        self._thread = threading.Thread(target=self._run, name="jev-brain", daemon=True)
        self._thread.start()

    # Public API used by the game loop

    def submit(self, described: Described, snap: Snapshot, caps: Capabilities) -> None:
        """Replace whatever is pending with the freshest state."""
        with self._lock:
            self._pending = (described, snap, caps)
            self._lock.notify()

    def latest(self) -> Decision | None:
        with self._lock:
            return self._latest

    def decide(self, described: Described, snap: Snapshot, caps: Capabilities) -> Decision | None:
        """Blocking variant for --sync runs."""
        decision = self._ask(described, snap, caps)
        with self._lock:
            if decision is not None:
                self._latest = decision
        return decision

    def cost_usd(self) -> float:
        return self.input_tokens * PRICE_PER_TOKEN

    def close(self) -> None:
        with self._lock:
            self._stop = True
            self._lock.notify()
        self._thread.join(timeout=3)
        self._log.close()
        self.client.close()

    # Worker

    def _run(self) -> None:
        while True:
            with self._lock:
                while self._pending is None and not self._stop:
                    self._lock.wait()
                if self._stop:
                    return
                described, snap, caps = self._pending
                self._pending = None
            decision = self._ask(described, snap, caps)
            if decision is not None:
                with self._lock:
                    self._latest = decision

    def _ask(self, described: Described, snap: Snapshot, caps: Capabilities) -> Decision | None:
        questions = build_questions(described, snap, caps)
        started = time.perf_counter()
        try:
            response = self.client.system_one(described.state, questions)
        except Exception as error:  # noqa: BLE001 - keep playing on transient API failures
            self.errors += 1
            self._write({"tic": snap.tic, "error": repr(error)})
            return None
        latency_ms = (time.perf_counter() - started) * 1000
        answers = response.answers

        mode = answers["mode"]
        target = answers.get("priority_target")
        pickup = answers.get("priority_pickup")
        decision = Decision(
            tic=snap.tic,
            mode=mode.choice,
            mode_confidence=mode.confidence,
            target_id=_actor_id(target.choice if target else None, described.enemy_keys),
            target_confidence=target.confidence if target else 0.0,
            pickup_id=_actor_id(pickup.choice if pickup else None, described.pickup_keys),
            under_threat=answers["under_threat"].noul,
            conserve_ammo=answers["conserve_ammo"].noul,
            latency_ms=latency_ms,
            input_tokens=response.usage.input_tokens,
            probabilities={
                "mode": mode.probabilities,
                "priority_target": target.probabilities if target else {},
            },
        )
        self.requests += 1
        self.input_tokens += response.usage.input_tokens
        self.latencies.append(latency_ms)
        self._write(
            {
                "tic": snap.tic,
                "state": described.state,
                "questions": {k: _question_json(q) for k, q in questions.items()},
                "answers": {k: _answer_json(a) for k, a in answers.items()},
                "decision": asdict(decision),
            }
        )
        return decision

    def _write(self, record: dict) -> None:
        self._log.write(json.dumps(record, default=str) + "\n")
        self._log.flush()


def _question_json(question) -> dict:
    dump = getattr(question, "model_dump", None)
    return dump(mode="json") if dump else {"repr": repr(question)}


def _answer_json(answer) -> dict:
    dump = getattr(answer, "model_dump", None)
    return dump(mode="json") if dump else {"repr": repr(answer)}
