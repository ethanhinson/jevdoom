from jevdoom.describe import (
    MAX_ENEMIES,
    ammo_words,
    bearing_words,
    describe,
    distance_words,
    enemy_summary,
    health_words,
)
from jevdoom.game import Actor, Capabilities, Snapshot

CAPS_TURN_ONLY = Capabilities(can_attack=True, can_move=False, can_strafe=False)


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


def snapshot(actors) -> Snapshot:
    return Snapshot(
        tic=0,
        health=100,
        armor=0,
        weapon=2,
        ammo=26,
        angle=0.0,
        x=0.0,
        y=0.0,
        kills=0,
        damage_taken=0,
        items=0,
        actors=tuple(actors),
    )


def test_bearing_words_cover_the_circle():
    assert bearing_words(0) == "dead ahead"
    assert bearing_words(15) == "slightly left"
    assert bearing_words(-15) == "slightly right"
    assert bearing_words(40) == "to the left, at the edge of the screen"
    assert bearing_words(-70) == "off to the right, out of view"
    assert bearing_words(140).startswith("behind and to the left")
    assert bearing_words(179) == "directly behind, out of view"


def test_distance_and_status_words_are_ordered():
    assert distance_words(50) == "touching distance"
    assert distance_words(200) == "very close"
    assert distance_words(400) == "close"
    assert distance_words(800) == "medium range"
    assert distance_words(2000) == "far away"
    assert health_words(100) == "healthy"
    assert health_words(10) == "near death"
    assert ammo_words(0) == "empty"
    assert ammo_words(40) == "plenty"


def test_enemy_summary_uses_friendly_names_and_movement():
    text = enemy_summary(actor(name="MarineChainsawVzd", distance=150, rel_bearing=-10, approaching=True))
    assert text == "chainsaw zombie, very close, slightly right, on screen, moving toward you"


def test_describe_keys_enemies_by_id_and_limits_count():
    actors = [actor(id=i, distance=100.0 * i) for i in range(1, MAX_ENEMIES + 4)]
    described = describe(snapshot(actors), CAPS_TURN_ONLY, took_damage_recently=True)
    assert len(described.enemy_keys) == MAX_ENEMIES
    assert described.enemy_keys["enemy_1"] == 1
    assert described.state["situation"] == f"{MAX_ENEMIES + 3} enemies nearby, {MAX_ENEMIES} on screen."
    assert described.state["player"]["took_damage_in_last_second"] is True
    assert described.state["player"]["can_only_turn_and_shoot"] is True
    assert described.state["enemies"]["enemy_1"]["kind"] == "pinky demon"


def test_describe_with_no_enemies():
    described = describe(snapshot([]), CAPS_TURN_ONLY, took_damage_recently=False)
    assert described.enemy_keys == {}
    assert described.state["situation"] == "No enemies nearby."
