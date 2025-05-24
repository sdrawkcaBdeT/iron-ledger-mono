"""
fatigue_morale.py – stamina drain, morale shocks, exhaustion & surrender logic
=============================================================================

Drop-in module for *The Arena* codebase.  Pure stdlib, Python 3.12.

Public surface
--------------
create_fatigue_morale_systems(world)  → injects the three systems & new stores
ActivitySampleEvent                   → importable for one-liner shims
Stamina, Morale, MoraleState          → components

Design snapshot 2025-04-30 – matches “Topic 4-A” spec with all subsequent
clarifications.
"""
from __future__ import annotations

# ───────────────────────────────────── stdlib
import enum
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Sequence, Tuple, Type
# ──────────────────────────────────── type aliases
EntityId = int
Tick     = int

# ---------------------------------------------------------------------------#
#                            1 - COMPONENTS                                  #
# ---------------------------------------------------------------------------#

@dataclass(slots=True)
class Stamina:
    """Per-fighter energy store."""
    max_pts: int = 100
    curr_pts: float = 100.0
    regen_per_tick: float = 0.2      # 0.2 sp / 0.05 s ⇒ 4 sp / s
    exhausted: bool = False


class MoraleState(enum.StrEnum):
    DETERMINED = "DETERMINED"
    COMPOSED   = "COMPOSED"
    UNCERTAIN  = "UNCERTAIN"
    FRACTURED  = "FRACTURED"
    DESPERATE  = "DESPERATE"


# editable bands – lower bound inclusive, ordered high→low
MORALE_BANDS: Dict[MoraleState, int] = {
    MoraleState.DETERMINED: 90,
    MoraleState.COMPOSED:   65,
    MoraleState.UNCERTAIN:  40,
    MoraleState.FRACTURED:  15,
    MoraleState.DESPERATE:   0,
}

@dataclass(slots=True)
class Morale:
    """Mental resilience gauge."""
    value: int = 100
    state: MoraleState = MoraleState.DETERMINED


# ---------------------------------------------------------------------------#
#                               2 - EVENTS                                   #
# ---------------------------------------------------------------------------#

@dataclass(slots=True)
class ActivitySampleEvent:
    """Posted once per tick for any locomotion / attack / defence animation."""
    tick: Tick
    entity_id: EntityId
    action_id: str
    metres_moved: float = 0.0


@dataclass(slots=True)
class ExhaustionEvent:
    tick: Tick
    entity_id: EntityId


@dataclass(slots=True)
class SurrenderEvent:
    tick: Tick
    entity_id: EntityId
    cause: Literal["low_morale", "exhaustion"]


# ---------------------------------------------------------------------------#
#                    3 - SYSTEM IMPLEMENTATIONS                              #
# ---------------------------------------------------------------------------#

# Constants
TICK_LEN_S: float = 0.05                             # 20 Hz engine step
_BLOOD_WINDOW_TICKS: int = int(10 / TICK_LEN_S)      # 10 s ⇒ 200 ticks
_MAX_NEG_SHOCK: int = 15                             # used for look-ahead


class FatigueSystem:
    """
    Consumes ActivitySampleEvent and drains stamina.

    Drain per tick = ACTIONS[action_id].stamina / ACTIONS[action_id].ticks.
    """

    def __init__(self, world):
        self.world = world
        from action_registry import ACTIONS   # global catalogue
        self.actions = ACTIONS
        self.post_event = world.post_event

    def __call__(self) -> None:
        for ev in self.world.consume_events(ActivitySampleEvent):
            stamina: Stamina = self.world.stamina[ev.entity_id]

            spec = self.actions[ev.action_id]
            drain = spec.stamina / spec.ticks
            stamina.curr_pts = max(0.0, stamina.curr_pts - drain)

            if not stamina.exhausted and stamina.curr_pts <= 0.0:
                stamina.exhausted = True
                self.post_event(ExhaustionEvent(self.world.tick, ev.entity_id))


class RecoverySystem:
    """Regenerates stamina for idle entities."""

    def __init__(self, world):
        self.world = world
        self._activity_seen: defaultdict[EntityId, Tick] = defaultdict(int)

    def __call__(self) -> None:
        tick = self.world.tick
        # record activity for this tick
        for ev in self.world.peek_events(ActivitySampleEvent):
            self._activity_seen[ev.entity_id] = tick

        for eid, stamina in self.world.stamina.items():
            # idle if no ActivitySample this tick
            if self._activity_seen.get(eid, -1) == tick:
                continue

            morale = self.world.morale[eid]
            if stamina.exhausted:
                continue  # no regen while exhausted

            regen = stamina.regen_per_tick
            if morale.state is MoraleState.DESPERATE:
                regen *= 0.25

            stamina.curr_pts = min(stamina.max_pts, stamina.curr_pts + regen)

            # auto-clear exhausted once above 25% reserve
            if stamina.exhausted and stamina.curr_pts >= 0.25 * stamina.max_pts:
                stamina.exhausted = False


