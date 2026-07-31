"""Save/continue persistence for a playthrough.

No pygame import here — like `state.py`, this is pure Python so it stays
testable without a display. It knows how to turn a `GameState` (plus the
cosmetic traveler/companion look info `game.py` tracks) into JSON on disk and
back, and how to list what's already saved. It deliberately doesn't know
about `scenes.PersonAppearance` either: appearances cross this boundary as
plain dicts of RGB tuples and floats, so this module never needs to import
the pygame-dependent rendering layer to save or load one.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fernweh.state import SEASONS, STAGES_PER_SEASON, Companion, GameState

# Saves live outside the repo's tracked content — `.gitignore` excludes this
# directory entirely, since a player's progress is local runtime data, not
# something that belongs in version control (same reasoning as `.venv/`).
SAVES_DIR = Path(__file__).resolve().parent.parent.parent / "saves"


@dataclass(frozen=True)
class SaveSummary:
    """Just enough about a save to show it in the continue-journey list."""

    id: str
    updated_at: str
    season: str
    stage_index: int
    companion_names: tuple[str, ...]
    ended: bool
    end_reason: str | None

    def describe(self) -> str:
        """A one-line label for this save, for the continue-journey menu."""
        party = f" · with {', '.join(self.companion_names)}" if self.companion_names else ""
        season_label = self.season.capitalize()
        if self.ended:
            outcome = (
                "reached the end" if self.end_reason == "completed" else "the road ended early"
            )
            return f"Revisit — {outcome}, {season_label}{party}"
        # 1-based "day" reads more naturally to a player than a 0-based index.
        return f"Continue — {season_label}, day {self.stage_index + 1}{party}"


def _save_path(save_id: str) -> Path:
    return SAVES_DIR / f"{save_id}.json"


def now_iso() -> str:
    """The current UTC time in the same ISO format every timestamp in a save uses."""
    return datetime.now(timezone.utc).isoformat()


def new_save_id() -> str:
    """Generate a fresh save id: sortable by creation time, unique per run."""
    # The timestamp alone could collide if two saves were ever created in the
    # same second (unlikely here, but cheap to rule out) — the short random
    # suffix guarantees uniqueness without needing to check existing files.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def save_game(
    save_id: str,
    state: GameState,
    traveler_appearance: dict[str, Any],
    companion_appearances: dict[str, dict[str, Any]],
    created_at: str | None = None,
) -> None:
    """Write the current playthrough to disk, creating or overwriting `save_id`.

    Writes to a temp file and `os.replace`s it into place rather than writing
    the target file directly — an autosave fires after every single choice,
    including whenever the player might kill the process moments later, so a
    write that's interrupted partway must never leave a half-written, corrupt
    save file behind. `os.replace` is atomic on both POSIX and Windows.
    """
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    now = now_iso()
    payload = {
        "id": save_id,
        "created_at": created_at or now,
        "updated_at": now,
        "state": _state_to_dict(state),
        "traveler_appearance": traveler_appearance,
        "companion_appearances": companion_appearances,
    }
    target = _save_path(save_id)
    tmp_path = target.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2))
    os.replace(tmp_path, target)


@dataclass(frozen=True)
class LoadedGame:
    """Everything needed to resume a playthrough exactly where it was left."""

    state: GameState
    traveler_appearance: dict[str, Any]
    companion_appearances: dict[str, dict[str, Any]]
    created_at: str


def load_game(save_id: str) -> LoadedGame:
    """Reconstruct a `GameState` and its cosmetic appearances from a saved file."""
    payload = json.loads(_save_path(save_id).read_text())
    return LoadedGame(
        state=_state_from_dict(payload["state"]),
        traveler_appearance=payload["traveler_appearance"],
        companion_appearances=payload["companion_appearances"],
        created_at=payload["created_at"],
    )


def list_saves() -> list[SaveSummary]:
    """Return every save's summary, most recently updated first."""
    if not SAVES_DIR.exists():
        return []
    summaries = []
    for path in SAVES_DIR.glob("*.json"):
        # A save corrupted by, say, a kill at the exact instant of an
        # (already-atomic, but let's be defensive) filesystem hiccup
        # shouldn't take down the whole continue-journey list — it's just
        # skipped rather than raising out of the menu screen.
        try:
            payload = json.loads(path.read_text())
            state_dict = payload["state"]
            summaries.append(
                SaveSummary(
                    id=payload["id"],
                    updated_at=payload["updated_at"],
                    season=_season_for_stage(state_dict["stage_index"]),
                    stage_index=state_dict["stage_index"],
                    companion_names=tuple(c["name"] for c in state_dict["companions"]),
                    ended=state_dict["ended"],
                    end_reason=state_dict["end_reason"],
                )
            )
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda s: s.updated_at, reverse=True)
    return summaries


def delete_save(save_id: str) -> None:
    """Remove a save file, if it exists."""
    _save_path(save_id).unlink(missing_ok=True)


def _season_for_stage(stage_index: int) -> str:
    season_number = min(stage_index // STAGES_PER_SEASON, len(SEASONS) - 1)
    return SEASONS[season_number]


def _state_to_dict(state: GameState) -> dict[str, Any]:
    return {
        "energy": state.energy,
        "supplies": state.supplies,
        "stage_index": state.stage_index,
        # The chosen journey plan must be saved: without it, resuming would
        # re-roll a different sequence of stages and the story would change
        # under the player mid-journey.
        "plan": list(state.plan),
        "companions": [
            {
                "id": c.id,
                "name": c.name,
                "one_line_trait": c.one_line_trait,
                "joined_at_stage": c.joined_at_stage,
            }
            for c in state.companions
        ],
        "memories": list(state.memories),
        "afflictions": sorted(state.afflictions),
        "ended": state.ended,
        "end_reason": state.end_reason,
    }


def _state_from_dict(data: dict[str, Any]) -> GameState:
    return GameState(
        energy=data["energy"],
        supplies=data["supplies"],
        stage_index=data["stage_index"],
        # Older saves (pre-randomization) have no plan; an empty plan is fine
        # for a finished journey being revisited, and `game.py` guards the
        # in-progress case.
        plan=list(data.get("plan", [])),
        companions=[
            Companion(
                id=c["id"],
                name=c["name"],
                one_line_trait=c["one_line_trait"],
                joined_at_stage=c["joined_at_stage"],
            )
            for c in data["companions"]
        ],
        memories=list(data["memories"]),
        afflictions=set(data["afflictions"]),
        ended=data["ended"],
        end_reason=data["end_reason"],
    )
