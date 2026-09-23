import vizdoom as vzd

from jevdoom.brain import Decision
from jevdoom.control import TURN_PER_TIC, aim_tolerance, choose_buttons, resolve_target, turn_toward
from jevdoom.game import Actor, Capabilities, Snapshot, relative_bearing

B = vzd.Button
CAPS_TURN_ONLY = Capabilities(can_attack=True, can_move=False, can_strafe=False)
CAPS_FULL = Capabilities(can_attack=True, can_move=True, can_strafe=True)


def actor(**overrides) -> Actor:
    base = dict(
        id=1,
        name="Demon",
        category="monster",
        distance=300.0,
        rel_bearing=0.0,
        visible=True,
        approaching=False,
    )
    base.update(overrides)
    return Actor(**base)


def snapshot(actors, ammo=26, angle=0.0) -> Snapshot:
    return Snapshot(
        tic=0,
        health=100,
        armor=0,
        weapon=2,
        ammo=ammo,
        angle=angle,
        x=0.0,
        y=0.0,
        kills=0,
        damage_taken=0,
        items=0,
        actors=tuple(actors),
    )


def decision(**overrides) -> Decision:
    base = dict(
        tic=0,
        mode="fight",
        mode_confidence=1.0,
        target_id=1,
        target_confidence=1.0,
        pickup_id=None,
        under_threat=0.0,
        conserve_ammo=0.0,
        latency_ms=100.0,
        input_tokens=1,
    )
    base.update(overrides)
    return Decision(**base)


def test_relative_bearing_positive_means_left():
    # Facing east (0 deg), a target due north (+y) is 90 degrees to the left.
    assert relative_bearing(0.0, 0.0, 10.0) == 90.0
    assert relative_bearing(0.0, 0.0, -10.0) == -90.0
    assert relative_bearing(90.0, -10.0, 0.0) == 90.0


def test_turn_is_capped_per_tic():
    assert turn_toward(100.0) == TURN_PER_TIC
    assert turn_toward(-100.0) == -TURN_PER_TIC
    assert turn_toward(3.0) == 3.0


def test_aim_tolerance_shrinks_with_distance():
    assert aim_tolerance(50) == 10.0
    assert aim_tolerance(300) < aim_tolerance(100)
    assert aim_tolerance(5000) == 2.5


def test_target_falls_back_to_nearest_visible_when_dead():
    far_visible = actor(id=7, distance=600, visible=True)
    near_hidden = actor(id=8, distance=100, visible=False)
    snap = snapshot([near_hidden, far_visible])
    assert resolve_target(decision(target_id=99), snap) is far_visible
    assert resolve_target(decision(target_id=8), snap) is near_hidden


def test_fight_turns_toward_target_then_shoots():
    snap = snapshot([actor(rel_bearing=40.0)])
    pressed = choose_buttons(decision(), snap, CAPS_TURN_ONLY, home_angle=0.0)
    assert pressed[B.TURN_LEFT_RIGHT_DELTA] == TURN_PER_TIC
    assert B.ATTACK not in pressed

    aligned = snapshot([actor(rel_bearing=1.0)])
    pressed = choose_buttons(decision(), aligned, CAPS_TURN_ONLY, home_angle=0.0)
    assert pressed[B.ATTACK] == 1


def test_hold_faces_target_without_shooting():
    snap = snapshot([actor(rel_bearing=0.0)])
    pressed = choose_buttons(decision(mode="hold"), snap, CAPS_TURN_ONLY, home_angle=0.0)
    assert B.ATTACK not in pressed


def test_hold_still_shoots_a_close_target_when_jev_rates_danger_high():
    close = snapshot([actor(rel_bearing=0.0, distance=80)])
    pressed = choose_buttons(decision(mode="hold", under_threat=0.9), close, CAPS_TURN_ONLY, home_angle=0.0)
    assert pressed[B.ATTACK] == 1
    far = snapshot([actor(rel_bearing=0.0, distance=500)])
    pressed = choose_buttons(decision(mode="hold", under_threat=0.9), far, CAPS_TURN_ONLY, home_angle=0.0)
    assert B.ATTACK not in pressed


def test_conserve_ammo_holds_fire_on_far_targets_only():
    far = snapshot([actor(distance=900, rel_bearing=0.0)])
    pressed = choose_buttons(decision(conserve_ammo=0.9), far, CAPS_TURN_ONLY, home_angle=0.0)
    assert B.ATTACK not in pressed
    near = snapshot([actor(distance=200, rel_bearing=0.0)])
    pressed = choose_buttons(decision(conserve_ammo=0.9), near, CAPS_TURN_ONLY, home_angle=0.0)
    assert pressed[B.ATTACK] == 1


def test_no_ammo_never_shoots():
    snap = snapshot([actor(rel_bearing=0.0)], ammo=0)
    pressed = choose_buttons(decision(), snap, CAPS_TURN_ONLY, home_angle=0.0)
    assert B.ATTACK not in pressed


def test_retreat_backs_up_while_facing_target():
    snap = snapshot([actor(rel_bearing=0.0)])
    pressed = choose_buttons(decision(mode="retreat"), snap, CAPS_FULL, home_angle=0.0)
    assert pressed[B.MOVE_BACKWARD] == 1
    assert pressed[B.ATTACK] == 1


def test_advance_heads_home_and_moves():
    snap = snapshot([], angle=30.0)
    pressed = choose_buttons(decision(mode="advance", target_id=None), snap, CAPS_FULL, home_angle=0.0)
    assert pressed[B.TURN_LEFT_RIGHT_DELTA] == -TURN_PER_TIC
    assert pressed[B.MOVE_FORWARD] == 1


def test_no_decision_means_no_input():
    assert choose_buttons(None, snapshot([actor()]), CAPS_FULL, home_angle=0.0) == {}
