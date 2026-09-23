"""Turn a Snapshot into the plain-language state Jev reads.

Jev is weak with raw numbers, so distances, directions, health and ammo are
all expressed as words. Anything that is arithmetic stays in code.
"""

from __future__ import annotations

from dataclasses import dataclass

from .game import Actor, Capabilities, Snapshot

MONSTERS: dict[str, tuple[str, str]] = {
    "Demon": ("pinky demon", "fast melee biter; harmless until it reaches you, then very dangerous"),
    "Spectre": ("spectre, a near-invisible pinky demon", "fast melee biter; must reach you to hurt you"),
    "MarineChainsawVzd": ("chainsaw zombie", "melee only; walks at you and must touch you to hurt you"),
    "Zombieman": ("zombie soldier", "shoots a pistol from any distance; weak"),
    "ShotgunGuy": ("shotgun zombie", "shoots a shotgun from any distance; very dangerous up close"),
    "ChaingunGuy": ("chaingun zombie", "sprays bullets from any distance; dangerous"),
    "WolfensteinSS": ("machine-gun soldier", "shoots bursts from any distance"),
    "DoomImp": ("imp", "throws slow fireballs from range and claws up close"),
    "LostSoul": ("lost soul", "flying skull that charges straight at you"),
    "Cacodemon": ("cacodemon", "flying; spits fireballs from range; tough"),
    "PainElemental": ("pain elemental", "flying; spawns lost souls"),
    "HellKnight": ("hell knight", "throws powerful plasma balls; very tough"),
    "BaronOfHell": ("baron of hell", "throws powerful plasma balls; extremely tough"),
    "Revenant": ("revenant", "fires homing rockets from range; punches hard up close"),
    "Mancubus": ("mancubus", "fires spreads of fireballs; very tough"),
    "Fatso": ("mancubus", "fires spreads of fireballs; very tough"),
    "Arachnotron": ("arachnotron", "rapid plasma fire from range; tough"),
    "Archvile": ("arch-vile", "sets you on fire from any distance it can see you; extremely dangerous"),
    "Cyberdemon": ("cyberdemon", "boss; fires rockets"),
    "SpiderMastermind": ("spider mastermind", "boss; super chaingun"),
}

PICKUPS: dict[str, str] = {
    "Stimpack": "small health pack",
    "Medikit": "large health pack",
    "HealthBonus": "tiny health bonus",
    "ArmorBonus": "tiny armor bonus",
    "GreenArmor": "green armor vest",
    "BlueArmor": "blue armor vest",
    "Clip": "a few pistol bullets",
    "ClipBox": "box of bullets",
    "Shell": "a few shotgun shells",
    "ShellBox": "box of shotgun shells",
    "RocketAmmo": "one rocket",
    "RocketBox": "box of rockets",
    "Cell": "energy cell",
    "CellPack": "energy cell pack",
    "Shotgun": "shotgun",
    "SuperShotgun": "super shotgun",
    "Chaingun": "chaingun",
    "RocketLauncher": "rocket launcher",
    "PlasmaRifle": "plasma rifle",
    "BFG9000": "BFG 9000",
    "Chainsaw": "chainsaw",
    "Backpack": "backpack with ammo",
    "Soulsphere": "soulsphere, big health boost",
    "Megasphere": "megasphere, full health and armor",
    "Berserk": "berserk pack, heals and boosts punches",
    "InvulnerabilitySphere": "invulnerability sphere",
    "BlurSphere": "partial invisibility sphere",
    "RadSuit": "radiation suit",
    "Infrared": "light amplification goggles",
    "Allmap": "computer map",
    "RedCard": "red keycard",
    "BlueCard": "blue keycard",
    "YellowCard": "yellow keycard",
    "RedSkull": "red skull key",
    "BlueSkull": "blue skull key",
    "YellowSkull": "yellow skull key",
}

WEAPONS = {
    0: "fists",
    1: "fists or chainsaw",
    2: "pistol",
    3: "shotgun",
    4: "chaingun",
    5: "rocket launcher",
    6: "plasma rifle",
    7: "BFG 9000",
}

MAX_ENEMIES = 8
MAX_PICKUPS = 6


