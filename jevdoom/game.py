"""Thin wrapper around a ViZDoom game that exposes a plain snapshot each tic."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import vizdoom as vzd

SCENARIOS = {
    "defend_the_center": "defend_the_center.cfg",
    "deadly_corridor": "deadly_corridor.cfg",
    "freedoom2": "freedoom2.cfg",
}

# Fixed order so snapshot() can index by position.
GAME_VARIABLES = [
    vzd.GameVariable.HEALTH,
    vzd.GameVariable.ARMOR,
    vzd.GameVariable.SELECTED_WEAPON,
    vzd.GameVariable.SELECTED_WEAPON_AMMO,
    vzd.GameVariable.ANGLE,
    vzd.GameVariable.POSITION_X,
    vzd.GameVariable.POSITION_Y,
    vzd.GameVariable.KILLCOUNT,
    vzd.GameVariable.DAMAGE_TAKEN,
    vzd.GameVariable.ITEMCOUNT,
]

# Positive delta values turn the player to the right in the engine. Our code
# works in "positive = left" like the rest of Doom's angle math, so flip it.
TURN_DELTA_SIGN = -1.0
MAX_TURN_DELTA = 30.0
APPROACH_STEP = 1.0  # Doom units closer than the previous snapshot counts as approaching

MONSTER_NAMES = {
    "Demon",
    "Spectre",
    "MarineChainsawVzd",
    "Zombieman",
    "ShotgunGuy",
    "ChaingunGuy",
    "DoomImp",
    "LostSoul",
    "Cacodemon",
    "HellKnight",
    "BaronOfHell",
    "Revenant",
    "Mancubus",
    "Arachnotron",
    "PainElemental",
    "Archvile",
    "WolfensteinSS",
    "Cyberdemon",
    "SpiderMastermind",
    "Fatso",
    "CommanderKeen",
}

PICKUP_NAMES = {
    "Stimpack",
    "Medikit",
    "HealthBonus",
    "ArmorBonus",
    "GreenArmor",
    "BlueArmor",
    "Clip",
    "ClipBox",
    "Shell",
    "ShellBox",
    "RocketAmmo",
    "RocketBox",
    "Cell",
    "CellPack",
    "Shotgun",
    "SuperShotgun",
    "Chaingun",
    "RocketLauncher",
    "PlasmaRifle",
    "BFG9000",
    "Chainsaw",
    "Backpack",
    "Soulsphere",
    "Megasphere",
    "Berserk",
    "InvulnerabilitySphere",
    "BlurSphere",
    "RadSuit",
    "Infrared",
    "Allmap",
    "RedCard",
    "BlueCard",
    "YellowCard",
    "RedSkull",
    "BlueSkull",
    "YellowSkull",
}


@dataclass(frozen=True)
class Actor:
    id: int
    name: str
    category: str  # "monster", "pickup" or "other"
    distance: float
    rel_bearing: float  # degrees; positive means to the player's left
    visible: bool  # currently drawn on screen
    approaching: bool  # moving toward the player


@dataclass(frozen=True)
class Snapshot:
    tic: int
    health: int
    armor: int
    weapon: int
    ammo: int
    angle: float
    x: float
    y: float
    kills: int
    damage_taken: int
    items: int
    actors: tuple[Actor, ...]

    @property
    def enemies(self) -> tuple[Actor, ...]:
        return tuple(a for a in self.actors if a.category == "monster")

    @property
    def pickups(self) -> tuple[Actor, ...]:
        return tuple(a for a in self.actors if a.category == "pickup")


@dataclass(frozen=True)
class Capabilities:
    can_attack: bool
    can_move: bool
    can_strafe: bool


PICKUP_CATEGORIES = {"Armor", "Health", "Ammo", "Weapon", "Key", "Powerup", "Artifact", "Item", "Pickup"}


def categorize(name: str, category: str = "") -> str:
    """Classify an engine actor. The engine's own category wins; names are the fallback."""
    if category == "Monster" or name in MONSTER_NAMES:
        return "monster"
    if category in PICKUP_CATEGORIES or name in PICKUP_NAMES:
        return "pickup"
    return "other"


