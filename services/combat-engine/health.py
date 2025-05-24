# ================================================================
#  health.py – Tissue-stack damage, bleeding, death for *The Arena*
# ================================================================
"""
Production-ready, stdlib-only Python 3.12 implementation of the
“Damage-and-Bleed v0.3” spec (April 2025), with micro-perf and
physiology tweaks (2025-04-29 review).

Exports
-------
• Dataclasses:  Limb, Organ, Vitals, BleedSource, DeathEvent
• Helpers:     REGIONS, build_default_anatomy
• Systems:     DamageSystem, BleedSystem
• register_health_systems(world)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import (
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)

# ---------------------------------------------------------------------------
# 1.  Component dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Limb:
    """Mutable hit-point container for a body region (skin→muscle→bone)."""

    name: str
    max_skin: int
    max_muscle: int
    max_bone: int
    curr_skin: int
    curr_muscle: int
    curr_bone: int

    # quick helpers ----------------------------------------------------------

    def bone_fractured(self) -> bool:
        """True if bone HP is depleted."""
        return self.curr_bone <= 0


@dataclass(slots=True)
class Organ:
    """Vital organ embedded within a region."""

    name: str
    max_hp: int
    curr_hp: int
    base_cat_rate: float  # ml s⁻¹ catastrophic bleed minimum


@dataclass(slots=True)
class Vitals:
    """Circulatory state in millilitres."""

    blood_ml: float = 5_000.0
    blood_loss_rate_ml_s: float = 0.0
    is_alive: bool = True


@dataclass(slots=True)
class BleedSource:
    """A single wound emitting blood each tick."""

    limb_idx: int
    rate_ml_s: float
    internal: bool = False


@dataclass(slots=True)
class DeathEvent:
    """Broadcast when an entity dies."""

    tick: int
    entity_id: int
    cause: Literal["organ_failure", "exsanguination"]


# ---------------------------------------------------------------------------
# 2.  Anatomy constants & builders
# ---------------------------------------------------------------------------

REGIONS: List[str] = [
    "head",
    "neck",
    "thorax",
    "abdomen",
    "left_arm",
    "right_arm",
    "left_leg",
    "right_leg",
]

VITAL_ORGANS: Dict[str, List[str]] = {
    "head": ["brain"],
    "neck": ["carotid"],
    "thorax": ["heart", "left_lung", "right_lung"],
    "abdomen": ["liver", "spleen", "left_kidney", "right_kidney"],
}

BLEED_RATE_CATASTRO: Dict[str, float] = {
    "brain": 0.0,
    "carotid": 150.0,
    "heart": 120.0,
    "left_lung": 20.0,
    "right_lung": 20.0,
    "liver": 50.0,
    "spleen": 60.0,
    "left_kidney": 30.0,
    "right_kidney": 30.0,
}

DEFAULT_LIMB_HP: Dict[str, Tuple[int, int, int]] = {
    "head": (15, 25, 20),
    "neck": (10, 10, 0),
    "thorax": (18, 30, 18),
    "abdomen": (18, 28, 15),
    "left_arm": (12, 22, 12),
    "right_arm": (12, 22, 12),
    "left_leg": (14, 24, 14),
    "right_leg": (14, 24, 14),
}

DEFAULT_ORGAN_HP: Dict[str, int] = {
    "brain": 15,
    "carotid": 10,
    "heart": 15,
    "left_lung": 12,
    "right_lung": 12,
    "liver": 15,
    "spleen": 12,
    "left_kidney": 10,
    "right_kidney": 10,
}

BONE_BREAK_THRESHOLD_J: Dict[str, int] = {
    "head": 80,
    "neck": 60,
    "thorax": 120,
    "abdomen": 100,
    "left_arm": 60,
    "right_arm": 60,
    "left_leg": 60,
    "right_leg": 60,
}
BONE_HARDNESS_FACTOR: float = 15.0  # J → 1 bone HP

#   layer thicknesses used for depth walk
LAYERS: Tuple[Tuple[str, float], ...] = (
    ("skin", 0.2),
    ("muscle", 2.0),
    ("bone", 1.3),
    ("organ", 1.0),
)
TOTAL_STACK_CM: float = sum(t for _, t in LAYERS)

#   energy→bruise conversion for blunt < threshold
SOFT_ENERGY_PER_HP_SKIN = 10.0
SOFT_ENERGY_PER_HP_MUSCLE = 7.0

K1_EXTERNAL = 5.0   # ml s⁻¹ cm⁻¹
K2_INTERNAL = 30.0  # ml s⁻¹ (cm or hp proportion)

SHEAR_COEFF: Dict[str, float] = {
    "blunt": 0.0,
    "slash": 0.6,
    "pierce": 1.0,
}

SPEED_BINS = (2.0, 5.0, 8.0)  # m s⁻¹
_PEN_TABLE: Dict[str, Tuple[float, float, float, float]] = {
    "blunt": (0.0, 0.1, 0.25, 0.40),
    "slash": (0.05, 0.25, 0.60, 0.90),
    "pierce": (0.10, 0.40, 0.80, 1.00),
}

# ---------------------------------------------------------------------------
# 3.  ImpactEvent protocol – runtime-checkable
# ---------------------------------------------------------------------------


@runtime_checkable
class ImpactEvent(Protocol):  # pragma: no cover – typing only
    tick: int
    attacker_id: int
    defender_id: int
    relative_speed: float
    weapon_mass: float
    edge_type: str
    limb_idx: int


# ---------------------------------------------------------------------------
# 4.  Anatomy builder
# ---------------------------------------------------------------------------


def build_default_anatomy() -> Tuple[List[Limb], List[Optional[List[Organ]]]]:
    """Return default (limbs, organs) lists aligned to ``REGIONS`` order."""
    limbs: List[Limb] = []
    organs: List[Optional[List[Organ]]] = []
    for r in REGIONS:
        s_hp, m_hp, b_hp = DEFAULT_LIMB_HP[r]
        limbs.append(Limb(r, s_hp, m_hp, b_hp, s_hp, m_hp, b_hp))
        if r in VITAL_ORGANS:
            organs.append(
                [
                    Organ(o, DEFAULT_ORGAN_HP[o], DEFAULT_ORGAN_HP[o], BLEED_RATE_CATASTRO[o])
                    for o in VITAL_ORGANS[r]
                ]
            )
        else:
            organs.append(None)
    return limbs, organs


# ---------------------------------------------------------------------------
# 5.  Utility helpers
# ---------------------------------------------------------------------------


def penetration_fraction(edge: str, speed: float) -> float:
    """Return penetration fraction *p* ∈ [0,1] given edge and speed."""
    bins = _PEN_TABLE[edge]
    if speed < SPEED_BINS[0]:
        return bins[0]
    if speed < SPEED_BINS[1]:
        return bins[1]
    if speed < SPEED_BINS[2]:
        return bins[2]
    return bins[3]


def bone_break_threshold(region: str) -> int:
    return BONE_BREAK_THRESHOLD_J[region]


# ---------------------------------------------------------------------------
# 6.  Systems
# ---------------------------------------------------------------------------


def DamageSystem(world, dt_ns: int) -> None:  # noqa: N802 – engine convention
    """Consume ImpactEvents, mutate anatomy, spawn BleedSources & DeathEvents."""
    evq: List[ImpactEvent] = world.consume_events(ImpactEvent)  # type: ignore[arg-type]
    bleed_dict: Dict[int, List[BleedSource]] = world.__dict__.setdefault(
        "_bleed_sources", {}
    )

    rng = world.rng  # cache hot-path attribute
    sources_for = bleed_dict.setdefault

    for hit in evq:
        limbs: List[Limb] = world.limbs[hit.defender_id]  # type: ignore[attr-defined]
        organs = world.organs[hit.defender_id]            # type: ignore[attr-defined]
        limb = limbs[hit.limb_idx]

        # -------  energy split  ----------------------------
        ke_total = 0.5 * hit.weapon_mass * hit.relative_speed**2
        shear_coeff = SHEAR_COEFF.get(hit.edge_type, 0.0)
        ke_shear = ke_total * shear_coeff
        ke_crush = ke_total * (1.0 - shear_coeff)

        # ---------------------------------------------------
        #  Crush / blunt pipeline
        # ---------------------------------------------------
        threshold = bone_break_threshold(limb.name)
        if ke_crush < threshold:
            # soft-tissue bruise
            limb.curr_skin = max(
                0,
                limb.curr_skin
                - max(1, int(ke_crush * 0.33 / SOFT_ENERGY_PER_HP_SKIN)),
            )
            limb.curr_muscle = max(
                0,
                limb.curr_muscle
                - max(1, int(ke_crush * 0.67 / SOFT_ENERGY_PER_HP_MUSCLE)),
            )
        else:
            excess = ke_crush - threshold
            bone_dmg_hp = max(1, int(round(excess / BONE_HARDNESS_FACTOR)))
            limb.curr_bone = max(0, limb.curr_bone - bone_dmg_hp)

            if limb.bone_fractured() and organs and organs[hit.limb_idx]:
                for organ in organs[hit.limb_idx] or []:  # type: ignore[index]
                    if rng.random() < 0.25:
                        organ.curr_hp = max(0, organ.curr_hp - 1)
                        rate = max(K2_INTERNAL, organ.base_cat_rate)
                        sources_for(hit.defender_id, []).append(
                            BleedSource(hit.limb_idx, rate, internal=True)
                        )
                        if organ.curr_hp <= 0:
                            world.post_event(
                                DeathEvent(world.tick, hit.defender_id, "organ_failure")
                            )

        # ---------------------------------------------------
        #  Shear / penetration pipeline
        # ---------------------------------------------------
        p = penetration_fraction(hit.edge_type, hit.relative_speed)
        remaining = p * TOTAL_STACK_CM

        for layer_name, thickness in LAYERS:
            if remaining <= 0:
                break

            if layer_name == "organ" and organs and organs[hit.limb_idx]:
                organ: Organ = rng.choice(organs[hit.limb_idx])  # type: ignore[index]
                proportion = min(1.0, remaining / thickness)
                dmg_hp = max(1, int(proportion * organ.max_hp))
                organ.curr_hp = max(0, organ.curr_hp - dmg_hp)
                rate = max(
                    organ.base_cat_rate,
                    K2_INTERNAL * (dmg_hp / organ.max_hp),
                )
                sources_for(hit.defender_id, []).append(
                    BleedSource(hit.limb_idx, rate, internal=True)
                )
                if organ.curr_hp <= 0:
                    world.post_event(
                        DeathEvent(world.tick, hit.defender_id, "organ_failure")
                    )
                break

            damage_pool = min(remaining, thickness)
            proportion = damage_pool / thickness

            if layer_name == "skin":
                prev = limb.curr_skin
                dmg_hp = max(1, math.ceil(proportion * limb.max_skin))
                limb.curr_skin = max(0, limb.curr_skin - dmg_hp)
                if prev > 0 and limb.curr_skin == 0:
                    sources_for(hit.defender_id, []).append(
                        BleedSource(
                            hit.limb_idx,
                            K1_EXTERNAL * proportion,  # rate ~ depth ratio
                            internal=False,
                        )
                    )

            elif layer_name == "muscle":
                prev = limb.curr_muscle
                dmg_hp = max(1, math.ceil(proportion * limb.max_muscle))
                limb.curr_muscle = max(0, limb.curr_muscle - dmg_hp)
                if prev > 0 and limb.curr_muscle == 0:
                    sources_for(hit.defender_id, []).append(
                        BleedSource(
                            hit.limb_idx,
                            K1_EXTERNAL * proportion,
                            internal=False,
                        )
                    )

            elif layer_name == "bone":
                dmg_hp = max(1, math.ceil(proportion * limb.max_bone))
                limb.curr_bone = max(0, limb.curr_bone - dmg_hp)

            remaining -= damage_pool


def BleedSystem(world, dt_ns: int) -> None:  # noqa: N802
    """Drain blood based on BleedSources; issue exsanguination DeathEvent."""
    dt_s = dt_ns / 1_000_000_000.0
    bleed_dict: Dict[int, List[BleedSource]] = world.__dict__.setdefault(
        "_bleed_sources", {}
    )

    for ent_id, vit in list(world.vitals.items()):  # type: ignore[attr-defined]
        if not vit.is_alive:
            continue
        total_rate = sum(src.rate_ml_s for src in bleed_dict.get(ent_id, []))
        vit.blood_loss_rate_ml_s = total_rate
        vit.blood_ml -= total_rate * dt_s
        if vit.blood_ml <= 0:
            vit.is_alive = False
            world.post_event(DeathEvent(world.tick, ent_id, "exsanguination"))


# ---------------------------------------------------------------------------
# 7.  Registration helper
# ---------------------------------------------------------------------------


def register_health_systems(world) -> None:
    """Attach DamageSystem & BleedSystem to an ECS world."""
    world.add_system(DamageSystem)
    world.add_system(BleedSystem)


# ---------------------------------------------------------------------------
# 8.  Import-time guard
# ---------------------------------------------------------------------------

if __name__.endswith(".__main__"):  # pragma: no cover
    print("health.py is a library; run demo_damage.py for the showcase.")