def bearing_words(rel: float) -> str:
    """Doom's field of view is 90 degrees, so anything past 45 degrees is off screen."""
    side = "left" if rel > 0 else "right"
    magnitude = abs(rel)
    if magnitude <= 6:
        return "dead ahead"
    if magnitude <= 25:
        return f"slightly {side}"
    if magnitude <= 45:
        return f"to the {side}, at the edge of the screen"
    if magnitude <= 100:
        return f"off to the {side}, out of view"
    if magnitude <= 160:
        return f"behind and to the {side}, out of view"
    return "directly behind, out of view"


def distance_words(distance: float) -> str:
    if distance < 90:
        return "touching distance"
    if distance < 220:
        return "very close"
    if distance < 450:
        return "close"
    if distance < 900:
        return "medium range"
    return "far away"


def health_words(health: int) -> str:
    if health <= 0:
        return "dead"
    if health <= 20:
        return "near death"
    if health <= 40:
        return "badly hurt"
    if health <= 70:
        return "hurt"
    return "healthy"


def ammo_words(ammo: int) -> str:
    if ammo <= 0:
        return "empty"
    if ammo <= 5:
        return "almost out"
    if ammo <= 12:
        return "low"
    if ammo <= 30:
        return "some"
    return "plenty"


def enemy_summary(actor: Actor) -> str:
    kind, _ = MONSTERS.get(actor.name, (actor.name, "unknown monster"))
    parts = [kind, distance_words(actor.distance), bearing_words(actor.rel_bearing)]
    parts.append("on screen" if actor.visible else "not on screen")
    if actor.approaching:
        parts.append("moving toward you")
    return ", ".join(parts)


def pickup_summary(actor: Actor) -> str:
    kind = PICKUPS.get(actor.name, actor.name)
    return ", ".join([kind, distance_words(actor.distance), bearing_words(actor.rel_bearing)])


def enemy_key(actor: Actor) -> str:
    return f"enemy_{actor.id}"


def pickup_key(actor: Actor) -> str:
    return f"item_{actor.id}"


@dataclass(frozen=True)
class Described:
    state: dict
    enemy_keys: dict[str, int]  # question option -> actor id
    pickup_keys: dict[str, int]


def describe(snap: Snapshot, caps: Capabilities, took_damage_recently: bool) -> Described:
    enemies = snap.enemies[:MAX_ENEMIES]
    pickups = snap.pickups[:MAX_PICKUPS]

    enemy_state = {}
    enemy_keys = {}
    for actor in enemies:
        kind, behavior = MONSTERS.get(actor.name, (actor.name, "unknown monster"))
        key = enemy_key(actor)
        enemy_keys[key] = actor.id
        enemy_state[key] = {
            "kind": kind,
            "how_it_attacks": behavior,
            "distance": distance_words(actor.distance),
            "direction": bearing_words(actor.rel_bearing),
            "on_screen": actor.visible,
            "moving_toward_player": actor.approaching,
        }

    pickup_state = {}
    pickup_keys = {}
    for actor in pickups:
        key = pickup_key(actor)
        pickup_keys[key] = actor.id
        pickup_state[key] = {
            "item": PICKUPS.get(actor.name, actor.name),
            "distance": distance_words(actor.distance),
            "direction": bearing_words(actor.rel_bearing),
        }

    visible_count = sum(1 for a in enemies if a.visible)
    total = len(snap.enemies)
    if total == 0:
        situation = "No enemies nearby."
    else:
        noun = "enemy" if total == 1 else "enemies"
        situation = f"{total} {noun} nearby, {visible_count} on screen."

    state = {
        "player": {
            "health": f"{health_words(snap.health)} ({snap.health} of 100)",
            "armor": "none" if snap.armor <= 0 else f"{snap.armor} points",
            "weapon": WEAPONS.get(snap.weapon, "unknown weapon"),
            "ammo": f"{ammo_words(snap.ammo)} ({snap.ammo} rounds)",
            "took_damage_in_last_second": took_damage_recently,
            "can_move": caps.can_move,
            "can_only_turn_and_shoot": not caps.can_move,
        },
        "situation": situation,
        "enemies": enemy_state,
        "pickups": pickup_state,
    }
    return Described(state=state, enemy_keys=enemy_keys, pickup_keys=pickup_keys)
