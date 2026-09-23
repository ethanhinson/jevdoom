# jevdoom

Jev (TypeSafe System One) plays ViZDoom. Jev decides what matters each moment - which enemy to deal with, whether to
fight, hold, retreat or grab a pickup - and plain code turns that into button presses.

## Run

```sh
cp .env.example .env   # then put your TypeSafe key in it
uv run jevdoom --scenario defend_the_center --episodes 3
```

`uv run jevdoom --help` lists the scenarios and options. Each run writes a JSONL log of every Jev call to `logs/`.

## Watch the calls live with Jeview

[Jeview](https://github.com/andududu/jeview) is a local gateway that sits between this code and TypeSafe, records
every call, and draws them on a live map. It is cloned beside this project at `../jeview` and needs Node 24.

```sh
# terminal 1: start Jeview and open the viewer at http://127.0.0.1:4777/
cd ../jeview && ./launch.sh

# terminal 2: play, sending Jev calls through Jeview
uv run jevdoom --jeview
```

The first time, set your TypeSafe key in the viewer (the key icon, top right). Calls are grouped under the `jevdoom`
label in the viewer. `--jeview URL` points at a Jeview on another port.

## Develop

```sh
uv run pytest
uv run ruff check .
```