class MoraleSystem:
    """
    Aggregates morale shocks from combat, blood loss & exhaustion.
    Emits SurrenderEvent under DESPERATE conditions.
    """

    def __init__(self, world):
        self.world = world
        self.post_event = world.post_event
        self._blood_tick_counter: Dict[EntityId, int] = defaultdict(int)

    @staticmethod
    def _state_from_value(val: int) -> MoraleState:
        for state, lower in MORALE_BANDS.items():
            if val >= lower:
                return state
        return MoraleState.DESPERATE  # fallback

    def __call__(self) -> None:
        tick = self.world.tick
        delta: Dict[EntityId, float] = defaultdict(float)

        # (a) Impact & Death events
        for ev in self.world.peek_events("ImpactEvent"):
            delta[ev.attacker_id] += 5
            delta[ev.defender_id] -= 10

        for ev in self.world.peek_events("DeathEvent"):
            delta[ev.entity_id] -= 100

        # (b) Exhaustion events => immediate big negative shock
        for ev in self.world.consume_events(ExhaustionEvent):
            delta[ev.entity_id] -= _MAX_NEG_SHOCK

        # (c) Blood-loss steady erosion
        for eid, vitals in self.world.vitals.items():
            self._blood_tick_counter[eid] += 1
            if self._blood_tick_counter[eid] >= _BLOOD_WINDOW_TICKS:
                self._blood_tick_counter[eid] = 0
            pct_lost = 100.0 * (1 - vitals.blood_ml / vitals.max_blood_ml)
            delta[eid] += -0.0025 * pct_lost

        # Apply morale changes
        for eid, d_moral in delta.items():
            morale = self.world.morale[eid]
            stamina = self.world.stamina[eid]

            morale.value = max(0, min(100, int(morale.value + d_moral)))
            morale.state = self._state_from_value(morale.value)

            # Check surrender conditions if DESPERATE
            if morale.state is MoraleState.DESPERATE:
                projected = morale.value - _MAX_NEG_SHOCK
                if projected < 10 or stamina.exhausted:
                    cause = "exhaustion" if stamina.exhausted else "low_morale"
                    self.post_event(SurrenderEvent(tick, eid, cause))


# ---------------------------------------------------------------------------#
#                    4 - FACTORY & REGISTRATION                              #
# ---------------------------------------------------------------------------#

def create_fatigue_morale_systems(world) -> None:
    """
    Add morale/stamina logic to 'world'. This:
      - Ensures an event API
      - Adds AttackSystem if missing
      - Sets up 'world.stamina' and 'world.morale' dicts
      - Registers FatigueSystem, RecoverySystem, MoraleSystem
      - Leaves 'Weapon', 'Opponent', etc. to other modules
    """
    from attack import _ensure_event_api
    from attack import AttackSystem

    _ensure_event_api(world)
    world._event_q = getattr(world, "_event_q", [])

    if AttackSystem not in {type(s) for s in world._systems}:
        world.add_system(AttackSystem())

    if not hasattr(world, "tick_once"):
        def _tick_once() -> None:
            for sys in world._systems:
                try:
                    sys()
                except TypeError:
                    sys(world, 20_000_000)
            world.tick += 1

        if not hasattr(world, "peek_events"):
            def _peek_events(cls=None):
                return [e for e in world._event_q
                        if cls is None
                        or isinstance(e, cls)
                        or getattr(e, "__name__", None) == cls]
            world.peek_events = _peek_events

        world.tick = 0
        world.tick_once = _tick_once  # type: ignore[attr-defined]

    # Build brand-new stamina/morale stores
    world.stamina = {}
    world.morale  = {}

    # Seed from existing fighters
    for eid in getattr(world, "combatants", []):
        world.stamina[eid] = Stamina()
        world.morale[eid]  = Morale()

    # Register the systems
    world.add_system(FatigueSystem(world))
    world.add_system(RecoverySystem(world))
    world.add_system(MoraleSystem(world))


# ---------------------------------------------------------------------------#
#                    5 - PYTEST REGRESSION SUITE                             #
# ---------------------------------------------------------------------------#

def _terminal_events_for(world) -> Tuple[Type]:
    """Return SurrenderEvent plus DeathEvent if it exists."""
    surrender = SurrenderEvent
    death = getattr(world, "DeathEvent", None)
    if death is None:
        return (surrender,)
    return (surrender, death)

def _simulate_bout(world, max_ticks: int = 100_000) -> Tuple[str, Tick]:
    """
    Run until SurrenderEvent or DeathEvent is seen, or until a tick budget.
    """
    wanted = _terminal_events_for(world)
    for i in range(max_ticks):
        world.tick_once()
        for ev in world.consume_events(wanted):
            return ev.__class__.__name__, ev.tick
    if i == max_ticks - 1:  # timed out
        print("\n[DEBUG] timed-out after", max_ticks, "ticks")
        print(" last 20 ImpactEvents:",
              [e.tick for e in world.peek_events("ImpactEvent")[-20:]])
        for eid in getattr(world, "combatants", []):
            m = world.morale[eid].value
            s = world.stamina[eid].curr_pts
            print(f"  E{eid}: morale {m:3d}  stamina {s:5.1f}")
        print("  queue contents:",
              [e.__class__.__name__ for e in world._event_q][:10])
    raise RuntimeError("No terminal event within tick budget")


