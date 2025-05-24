# economy_sim/sidecar/schemas.py
from pydantic import BaseModel, Field
from typing import Dict, List, Tuple

Vec2 = Tuple[float, float]

class ToolBlock(BaseModel):
    durability: int
    max_durability: int
    repair_state: str

class RoundConfigOut(BaseModel):
    agent_id: int
    zone_id: int = 0
    seed: int
    move_speed_mult: float
    sprint_speed_mult: float
    sprint_time_mult: float
    gather_time_mult: float
    tool: ToolBlock

class GatherRunIn(BaseModel):
    agent_id: int
    zone_id: int
    path: List[Vec2]
    nodes_collected: int
    stamina_boost: float | None = None

class GatherResultOut(BaseModel):
    haul: Dict[str, int]
    durability_used: int
    repair_state: str
