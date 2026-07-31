<div align="center">

![Fernweh banner](https://capsule-render.vercel.app/api?type=soft&color=0:8FBF7F,25:E8C468,50:E0813E,75:6E8FB5,100:E8EEF2&height=200&section=header&text=Fernweh&fontSize=64&fontColor=2E2A26&fontAlignY=40&desc=a%20walk%20from%20spring%20to%20winter&descAlignY=62&descSize=20&descColor=2E2A26&animation=fadeIn)

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Georgia&size=18&pause=2200&color=6B6B6B&center=true&vCenter=true&width=560&lines=a+walk+from+spring+to+winter.;no+combat.+no+timer.+no+score.;however+you+arrive%2C+you+arrive.)](https://github.com/JustThatRandomCoder/fernweh)

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: All Rights Reserved](https://img.shields.io/badge/license-all%20rights%20reserved-6E8FB5)](LICENSE)
[![Built with pygame-ce](https://img.shields.io/badge/built%20with-pygame--ce-8FBF7F)](https://github.com/pygame-community/pygame-ce)

</div>

Fernweh is a calm, single-player narrative journey across four seasons. There's no combat,
no open map, no timer or score on screen — you walk a fixed path from spring to winter,
stage by stage, making small choices that trade off what little you're carrying. Every
scene, every color, every flake of snow or falling leaf is drawn procedurally with pygame
primitives — there are no image assets in this repository.

<!-- TODO: add gameplay GIF once recorded — a short screen capture (ScreenToGif on
Windows, or macOS's built-in Cmd+Shift+5 screen recording, converted to GIF with
`ffmpeg` or gifski) of a full stage: scene, situation text, and a choice being made. -->

## How it plays

- **The journey.** Four seasons — Spring, Summer, Autumn, Winter — five stages each, twenty
  in total, always in that order. No branching map: your choices shape what happens to you,
  not where the road goes.
- **Resources.** You're sustained by two things: **Energy** and **Supplies**, both 0–100.
  Both drain a little each stage on their own, and drain faster as the seasons turn colder
  or as more companions travel with you. Choices can cost more of one to spare the other, or
  restore what the road has taken.
- **Companions.** Along the way you can invite up to four travelers to join you. Company is
  good for the telling, but more mouths to feed means faster Supplies drain — every
  invitation is a real tradeoff, not a free bonus.
- **Afflictions.** Hardship follows as status conditions — Exhausted, Ill, Frostbitten —
  that speed up drain, grey out reckless choices, and visibly darken and slow the game the
  more of them are active. Specific rest and recovery choices cure them, usually over a
  stage or two.
- **The ending.** If Energy or Supplies ever hits zero, the journey ends early, wherever it
  happens to be — quietly, not with a "game over" screen. Reaching the twentieth stage or
  running out early both lead to the same place: a short, procedurally composed closing
  passage built from how you arrived (rested or exhausted, alone or in company, still
  recovering or not) and a small list of the keepsakes and companions you gathered. That's
  the score. It's never shown as a number.

## Screenshots

<!-- TODO: add gameplay GIF once recorded -->

## Installation & running

Requires Python 3.11+. Nothing else — no manual virtual environment, no manual
`pip install`, no activation step.

```bash
git clone https://github.com/JustThatRandomCoder/fernweh.git fernweh
cd fernweh
python3 fernweh.py
```

The first run sets up a local virtual environment and installs dependencies
automatically (with a short status message while it does), then opens the window and
starts with a click-through intro (also reachable later by pressing `H`). Every run after
that skips straight to launching the game.

To test that first-run experience again as if you'd only just cloned the repo, reset with:

```bash
python3 fresh-start.py            # asks before removing anything
python3 fresh-start.py --dry-run  # just show what it would remove
```

This removes the local virtual environment (the installed dependencies), all saved games,
and generated caches — nothing tracked by git — so the next launch reruns the whole setup
from scratch.

## Running tests

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest tests/ -v
```

See [`TESTING.md`](TESTING.md) for the full setup walkthrough and what's covered.

## Tech & architecture

Python 3.11+ and [pygame-ce](https://github.com/pygame-community/pygame-ce) for rendering,
with the game's rules (resources, stage progression, afflictions, ending generation) kept as
pure Python with zero `pygame` imports, so the whole logic layer is unit-tested headlessly.
All visuals are procedural pygame primitives — gradients, particles, and a small hand-rolled
tweening module — no image assets. Narrative content lives in
[`content/stages.json`](content/stages.json), not hardcoded in engine code. See
[`DOCUMENTATION.md`](DOCUMENTATION.md) for the full technical writeup, including the
decisions behind each system.

## Easy start (for non-coders)

Don't want to touch a terminal? You don't have to. Once you have the game's folder:

1. Open the **`fernweh`** folder.
2. Double-click the **`START-GAME-FERNWEH`** file:
   - On **Mac**, use `START-GAME-FERNWEH.command`.
   - On **Windows**, use `START-GAME-FERNWEH.bat`.
3. The first time, a window opens and shows it setting things up — this can take a
   minute while it installs everything the game needs. Just leave it open.
4. When it's done, the game opens on its own. Every time after that, it starts right away.

That's it. No commands, no setup.

<details>
<summary>A couple of things that might come up</summary>

- **(Mac) "macOS cannot verify the developer" / it won't open.** Right-click (or
  Control-click) the `START-GAME-FERNWEH.command` file, choose **Open**, then click **Open**
  again in the dialog. You only need to do this once.
- **(Windows) a blue "Windows protected your PC" box.** Click **More info**, then **Run
  anyway**. You only need to do this once.
- **It says Python isn't installed.** The launcher will tell you and link to
  [python.org/downloads](https://www.python.org/downloads/). Install Python 3 (on Windows,
  tick **Add Python to PATH** during setup), then double-click `START-GAME-FERNWEH` again.
- **How do I get the folder in the first place?** Download it from the project's GitHub page
  (the green **Code** button → **Download ZIP**), then unzip it. The `START-GAME-FERNWEH`
  files are inside.

> The one-click launchers cover macOS and Windows. On Linux, use the terminal steps under
> [Installation & running](#installation--running) above.

</details>

## License

Copyright © 2026 Julius Grimm. All rights reserved. Fernweh is free to download and play for
personal, non-commercial use. Modifying and redistributing the game, or using its code in
another project, requires prior written permission from the author — see
[`LICENSE`](LICENSE) for the full terms, and reach out to me@juliusgrimm.dev to request
permission beyond what's granted there.
