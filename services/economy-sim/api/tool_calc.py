# economy_sim/sidecar/tool_calc.py
import random, secrets
from .loader import load_table
from .schemas import RoundConfigOut, GatherResultOut

materials   = load_table("materials_metal")       | load_table("materials_cloth") | load_table("materials_leather")
qualities   = load_table("craft_quality")
repair_tbl  = load_table("repair_state")
tools_tbl   = load_table("tools")
goods_tbl   = load_table("goods")                 # so recipes can cross-verify

def _roll(lo: float, hi: float) -> float:
    return lo + random.random() * (hi - lo)

def get_tool_row(tool_id: str) -> dict:          # helper
    return tools_tbl[tool_id]

def compute_round_config(agent_id: int, tool_id: str, quality_id: str) -> RoundConfigOut:
    tool = get_tool_row(tool_id)
    mat  = materials[tool["material"]]
    qual = qualities[quality_id]
    rep  = repair_tbl[tool.get("repair_state", "Used")]

    gather_mult   = (1 + _roll(*mat["harvestSpeedRange"])) \
                  * (1 + _roll(*qual["gatherSpeedRange"])) \
                  * rep["gatherSpeedMult"]
    move_mult     = (1 / mat["weightFactor"]) \
                  * (1 + _roll(*qual["moveSpeedRange"])) \
                  * rep["moveSpeedMult"]

    dura_mult     = _roll(*mat["durabilityModifierRange"]) \
                  * _roll(*qual["durabilityRange"])

    max_dura      = round(tool["baseDurability"] * dura_mult)
    cur_dura      = min(tool["baseDurability"], max_dura)

    return RoundConfigOut(
        agent_id            = agent_id,
        seed                = secrets.randbits(32),
        move_speed_mult     = move_mult,
        sprint_speed_mult   = 1.25,
        sprint_time_mult    = 0.90,
        gather_time_mult    = 1 / gather_mult,
        tool = {
            "durability":     cur_dura,
            "max_durability": max_dura,
            "repair_state":   tool.get("repair_state", "Used")
        }
    )

def apply_gather_use(cfg: RoundConfigOut, nodes_collected: int) -> GatherResultOut:
    """
    Decrement durability and compute the new repair-state.
    """
    # -------------------------------- durability math --------------------
    dur_left  = max(cfg.tool.durability - nodes_collected, 0)
    pct_left  = dur_left / cfg.tool.max_durability

    # look up first row whose floor ≤ pct_left
    new_state = next(
        state for state, row in repair_tbl.items()
        if pct_left >= row["durabilityFloor"]
    )


    result = GatherResultOut(
        haul={"resource_node": nodes_collected},
        durability_used=nodes_collected,
        repair_state=new_state,
    )

    # --------------------------- debugging stdout ------------------------
    print(
        f"Agent {cfg.agent_id}: +{nodes_collected} nodes, "
        f"dur left={dur_left}/{cfg.tool.max_durability} "
    )
    # --------------------------------------------------------------------
    return result

