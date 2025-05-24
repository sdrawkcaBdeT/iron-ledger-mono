# arena_blueprints.py
from movement_collision import _require_store, Position2D, CollisionRadius
from attack import _build_maul, Weapon, Opponent, AttackSystem

DEFAULT_SEPARATION = 0.30  # m – ensures the weapon can overlap if swung
DEFAULT_RADIUS     = 0.30  # collision radius for both fighters

def spawn_fighters_pair(world,
                        sep: float = DEFAULT_SEPARATION,
                        r: float   = DEFAULT_RADIUS) -> None:
    """
    Create two opposed fighters, place them 'sep' metres apart on the X-axis,
    give each a generic zweihänder (maul in your code) and register them.
    """
    # 1. Create 2 fighter entity IDs
    a, b = world.entities.next_id(), world.entities.next_id()

    # 2. Ensure AttackSystem is registered (so swinging can happen)
    if AttackSystem not in {type(s) for s in world._systems}:
        world.add_system(AttackSystem())

    # 3. Positions & collision
    #    We place them left & right so the weapon arcs can overlap
    _require_store(world, Position2D).add(a, Position2D(-sep/2, 0.0))
    _require_store(world, Position2D).add(b, Position2D(+sep/2, 0.0))
    _require_store(world, CollisionRadius).add(a, CollisionRadius(r))
    _require_store(world, CollisionRadius).add(b, CollisionRadius(r))

    # 4. Attach a weapon and Opponent to each
    weapon = _build_maul()                    
    _require_store(world, Weapon).add(a, weapon)
    _require_store(world, Weapon).add(b, weapon)

    _require_store(world, Opponent).add(a, Opponent(b))
    _require_store(world, Opponent).add(b, Opponent(a))

    # 5. Record them in world.combatants
    #    So other modules (like fatigue_morale) know these exist
    world.combatants = getattr(world, "combatants", []) + [a, b]