def _build_world(rng_seed: int = 42, n_pairs: int = 1):
    """
    Creates a minimal ECS world, spawns fighters, attaches fatigue/morale.
    Adds a final fallback to ensure each fighter actually has a Weapon/Opponent.
    """
    from engine_tick import World
    import random

    w = World(rng=random.Random(rng_seed))

    # Attempt user-defined spawner from arena_blueprints
    try:
        from arena_blueprints import spawn_fighters_pair
    except ModuleNotFoundError:
        def spawn_fighters_pair(world):
            from movement_collision import (
                _require_store,
                Position2D,
                CollisionRadius,
            )
            from attack import _build_maul, Weapon, Opponent

            a, b = world.entities.next_id(), world.entities.next_id()

            _require_store(world, Position2D).add(a, Position2D(-0.3, 0.0))
            _require_store(world, Position2D).add(b, Position2D(+0.3, 0.0))
            _require_store(world, CollisionRadius).add(a, CollisionRadius(0.3))
            _require_store(world, CollisionRadius).add(b, CollisionRadius(0.3))

            weapon = _build_maul()
            _require_store(world, Weapon).add(a, weapon)
            _require_store(world, Weapon).add(b, weapon)

            _require_store(world, Opponent).add(a, Opponent(b))
            _require_store(world, Opponent).add(b, Opponent(a))

            if not hasattr(world, "combatants"):
                world.combatants = []
            world.combatants.extend((a, b))

    if not hasattr(w, "combatants"):
        w.combatants = []

    # Spawn pairs
    for _ in range(n_pairs):
        spawn_fighters_pair(w)

    # Attach fatigue & morale systems
    create_fatigue_morale_systems(w)

    # ---------------------------------------------------------------------
    # FINAL FALLBACK: ensure each fighter has a Weapon & Opponent
    from attack import _build_maul, Weapon, Opponent
    from movement_collision import _require_store
    wstore_weapon    = _require_store(w, Weapon)
    wstore_opponent = _require_store(w, Opponent)

    # We’ll pair them 2-by-2 for fallback if needed
    for i in range(0, len(w.combatants), 2):
        eid1 = w.combatants[i]
        if i + 1 < len(w.combatants):
            eid2 = w.combatants[i+1]
        else:
            break

        # fallback for Weapon
        if wstore_weapon.get(eid1) is None:
            wstore_weapon.add(eid1, _build_maul())
        if wstore_weapon.get(eid2) is None:
            wstore_weapon.add(eid2, _build_maul())

        # fallback for Opponent
        if wstore_opponent.get(eid1) is None:
            wstore_opponent.add(eid1, Opponent(eid2))
        if wstore_opponent.get(eid2) is None:
            wstore_opponent.add(eid2, Opponent(eid1))

    return w


def test_surrender_or_death_deterministic():
    """Check that repeated runs with the same seed produce identical outcomes."""
    outcomes = [_simulate_bout(_build_world(123)) for _ in range(3)]
    assert all(o == outcomes[0] for o in outcomes), outcomes


def test_perf_100_entities(pytestconfig):
    """Stress test the morale/stamina logic with 100 fighters."""
    import pytest
    if pytestconfig.getoption("--fast"):
        pytest.skip("perf test skipped on --fast run")

    w = _build_world(rng_seed=99, n_pairs=50)
    t0_ns = time.perf_counter_ns()
    for _ in range(1_000):
        w.tick_once()
    mean_ns = (time.perf_counter_ns() - t0_ns) / 1_000
    assert mean_ns <= 4_000_000, f"{mean_ns/1e6:.2f} ms / tick"


# ---------------------------------------------------------------------------#
#                  6 - LIGHTWEIGHT DEMO / CLI DRIVER                         #
# ---------------------------------------------------------------------------#

def _demo():
    print("== DEMO: two fighters until surrender or death ==")
    from collections import defaultdict
    w = _build_world(rng_seed=7)
    stamina_hist: Dict[EntityId, List[float]] = defaultdict(list)
    morale_hist:  Dict[EntityId, List[int]]   = defaultdict(list)

    t0 = time.perf_counter()
    outcome, final_tick = _simulate_bout(w, 15_000)
    dt = time.perf_counter() - t0

    for eid in w.combatants:
        stamina_hist[eid].append(w.stamina[eid].curr_pts)
        morale_hist[eid].append(w.morale[eid].value)

    print(f"Result: {outcome} on tick {final_tick:,}")
    print(f"Elapsed: {dt*1e3:.2f} ms  (avg {dt/final_tick*1e9:.0f} ns / tick)")
    print("- Current values -")
    for eid in w.combatants:
        print(f"  E{eid}: stamina {w.stamina[eid].curr_pts:.1f}  "
              f"morale {w.morale[eid].value} ({w.morale[eid].state})")


if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        _demo()
    else:
        print("Run with --demo for a quick bout, or use pytest.")
