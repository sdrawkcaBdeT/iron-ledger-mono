"""
action_registry.py – central action catalogue & timing helpers
==============================================================
*Single* source-of-truth for movement / attack / defence specs.

Public surface (stable):
    ACTIONS          – dict[id, ActionSpec]
    CHAINS           – list[ChainMod]
    ENC_MULT         – {"armor": {...}, "weapon": {...}}
    effective_ticks  – stat-, encumbrance-, fatigue-aware duration calculator
    version_hash()   – SHA-256 of the loaded JSON (balancing fingerprint)

All other names are internal; keep __all__ in sync if you extend.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Set

# ---------------------------------------------------------------------------

__all__ = [
    "ACTIONS",
    "CHAINS",
    "ENC_MULT",
    "effective_ticks",
    "version_hash",
]

TICK_LEN = 0.05  # seconds – must match engine_tick

# ---------- schema -----------------------------------------------------------------


class Phase(str, Enum):
    MOVE = "MOVE"
    ATTACK = "ATTACK"
    DEFEND = "DEFEND"


@dataclass(slots=True)
class ActionSpec:
    id: str
    phase: Phase
    ticks: int
    dist_m: float
    stamina: int
    # attack / defence specifics (None for moves)
    wind: int | None = None
    hit: int | None = None
    reco: int | None = None
    react: int | None = None
    active: int | None = None
    reset: int | None = None


@dataclass(slots=True)
class ChainMod:
    trigger: str
    next_ids: Set[str]
    windup_delta: int
    predicate: Callable[[object, int], bool]  # (world, eid) -> bool


# ---------- load JSON --------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent
JSON_PATH = "actions.json"

with open(JSON_PATH, encoding="utf-8") as fh:
    RAW = json.load(fh)
_RAW_BYTES = json.dumps(RAW, sort_keys=True).encode()

# – exposed tables –
ENC_MULT: Dict[str, Dict[str, float]] = RAW["encumbrance_mult"]
ACTIONS: Dict[str, ActionSpec] = {}

# ---------- helper to fill ACTIONS --------------------------------------------------


def _load_group(group_name: str, phase: Phase) -> None:
    """
    Populate the global ACTIONS table from RAW[group_name].

    * If the JSON row already has a "ticks" field we trust it.
    * Otherwise we derive it from the phase-specific trio:
        • ATTACK ─ wind + hit + reco
        • DEFEND ─ react + active + reset
        • MOVE   ─ dist-only rows must always carry explicit "ticks"
    """
    for entry in RAW[group_name]:
        ticks = entry.get("ticks")
        if ticks is None:
            if phase is Phase.ATTACK:
                ticks = entry["wind"] + entry["hit"] + entry["reco"]
            elif phase is Phase.DEFEND:
                ticks = entry["react"] + entry["active"] + entry["reset"]
            else:  # MOVE
                raise KeyError(
                    f'"{entry["id"]}" in locomotion group lacks "ticks" field'
                )

        spec = ActionSpec(
            id=entry["id"],
            phase=phase,
            ticks=ticks,
            dist_m=entry.get("dist_m", 0.0),
            stamina=entry["stam"],
            wind=entry.get("wind"),
            hit=entry.get("hit"),
            reco=entry.get("reco"),
            react=entry.get("react"),
            active=entry.get("active"),
            reset=entry.get("reset"),
        )
        ACTIONS[spec.id] = spec


_load_group("locomotion", Phase.MOVE)
_load_group("attacks", Phase.ATTACK)
_load_group("defence", Phase.DEFEND)

# ---------- chain rules ------------------------------------------------------------


def _pred_always(world: object, eid: int) -> bool:  # default predicate
    return True


CHAINS: List[ChainMod] = []
for rule in RAW["chains"]:
    predicate = _pred_always
    if rule.get("predicate") == "within_flank_1m":

        # deferred import to avoid circular dep
        from math import hypot

        def _within_flank(world, eid):  # type: ignore
            target = world.get_target(eid)
            return hypot(*(world.pos[eid] - world.pos[target])) <= 1.0

        predicate = _within_flank

    CHAINS.append(
        ChainMod(
            trigger=rule["trigger"][0]
            if isinstance(rule["trigger"], list)
            else rule["trigger"],
            next_ids=set(rule["next"]),
            windup_delta=rule["delta"],
            predicate=predicate,
        )
    )

# ---------- effective_ticks() -------------------------------------------------------


def effective_ticks(
    action_id: str,
    *,
    armor_class: str,
    weapon_class: str,
    stamina_curr: int,
    stamina_exhaust: int,
    coord: int,
    percep: int,
    phase: Phase | None = None,
) -> int:
    """
    Return the final integer tick duration for `action_id` after encumbrance,
    stats, and exhaustion modifiers.
    """
    spec = ACTIONS[action_id]
    phase = phase or spec.phase
    t = spec.ticks
    t *= ENC_MULT["armor"][armor_class]
    t *= ENC_MULT["weapon"][weapon_class]
    t *= (1 - 0.01 * coord)  # coordination bonus (‐20 % max @ coord 20)
    if phase is Phase.DEFEND:
        t *= (1 - 0.007 * percep)  # perception shortens defence react
    if stamina_curr <= stamina_exhaust:
        t *= 1.15  # exhaustion penalty
    return max(1, round(t))


# ---------- tiny deterministic helper ----------------------------------------------

_RNG = random.Random(42)  # global seeded instance for tie-breaks


def _tie_break(choices: List[str]) -> str:
    """Return a stable random choice from `choices` using the global seed."""
    return _RNG.choice(sorted(choices))


# ---------- balancing fingerprint ---------------------------------------------------


def version_hash() -> str:
    """
    SHA-256 hash of the *sorted* actions.json payload.

    Regression harnesses store this string alongside baseline metrics so they
    know when a designer changed balance and a re-baseline is required.
    """
    return hashlib.sha256(_RAW_BYTES).hexdigest()
