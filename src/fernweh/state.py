"""Pure game-state model: resources, companions, memories, afflictions.

No pygame import here or anywhere it's used from — this module is fully
unit-testable without a display.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The two resources the whole game balances against; both live on a 0-100 scale.
MAX_ENERGY = 100
MAX_SUPPLIES = 100
MAX_COMPANIONS = 4
STAGES_PER_SEASON = 5
TOTAL_STAGES = 20

# Fixed season order — the journey always walks through these four in this order.
SEASONS = ("spring", "summer", "autumn", "winter")


@dataclass(frozen=True)
class Companion:
    """A named traveling companion recruited during the journey."""

    id: str
    name: str
    one_line_trait: str
    joined_at_stage: int


@dataclass
class GameState:
    """Mutable state for a single playthrough of Fernweh."""

    energy: int = MAX_ENERGY
    supplies: int = MAX_SUPPLIES
    stage_index: int = 0
    companions: list[Companion] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    afflictions: set[str] = field(default_factory=set)
    ended: bool = False
    end_reason: str | None = None

    @property
    def season(self) -> str:
        """Season name for the current stage index."""
        # Season is derived from stage_index rather than stored separately, so
        # the two can never drift out of sync. `min(...)` guards against the
        # final stage landing exactly on a season boundary and overshooting.
        season_number = min(self.stage_index // STAGES_PER_SEASON, len(SEASONS) - 1)
        return SEASONS[season_number]

    @property
    def is_failed(self) -> bool:
        """Whether the journey ended early from a depleted resource."""
        return self.end_reason == "failure"

    @property
    def is_complete(self) -> bool:
        """Whether the journey ended by reaching the final stage."""
        return self.end_reason == "completed"

    def apply_energy_delta(self, delta: int) -> None:
        """Adjust energy by `delta`, clamped to [0, MAX_ENERGY], checking failure."""
        self.energy = max(0, min(MAX_ENERGY, self.energy + delta))
        self._check_failure()

    def apply_supplies_delta(self, delta: int) -> None:
        """Adjust supplies by `delta`, clamped to [0, MAX_SUPPLIES], checking failure."""
        self.supplies = max(0, min(MAX_SUPPLIES, self.supplies + delta))
        self._check_failure()

    def _check_failure(self) -> None:
        # Runs after every resource change so a fatal drain is caught the
        # instant it happens, rather than needing a separate "check failure"
        # step the caller might forget to call.
        if not self.ended and (self.energy <= 0 or self.supplies <= 0):
            self.ended = True
            self.end_reason = "failure"

    def add_companion(self, companion: Companion) -> bool:
        """Add a companion if there's room. Returns whether it was added."""
        if len(self.companions) >= MAX_COMPANIONS:
            return False
        self.companions.append(companion)
        return True

    def add_memory(self, memory: str) -> None:
        """Record a collected memory."""
        self.memories.append(memory)

    def add_affliction(self, affliction_id: str) -> None:
        """Mark an affliction as active."""
        self.afflictions.add(affliction_id)

    def remove_affliction(self, affliction_id: str) -> None:
        """Clear an active affliction, if present."""
        self.afflictions.discard(affliction_id)

    def advance_stage(self) -> None:
        """Move to the next stage, or mark the journey complete at the end."""
        # Once ended, this is a no-op — a stray call after the journey is over
        # (failure or completion) can't resurrect it or skip stages.
        if self.ended:
            return
        if self.stage_index >= TOTAL_STAGES - 1:
            self.ended = True
            self.end_reason = "completed"
        else:
            self.stage_index += 1
