"""Turn Jev's latest decision plus fresh geometry into button presses.

This is the reflex layer. It runs every tic and never calls the model.
"""

from __future__ import annotations

import math

import vizdoom as vzd

from .brain import Decision
from .game import Actor, Capabilities, Snapshot

B = vzd.Button

TURN_PER_TIC = 8.0  # degrees; roughly a human flick, keeps the turn watchable
MONSTER_HALF_WIDTH = 24.0  # Doom units; most monsters are 40-64 wide
CONSERVE_MAX_DISTANCE = 600.0  # when Jev says save ammo, only shoot closer than this
THREAT_OVERRIDE = 0.7  # Jev's own danger estimate above which a close target gets shot regardless of mode
THREAT_OVERRIDE_DISTANCE = 220.0  # "very close" or nearer


def aim_tolerance(distance: float) -> float:
    """Degrees of error that still lands a shot at this distance."""
    angle = math.degrees(math.atan2(MONSTER_HALF_WIDTH, max(distance, 1.0)))
    return max(2.5, min(10.0, angle))


def turn_toward(rel_bearing: float) -> float:
    """Signed degrees to turn this tic (positive = left)."""
    return max(-TURN_PER_TIC, min(TURN_PER_TIC, rel_bearing))


def resolve_target(decision: Decision | None, snap: Snapshot) -> Actor | None:
    """The enemy Jev picked if it is still alive, else the nearest one we can see."""
    enemies = snap.enemies
    if not enemies:
        return None
    if decision is not None and decision.target_id is not None:
        for actor in enemies:
            if actor.id == decision.target_id:
                return actor
    visible = [a for a in enemies if a.visible]
    return visible[0] if visible else enemies[0]


def resolve_pickup(decision: Decision | None, snap: Snapshot) -> Actor | None:
    pickups = snap.pickups
    if not pickups:
        return None
    if decision is not None and decision.pickup_id is not None:
        for actor in pickups:
            if actor.id == decision.pickup_id:
                return actor
    return pickups[0]


def choose_buttons(
    decision: Decision | None,
    snap: Snapshot,
    caps: Capabilities,
    home_angle: float,
) -> dict[vzd.Button, float]:
    pressed: dict[vzd.Button, float] = {}
    if decision is None:
        return pressed  # nothing from Jev yet: stand still

    mode = decision.mode
    target = resolve_target(decision, snap)

    if mode in ("fight", "retreat", "hold") and target is not None:
        pressed[B.TURN_LEFT_RIGHT_DELTA] = turn_toward(target.rel_bearing)
        aligned = abs(target.rel_bearing) <= aim_tolerance(target.distance)
        hold_fire = decision.conserve_ammo > 0.5 and target.distance > CONSERVE_MAX_DISTANCE
        # Compose Jev's judgments: a "hold" still fires when Jev itself rates the
        # danger high and the target is close enough to be the cause of it.
        imminent = decision.under_threat > THREAT_OVERRIDE and target.distance <= THREAT_OVERRIDE_DISTANCE
        wants_to_shoot = mode != "hold" or imminent
        if wants_to_shoot and aligned and caps.can_attack and snap.ammo > 0 and not hold_fire:
            pressed[B.ATTACK] = 1
        if mode == "retreat" and caps.can_move:
            pressed[B.MOVE_BACKWARD] = 1
        return pressed

    if mode == "grab_pickup" and caps.can_move:
        pickup = resolve_pickup(decision, snap)
        if pickup is not None:
            pressed[B.TURN_LEFT_RIGHT_DELTA] = turn_toward(pickup.rel_bearing)
            if abs(pickup.rel_bearing) < 30:
                pressed[B.MOVE_FORWARD] = 1
            return pressed
        mode = "advance"

    if mode == "advance" and caps.can_move:
        # Objective direction is the heading we started the episode with.
        rel_home = (home_angle - snap.angle + 180.0) % 360.0 - 180.0
        pressed[B.TURN_LEFT_RIGHT_DELTA] = turn_toward(rel_home)
        if abs(rel_home) < 45:
            pressed[B.MOVE_FORWARD] = 1
        return pressed

    return pressed
