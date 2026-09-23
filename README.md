# jevfun

Jev (TypeSafe System One) plays games. Jev decides what matters each moment and plain code does the rest.

- **jevdoom**: ViZDoom. Jev picks which enemy to deal with and whether to fight, hold, retreat or grab a pickup;
  code turns that into button presses.
- **jevtetris**: Tetris. Code lists every placement the piece could reach, with what the board looks like after
  each one; Jev picks one; code plays it. Holding is an option like any other.
- **jevgameboy**: the same brain playing the real Game Boy Tetris in the [PyBoy](https://github.com/Baekalfen/PyBoy)
  emulator, reading the board off the screen tiles and pressing the real buttons.

## Run

```sh
cp .env.example .env   # then put your TypeSafe key in it
uv run jevdoom --scenario defend_the_center --episodes 3
uv run jevtetris --games 1
```

`--help` on any of them lists the options. Each run writes a JSONL log of every Jev call to `logs/`. In the Tetris
window, + and - change the speed, space pauses, esc quits; the faint outlines are the placements Jev nearly chose.

## Game Boy

The Tetris ROM is not included. Put your own copy at `roms/tetris.gb` (the folder is ignored by git), then:

```sh
uv run jevgameboy            # opens the emulator window
uv run jevgameboy --speed 0  # as fast as the emulator can go
```

Jev sees the 10 by 18 field, the falling piece and the one preview piece, and there is no hold. Code turns the
piece with A until the orientation matches, slides it, holds Down, and waits for the screen to match the
placement Jev chose. If it does not match, the board is re-read from the screen and play continues.

## Watch the calls live with Jeview

[Jeview](https://github.com/andududu/jeview) is a local gateway that sits between this code and TypeSafe, records
every call, and draws them on a live map. It is cloned beside this project at `../jeview` and needs Node 24.

```sh
# terminal 1: start Jeview and open the viewer at http://127.0.0.1:4777/
cd ../jeview && ./launch.sh

# terminal 2: play, sending Jev calls through Jeview
uv run jevdoom --jeview
uv run jevtetris --jeview
uv run jevgameboy --jeview
```

The first time, set your TypeSafe key in the viewer (the key icon, top right). Calls are grouped under the
`jevdoom`, `jevtetris` and `jevgameboy` labels in the viewer. `--jeview URL` points at a Jeview on another port.

## Develop

```sh
uv run pytest
uv run ruff check .
```
