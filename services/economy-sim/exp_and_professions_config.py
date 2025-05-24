from collections import defaultdict
from data_structures import Profession # Assuming Profession enum from your existing data_structures.py

# --- EXP Curve ---
# Scaled Option 3 (Base 800 for first step, effective multiplier ~2.16)
# XP needed for each specific benchmark step i (where i from 1 to 10)
SCALED_EXP_CURVE_BENCHMARK_CHUNKS = [
    800, 1726, 3724, 8036, 17338, 37412, 80720, 174168, 376024, 811360
]

# Total EXP accumulated to reach the END of benchmark step i
TOTAL_EXP_TO_REACH_BENCHMARK = []
current_total_exp_val = 0
for chunk_val in SCALED_EXP_CURVE_BENCHMARK_CHUNKS:
    current_total_exp_val += chunk_val
    TOTAL_EXP_TO_REACH_BENCHMARK.append(current_total_exp_val)

def get_total_exp_for_benchmark_level(benchmark_level: int) -> int:
    if not 1 <= benchmark_level <= 10: return 0
    return TOTAL_EXP_TO_REACH_BENCHMARK[benchmark_level - 1]

def get_exp_chunk_for_benchmark_level(benchmark_level: int) -> int:
    if not 1 <= benchmark_level <= 10: return 0
    return SCALED_EXP_CURVE_BENCHMARK_CHUNKS[benchmark_level - 1]

BASE_EXP_REWARD_GATHERING_NODE = 16 # Example base EXP for one "node" collected from minigame

# --- Perk Definitions ---
LUMBERJACK_PERKS = {
    # Benchmark Level: {Perk Details}
    1: {"name": "Basic Wood Identification", "description": "Can gather oak_log.", "type": "unlock_resource", "data": {"resource_id": "oak_log"}},
    2: {"name": "Efficient Felling Technique", "description": "+10% wood yield.", "type": "modifier", "target_metric": "yield_multiplier", "value": 1.10},
    3: {"name": "Durable Axe Handling", "description": "Axe durability used per log reduced by 15%.", "type": "modifier", "target_metric": "durability_loss_multiplier", "value": 0.85},
    4: {"name": "Rare Timber Recognition", "description": "Can gather mahogany_log.", "type": "unlock_resource", "data": {"resource_id": "mahogany_log"}},
    5: {"name": "Forester's Bounty", "description": "5% chance per log unit to find an additional 'ancient_sap'.", "type": "rng_bonus_item", "item_id": "ancient_sap", "chance_per_unit": 0.05, "quantity_per_proc": 1},
    6: {"name": "Improved Yield I", "description": "Further +5% wood yield.", "type": "modifier", "target_metric": "yield_multiplier", "value": 1.05},
    7: {"name": "Masterful Axe Care", "description": "Axe durability used per log further reduced by 10%.", "type": "modifier", "target_metric": "durability_loss_multiplier", "value": 0.90},
    8: {"name": "Advanced Timber Scouting", "description": "Increased chance for higher quality variants.", "type": "quality_modifier", "target_metric": "wood_quality_chance", "value": 0.10},
    9: {"name": "Expert Forester", "description": "Can now also gather 'ironwood_log'.", "type": "unlock_resource", "data": {"resource_id": "ironwood_log"}},
    10: {"name": "Legendary Lumberjack", "description": "+25% to all wood yields & 10% chance for double 'Forester's Bounty' procs.", "type": "compound_bonus", "data": {"yield_multiplier": 1.25, "bounty_double_chance": 0.10 }}
}

# Example for MINER (need to design these perks)
MINER_PERKS = {
    1: {"name": "Basic Ore Finding", "description": "Can identify and mine copper_ore.", "type": "unlock_resource", "data": {"resource_id": "ore_copper"}},
    2: {"name": "Efficient Striking", "description": "+10% ore yield.", "type": "modifier", "target_metric": "yield_multiplier", "value": 1.10},
    # ... up to 10 benchmarks ...
}

PROFESSION_PERKS_DATA = {
    Profession.LUMBERJACK: LUMBERJACK_PERKS,
    Profession.MINER: MINER_PERKS, # Add other professions as you define their perks
    # Profession.FARMER: FARMER_PERKS,
    # ...
}

# --- EXP Rewards for Gathering specific resources (Optional, if not just yield * base) ---
# EXP_REWARDS_FOR_RESOURCE_TYPE = {
#     "wood": 16, "oak_log": 20, "mahogany_log": 30, "ironwood_log": 40,
#     "ore_iron": 18, "ore_copper": 16, "ore_tin": 15, "ore_coal": 12,
#     "ancient_sap": 50, # If finding it gives direct EXP
# }