def relative_bearing(player_angle: float, dx: float, dy: float) -> float:
    """Bearing of (dx, dy) relative to the player's facing, in (-180, 180]."""
    bearing = math.degrees(math.atan2(dy, dx))
    return (bearing - player_angle + 180.0) % 360.0 - 180.0


class DoomSession:
    def __init__(self, scenario: str, window: bool = True, skill: int | None = None):
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}; pick one of {sorted(SCENARIOS)}")
        game = vzd.DoomGame()
        game.load_config(os.path.join(vzd.scenarios_path, SCENARIOS[scenario]))
        game.set_window_visible(window)
        game.set_mode(vzd.Mode.PLAYER)
        game.set_screen_resolution(vzd.ScreenResolution.RES_640X480)
        game.set_render_hud(True)
        game.set_render_crosshair(True)
        game.set_render_weapon(True)
        game.set_labels_buffer_enabled(True)
        game.set_objects_info_enabled(True)
        game.set_available_game_variables(GAME_VARIABLES)
        game.add_available_button(vzd.Button.TURN_LEFT_RIGHT_DELTA, MAX_TURN_DELTA)
        if skill is not None:
            game.set_doom_skill(skill)
        game.init()
        self.game = game
        self.buttons: list[vzd.Button] = game.get_available_buttons()
        self._index = {b: i for i, b in enumerate(self.buttons)}
        self.capabilities = Capabilities(
            can_attack=vzd.Button.ATTACK in self._index,
            can_move=vzd.Button.MOVE_FORWARD in self._index,
            can_strafe=vzd.Button.MOVE_LEFT in self._index,
        )
        self.player_id: int | None = None
        # Monsters step by moving their position, not by carrying velocity, so
        # "approaching" is judged by how the distance changed since last snapshot.
        self._last_distance: dict[int, float] = {}

    def new_episode(self) -> None:
        self.game.new_episode()
        self.player_id = None
        self._last_distance = {}

    def finished(self) -> bool:
        return self.game.is_episode_finished()

    def snapshot(self, tic: int, radius: float = 1500.0) -> Snapshot | None:
        state = self.game.get_state()
        if state is None:
            return None
        gv = state.game_variables
        health, armor, weapon, ammo, angle, px, py, kills, damage, items = (float(v) for v in gv)
        visible_ids = {label.object_id for label in state.labels}
        actors: list[Actor] = []
        distances: dict[int, float] = {}
        for obj in state.objects:
            if obj.name == "DoomPlayer":
                self.player_id = obj.id
                continue
            category = categorize(obj.name, getattr(obj, "category", ""))
            if category == "other":
                continue
            dx, dy = obj.position_x - px, obj.position_y - py
            distance = math.hypot(dx, dy)
            if distance > radius:
                continue
            distances[obj.id] = distance
            previous = self._last_distance.get(obj.id)
            approaching = previous is not None and previous - distance > APPROACH_STEP
            actors.append(
                Actor(
                    id=obj.id,
                    name=obj.name,
                    category=category,
                    distance=distance,
                    rel_bearing=relative_bearing(angle, dx, dy),
                    visible=obj.id in visible_ids,
                    approaching=approaching,
                )
            )
        self._last_distance = distances
        actors.sort(key=lambda a: a.distance)
        return Snapshot(
            tic=tic,
            health=int(health),
            armor=int(armor),
            weapon=int(weapon),
            ammo=int(ammo),
            angle=angle,
            x=px,
            y=py,
            kills=int(kills),
            damage_taken=int(damage),
            items=int(items),
            actors=tuple(actors),
        )

    def act(self, pressed: dict[vzd.Button, float], tics: int = 1) -> float:
        """Apply one tic of input. `pressed` maps buttons to 1/0 or a delta value."""
        vector = [0.0] * len(self.buttons)
        for button, value in pressed.items():
            index = self._index.get(button)
            if index is None:
                continue
            if button == vzd.Button.TURN_LEFT_RIGHT_DELTA:
                value = TURN_DELTA_SIGN * max(-MAX_TURN_DELTA, min(MAX_TURN_DELTA, value))
            vector[index] = float(value)
        return self.game.make_action(vector, tics)

    def close(self) -> None:
        self.game.close()
