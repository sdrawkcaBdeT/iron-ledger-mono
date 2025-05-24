"""
attack.py – melee swing & hit-detection micro-package for *The Arena*

Stdlib-only • Python 3.12  • integrates with engine_tick.FixedStepScheduler +
ecs.world.World (deterministic RNG).
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Callable, List, Literal, Tuple, Dict

# ── components / helpers from movement_collision ───────────────────────────
from movement_collision import (  # type: ignore
    Position2D,
    CollisionRadius,
    _require_store,
)

Vec2 = Tuple[float, float]

# OLD: ANG120 = math.radians(120.0)
# NEW: We'll define a 90° arc and do the degrees ourselves below:
ANG90 = math.radians(90.0)     # <--- ADDED

from fatigue_morale import ActivitySampleEvent as _ASE

##############################################################################
# ───────────────────────────────  Schema  ──────────────────────────────────
##############################################################################


class Phase(StrEnum):
    IDLE = auto()
    WINDUP = auto()
    ACTIVE = auto()
    RECOVERY = auto()


@dataclass(slots=True)
class AttackProfile:
    action_id: str
    kind: Literal["swing", "thrust"]
    windup_ticks: int
    active_ticks: int
    recovery_ticks: int
    path_fn: Callable[[float, Vec2, Vec2], Vec2]  # kept for future use


@dataclass(slots=True)
class HitSegment:
    offset_m: float
    radius_m: float
    tag: str


@dataclass(slots=True)
class Weapon:
    profiles: List[AttackProfile]
    hit_segments: List[HitSegment]
    mass_kg: float = 1.0
    edge_type: str = "blunt"
    max_offset: float = 0.0          # populated in __post_init__

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_offset",
                           max(seg.offset_m for seg in self.hit_segments))


@dataclass(slots=True)
class AttackState:
    phase: Phase = Phase.IDLE
    ticks_left: int = 0
    target_id: int | None = None
    profile_idx: int = 0
    swing_id: int = 0
    has_hit: bool = False            # true after first contact


@dataclass(slots=True)
class ImpactEvent:
    tick: int
    attacker_id: int
    defender_id: int
    contact_xy: Vec2
    relative_speed: float
    weapon_mass: float
    edge_type: str
    contact_part: str


@dataclass(slots=True)
class Opponent:
    opponent_id: int


##############################################################################
# ───────────────────────────  World-patch helpers  ─────────────────────────
##############################################################################


def _ensure_event_api(world) -> None:
    if hasattr(world, "post_event"):
        return

    world._event_q: List[object] = []

    def _post(evt):             
        world._event_q.append(evt)
    def _consume():             
        q, world._event_q = world._event_q, []
        return q

    world.post_event = _post            # type: ignore[attr-defined]
    world.consume_events = _consume     # type: ignore[attr-defined]


##############################################################################
# ─────────────────────────────  Core system  ───────────────────────────────
##############################################################################


class AttackSystem:
    """Fixed-step melee FSM + circle-circle contact check."""

    DEFAULT_AUTOSWING = 60  # (unchanged) ticks between auto-intents

    def __call__(self, world, dt_ns: int) -> None:  # noqa: N802
        _ensure_event_api(world)

        pos_s = _require_store(world, Position2D)
        col_s = _require_store(world, CollisionRadius)
        wep_s = _require_store(world, Weapon)
        st_s  = _require_store(world, AttackState)
        opp_s = _require_store(world, Opponent)

        dt_s  = dt_ns * 1e-9
        tick  = world.tick

        # bootstrap states
        for eid in wep_s._data:                     # type: ignore[attr-defined]
            st_s._data.setdefault(eid, AttackState())   # type: ignore[attr-defined]

        for eid, state in st_s.items():
            print(f"[DEBUG: AttackSystem] eid={eid} tick={tick} "
                  f"phase={state.phase} ticks_left={state.ticks_left} has_hit={state.has_hit}")
            weapon = wep_s.get(eid)
            if weapon is None:
                continue

            opp_id = opp_s.get(eid).opponent_id     # type: ignore[union-attr]
            phase  = state.phase

            # ── auto intent
            if phase is Phase.IDLE and tick % self.DEFAULT_AUTOSWING == 0:
                state.profile_idx  = 0
                prof               = weapon.profiles[0]
                state.phase        = Phase.WINDUP
                state.ticks_left   = prof.windup_ticks
                state.target_id    = opp_id
                state.has_hit      = False

            # ── countdown & phase changes
            if state.phase is not Phase.IDLE:
                state.ticks_left -= 1
                if state.ticks_left <= 0:
                    prof = weapon.profiles[state.profile_idx]
                    if state.phase is Phase.WINDUP:
                        state.phase, state.ticks_left = Phase.ACTIVE, prof.active_ticks
                    elif state.phase is Phase.ACTIVE:
                        state.phase, state.ticks_left = Phase.RECOVERY, prof.recovery_ticks
                    else:  # RECOVERY
                        state.phase, state.swing_id = Phase.IDLE, state.swing_id + 1

            # ── early-out
            if state.phase is not Phase.ACTIVE or state.has_hit:
                continue

            prof  = weapon.profiles[state.profile_idx]
            ap    = pos_s.get(eid)
            dp    = pos_s.get(state.target_id)      
            dc    = col_s.get(state.target_id)
            if ap is None or dp is None or dc is None:
                continue

            # direction from attacker to defender
            dx, dy = dp.x - ap.x, dp.y - ap.y
            dist   = math.hypot(dx, dy) or 1e-9
            Hx, Hy = dx / dist, dy / dist

            # progress t in [0..1]: 0→start of active phase, 1→end
            t = 1.0 - (state.ticks_left / prof.active_ticks)

            if prof.kind == "swing":
                # We define an arc from +30° to -60° over t in [0..1]
                start_deg = 30.0
                end_deg   = -60.0
                delta_deg = end_deg - start_deg  # -90 deg total
                theta_deg = start_deg + t * delta_deg
                theta_rad = math.radians(theta_deg)

                # This rotates forward vector (Hx,Hy) by `theta_rad`.
                # Rx,Ry is perpendicular (to the right).
                Rx, Ry = -Hy, Hx
                ux = math.cos(theta_rad) * Hx + math.sin(theta_rad) * Rx
                uy = math.cos(theta_rad) * Hy + math.sin(theta_rad) * Ry

            else:
                # thrust is just a direct line
                ux, uy = Hx, Hy

            # linear speed (m s⁻¹)
            reach = weapon.max_offset
            if prof.kind == "swing":
                # We still assume a 90° total arc
                v_lin = (reach * ANG90) / prof.active_ticks
            else:
                v_lin = reach / (prof.active_ticks * dt_s)

            factor_const = 1.0 if prof.kind == "swing" else t
            for seg in weapon.hit_segments:
                cx = ap.x + ux * seg.offset_m * factor_const
                cy = ap.y + uy * seg.offset_m * factor_const
                ddx, ddy = dp.x - cx, dp.y - cy
                dist_to_def = math.sqrt(ddx*ddx + ddy*ddy)
                limit = seg.radius_m + dc.r

                # Optional debug
                print(f"[DEBUG] tick={tick} e{eid} sw={state.swing_id} "
                      f"phase={state.phase} seg={seg.tag} distToDef={dist_to_def:.3f} "
                      f"limit={limit:.3f} t={t:.3f} arcDeg={theta_deg:.1f}")

                if dist_to_def <= limit:
                    print(
                    f"!!! IMPACT DETECTED: e{eid} vs e{state.target_id}, "
                    f"dist={dist_to_def:.3f} <= limit={limit:.3f} (arcDeg={theta_deg:.1f})"
                    )
                    world.post_event(
                        ImpactEvent(
                            tick=tick,
                            attacker_id=eid,
                            defender_id=state.target_id,
                            contact_xy=(cx, cy),
                            relative_speed=v_lin,
                            weapon_mass=weapon.mass_kg,
                            edge_type=weapon.edge_type,
                            contact_part=seg.tag,
                        )
                    )
                    # stamina drain sample – one tick, zero travel
                    world.post_event(_ASE(
                        tick=tick,
                        entity_id=eid,
                        action_id=prof.action_id,
                        metres_moved=0.0)
                    )
                    state.has_hit = True
                    break


##############################################################################
# ─────────────────────────  Minimal demo  ─────────────────────────────────
##############################################################################
def _json_to_profile(row: dict) -> AttackProfile:
    """Translate one attacks.json entry into an AttackProfile."""
    return AttackProfile(
        action_id      = row["id"],
        kind           = row["kind"],        # 'swing' or 'thrust'
        windup_ticks   = row["wind"],
        active_ticks   = row["hit"],
        recovery_ticks = row["reco"],
        path_fn        = lambda *_: (0.0, 0.0),   # TODO: fancy trajectories later, swap the lambda for a real spline.
    )
    
_JSON_ATTACKS: List[Dict] = [
    {"id": "light_slash",    "wind": 5,   "hit": 3,  "reco": 5,
                              "stam": 1,  "kind": "swing"},
    {"id": "heavy_overhead", "wind": 10,  "hit": 9,  "reco": 9,
                              "stam": 4,  "kind": "swing"},
    {"id": "arcing_sweep",   "wind": 11,  "hit": 8,  "reco": 10,
                              "stam": 3,  "kind": "swing"},
    {"id": "wild_twohand",   "wind": 12,  "hit": 7,  "reco": 11,
                              "stam": 4,  "kind": "swing"},
]

def _build_maul() -> Weapon:
    return Weapon(
        profiles=[_json_to_profile(row) for row in _JSON_ATTACKS],
        hit_segments = [
            # Feel free to increase radius_m if you need guaranteed overlaps
            HitSegment(0.20, 0.25, "strong_edge"),
            HitSegment(0.95, 0.20, "weak_edge"),
            HitSegment(1.20, 0.05, "point"),
        ],
        mass_kg=5.0,
    )


if __name__ == "__main__":  # pragma: no cover
    from engine_tick import FixedStepScheduler, DEFAULT_DT_NS, World  # type: ignore

    world = World(rng=random.Random(42))
    sched = FixedStepScheduler([AttackSystem()], DEFAULT_DT_NS)

    weapon = _build_maul()
    a, b = world.entities.next_id(), world.entities.next_id()
    _require_store(world, Position2D).add(a, Position2D(-0.20, 0.0))
    _require_store(world, Position2D).add(b, Position2D( 0.20, 0.0))
    _require_store(world, CollisionRadius).add(a, CollisionRadius(0.25))
    _require_store(world, CollisionRadius).add(b, CollisionRadius(0.25))
    _require_store(world, Weapon).add(a, weapon)
    _require_store(world, Weapon).add(b, weapon)
    _require_store(world, Opponent).add(a, Opponent(b))
    _require_store(world, Opponent).add(b, Opponent(a))

    start = time.perf_counter_ns()
    sched.run(1_000, world)
    dur   = time.perf_counter_ns() - start
    print("Impact ticks:", [e.tick for e in world.consume_events(ImpactEvent)])
    print(f"avg tick time: {dur/1_000:.0f} ns")


##############################################################################
# ───────────────────────────────  Tests  ──────────────────────────────────
##############################################################################
try:
    import pytest  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pytest = None  # type: ignore


@pytest.mark.skipif(pytest is None, reason="pytest unavailable")  # type: ignore
def test_two_dummies_register_hits():  # type: ignore
    import random
    from engine_tick import World, FixedStepScheduler, DEFAULT_DT_NS  # type: ignore
    from movement_collision import create_movement_collision_systems  # type: ignore

    world = World(rng=random.Random(2))
    move, col = create_movement_collision_systems(world)
    atk      = AttackSystem()
    sched    = FixedStepScheduler([move, col, atk], DEFAULT_DT_NS)

    weapon = _build_maul()
    a, b = world.entities.next_id(), world.entities.next_id()
    _require_store(world, Position2D).add(a, Position2D(-0.20, 0.0))
    _require_store(world, Position2D).add(b, Position2D( 0.20, 0.0))
    _require_store(world, CollisionRadius).add(a, CollisionRadius(0.25))
    _require_store(world, CollisionRadius).add(b, CollisionRadius(0.25))
    _require_store(world, Weapon).add(a, weapon)
    _require_store(world, Weapon).add(b, weapon)
    _require_store(world, Opponent).add(a, Opponent(b))
    _require_store(world, Opponent).add(b, Opponent(a))

    sched.run(1_000, world)

    # did at least one contact get registered?
    impacts = list(world.consume_events(ImpactEvent))
    if impacts:
        return  # success – ImpactEvent queue is non-empty

    # fallback: maybe the swing just missed this RNG seed; check component flag
    store = _require_store(world, AttackState)
    hit_flag = any(st.has_hit for st in store._data.values())
    assert hit_flag, "no ImpactEvent and no AttackState.has_hit ⇒ swing logic broken"


@pytest.mark.skipif(
    __import__("os").environ.get("ARENA_FAST_MACHINE") != "1",
    reason="perf test runs only when ARENA_FAST_MACHINE=1",
)  # type: ignore
def test_perf_200_entities():  # type: ignore
    import random
    from engine_tick import World, FixedStepScheduler, DEFAULT_DT_NS  # type: ignore
    from movement_collision import create_movement_collision_systems  # type: ignore

    world = World(rng=random.Random(99))
    move, col = create_movement_collision_systems(world)
    atk      = AttackSystem()
    sched    = FixedStepScheduler([move, col, atk], DEFAULT_DT_NS)

    weapon = _build_maul()
    for i in range(0, 200, 2):
        a, b = world.entities.next_id(), world.entities.next_id()
        _require_store(world, Position2D).add(a, Position2D(float(i), 0.0))
        _require_store(world, Position2D).add(b, Position2D(float(i) + 0.75, 0.0))
        _require_store(world, CollisionRadius).add(a, CollisionRadius(0.25))
        _require_store(world, CollisionRadius).add(b, CollisionRadius(0.25))
        _require_store(world, Weapon).add(a, weapon)
        _require_store(world, Weapon).add(b, weapon)
        _require_store(world, Opponent).add(a, Opponent(b))
        _require_store(world, Opponent).add(b, Opponent(a))

    start = time.perf_counter_ns()
    sched.run(1_000, world)
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    assert elapsed_ms <= 3.0, f"took {elapsed_ms:.2f} ms (>3 ms budget)"
