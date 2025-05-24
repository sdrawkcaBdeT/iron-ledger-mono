import logging
import random
from data_structures import (
    Profession, SkillLevel, SILVER_PER_GOLD
)
from resource_loader import CATALOG

INDUSTRY_CONFIG = {
    Profession.BLACKSMITH: {
        "recipes": [
            {"inputs": {"ore_iron": 1, "ore_coal": 1}, "output_item": "weapon_basic", "out_per_batch": 1},
            {"inputs": {"ore_iron": 1, "ore_coal": 1}, "output_item": "armor_basic",  "out_per_batch": 1}
        ],
        "overhead_per_day": 0.0,
        "min_margin": 0.1,
        "min_stocks": {
            "ore_iron": 10,
            "ore_coal": 10
        }
    },
    Profession.COOK: {
        "recipes": [
            {"inputs": {"beef": 1},      "output_item": "meal_meat",      "out_per_batch": 5*2},
            {"inputs": {"sardine": 1},   "output_item": "meal_sardine",   "out_per_batch": 1*2},
            {"inputs": {"herring": 1},   "output_item": "meal_herring",   "out_per_batch": 1*2},
            {"inputs": {"trout": 1},     "output_item": "meal_trout",     "out_per_batch": 3*2},
            {"inputs": {"salmon": 1},    "output_item": "meal_salmon",    "out_per_batch": 3*2},
            {"inputs": {"swordfish": 1}, "output_item": "meal_swordfish", "out_per_batch": 5*2},
            {"inputs": {"shark": 1},     "output_item": "meal_shark",     "out_per_batch": 10*2},
        ],
        "overhead_per_day": 0.0,
        "min_margin": 1.2,
        "min_stocks": {
            "beef": 30, "sardine": 70, "herring": 70, "trout": 35,
            "salmon": 35, "swordfish": 8, "shark": 5
        }
    },
    Profession.CARPENTER: {
    "recipes": [
        {"inputs": {"wood": 5}, "output_item": "furniture", "out_per_batch": 1},
        {"inputs": {"wood": 5}, "output_item": "wagon", "out_per_batch": 1},
        {"inputs": {"wood": 10}, "output_item": "horse_cart", "out_per_batch": 1}
    ],
    "overhead_per_day": 0.0,
    "min_margin": 0.1,
    "min_stocks": {
        "wood": 50
    }
    },
    Profession.BAKER: {
        "recipes": [
            {"inputs": {"grain": 3}, "output_item": "bread", "out_per_batch": 4}
        ],
        "overhead_per_day": 0.0,
        "min_margin": 4.0,
        "min_stocks": {
            "grain": 50
        }
    },
    Profession.BREWER: {
        "recipes": [
            {"inputs": {"grain": 1}, "output_item": "beer", "out_per_batch": 5*10}
        ],
        "overhead_per_day": 0.0,
        "min_margin": 0.1,
        "min_stocks": {
            "grain": 50
        }
    },
    Profession.TAILOR: {
        "recipes": [
            {"inputs": {"wool": 1}, "output_item": "clothing", "out_per_batch": 2}
        ],
        "overhead_per_day": 0.0,
        "min_margin": 0.1,
        "min_stocks": {
            "wool": 20
        }
    }
}

def produce_raw_resources(person, guild, forest_capacity):
    """
    Mining, Logging, Fishing => produce raw items into guild.warehouse
    """
    if person.profession == Profession.MINER:
        qty = 6 if person.skill_level == SkillLevel.LOW else 8
        ore_type = random.choices(
            ["ore_iron","ore_copper","ore_tin","ore_coal","ore_silver","ore_gold"],
            weights=[0.25,0.15,0.15,0.15,0.15,0.15], k=1
        )[0]
        guild.warehouse[ore_type] += qty
        logging.debug(f"{person.name} (ID={person.person_id}) => produced {qty} {ore_type}. Now guild has {guild.warehouse[ore_type]}")
    elif person.profession == Profession.LUMBERJACK:
        qty = 6 if person.skill_level == SkillLevel.LOW else 8
        cut = min(qty, forest_capacity)
        if cut > 0:
            guild.warehouse["wood"] += cut
            forest_capacity -= cut
            logging.debug(f"{person.name} cut {cut} wood => {guild.guild_name}. Now guild has {guild.warehouse['wood']}")
    elif person.profession == Profession.FISHER:
        qty = 6 if person.skill_level == SkillLevel.LOW else 8
        fish_type = random.choices(
            ["sardine","herring","trout","salmon","swordfish","shark"],
            weights=[0.30,0.22,0.18,0.15,0.10,0.05], k=1
        )[0]
        guild.warehouse[fish_type] += qty
        logging.debug(f"{person.name} (ID={person.person_id}) => produced {qty} {fish_type}. Now guild has {guild.warehouse[fish_type]}")

    return forest_capacity

def farmer_produce_daily(person, guild, season_factor):
    base_qty = 6 if person.skill_level == SkillLevel.LOW else 8
    grain_qty = base_qty * season_factor
    guild.warehouse["grain"] += grain_qty
    logging.debug(f"{person.name} => +{grain_qty} grain. Now guild has {guild.warehouse['grain']}")

    if person.cows > 0:
        milk = person.cows
        guild.warehouse["milk"] += milk
        logging.debug(f"{person.name} got {milk} milk from {person.cows} cows => {guild.guild_name}. Now guild has {guild.warehouse['milk']}")
        # chance to slaughter
        if random.random() < 0.05 and person.cows > 0:
            person.cows -= 1
            guild.warehouse["beef"] += 2
            logging.debug(f"{person.name} slaughtered 1 cow => 2 beef => {guild.guild_name}. Now guild has {guild.warehouse['beef']}")

    if person.sheep > 0:
        w = person.sheep
        guild.warehouse["wool"] += w
        logging.debug(f"{person.name} sheared {w} wool => {guild.guild_name}. Now guild has {guild.warehouse['wool']}")

def parse_recipes_and_produce(person, guild, simulation) -> None:
    """
    Multi‑input production loop.

    ─────────────────────────────────────────── “2‑b” in plain words ───────────────────────────────────────────
    A guild should **stop producing** a finished item when the amount that is already
    • sitting locally **or**
    • listed in the market (for_sale)
    is “large enough”.  
    “Large enough” is defined as:

        finished_on_hand ≥ safety_buffer × max(  min_stocks[input_i]  for input_i in recipe )

    where *safety_buffer* = **1.10** (i.e. keep 10 % head‑room above the strict minimum).

    This guarantees:
    1. We never run out of storage because we keep a margin.
    2. We do not waste inputs if plenty of finished stock is already available.
    3. A single over‑sized market listing will *still* block new production until it sells,
       which is exactly what we want.
    ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    """
    config = INDUSTRY_CONFIG.get(guild.profession)
    if not config:                     # professions like miners & farmers skip this path
        return

    DAILY_BATCH_CAP = 10               # hard daily cap – prevents runaway loops
    SAFETY_BUFFER  = 1.30              # <‑‑ “2‑b”              (30 %)

    produced_anything = False

    for recipe in config["recipes"]:
        out_item  : str            = recipe["output_item"]
        inputs    : dict[str,int]  = recipe["inputs"]
        per_batch : int            = recipe["out_per_batch"]

        # ------------------------------------------------------------------
        #  Step 1 – how many finished goods are *already* around?
        # ------------------------------------------------------------------
        local_finished   = guild.warehouse.get(out_item, 0.0)
        listed_finished  = simulation.marketWarehouse.for_sale_map[out_item].get(guild, 0.0)
        finished_on_hand = local_finished + listed_finished           # 2‑b

        # ------------------------------------------------------------------
        #  Step 2 – compute the threshold that blocks new production
        #           ► max(min_stocks of all required inputs) * 1.30
        # ------------------------------------------------------------------
        raw_min_levels = [
            config["min_stocks"].get(raw, 0.0)
            for raw in inputs
        ]
        threshold = SAFETY_BUFFER * max(raw_min_levels, default=0.0)

        # If we already meet / exceed the threshold, skip this recipe
        if finished_on_hand >= threshold:
            logging.debug(
                f"[{guild.guild_name}]  skip {out_item:>14s}: "
                f"finished={finished_on_hand:.1f}  threshold={threshold:.1f}"
            )
            continue

        # ------------------------------------------------------------------
        #  Step 3 – how many batches can we realistically run today?
        # ------------------------------------------------------------------
        max_batches = DAILY_BATCH_CAP
        for raw_item, qty_needed in inputs.items():
            available = guild.warehouse.get(raw_item, 0.0)
            max_from_this_input = int(available // qty_needed)
            max_batches = min(max_batches, max_from_this_input)

        if max_batches == 0:
            logging.debug(
                f"[{guild.guild_name}]  no inputs for {out_item}; requirements={inputs}"
            )
            continue

        # ------------------------------------------------------------------
        #  Step 4 – consume inputs & add outputs
        # ------------------------------------------------------------------
        for raw_item, qty_needed in inputs.items():
            guild.warehouse[raw_item] -= qty_needed * max_batches

        guild.warehouse[out_item] += per_batch * max_batches
        produced_qty = per_batch * max_batches
        produced_anything = True

        logging.debug(
            f"[{guild.guild_name}]  produced {produced_qty:>6.1f}  {out_item:<14s}  "
            f"(batches={max_batches},  now={guild.warehouse[out_item]:.1f})"
        )

    # flag for wage calculation
    if produced_anything:
        guild.did_produce_today = True

def guild_buy_raw_materials(guild, simulation):
    """
    This replaces the old "place_bid(1.10 * ref_price)" logic
    with a profit-based approach that adaptively increases
    if the guild remains short for multiple days.
    """
    config = simulation.INDUSTRY_CONFIG.get(guild.profession, None)
    if not config:
        return  # no multi-ingredient production => skip

    # overhead & min_margin can come from config or a guess:
    overhead_per_unit = .001 # placeholder low value
    min_margin = .001

    # We'll store short-days in a dictionary on the simulation
    if not hasattr(simulation, "guild_days_short"):
        simulation.guild_days_short = {}  # { (guild, raw_item): int }

    min_stocks = config["min_stocks"]
    for raw_item, needed_amt in min_stocks.items():
        current = guild.warehouse[raw_item]
        if current >= needed_amt:
            # Not short => reset the days_short count
            simulation.guild_days_short[(guild, raw_item)] = 0
            continue

        # We are short
        shortfall = needed_amt - current

        # 1) Identify the final product(s) that use this raw_item:
        #    For example, if raw_item="sardine" => final_item="meal_sardine"
        #    Or do a more general approach if multiple recipes use 'sardine'.
        #    We'll just guess a single mapping, or you can code a lookup:
        final_item = raw_item_to_final(raw_item)  # Your custom function

        # 2) Grab the potential sale price from the market reference
        #    or from recent trades. We'll do the naive approach:
        final_price = simulation.marketWarehouse.goods[final_item]["price"]

        # 3) Base max bid = final_price - overhead - margin
        #    If negative => set to a small positive or 0
        max_bid_base = final_price - overhead_per_unit - min_margin
        if max_bid_base < 0.01:
            max_bid_base = 0.01

        # 4) See how many days we've been short
        key = (guild, raw_item)
        days_short = simulation.guild_days_short.get(key, 0)
        days_short += 1
        simulation.guild_days_short[key] = days_short

        # 5) Bump factor => 2% per day short
        bump_factor = 1.02 ** days_short
        max_bid_price = max_bid_base * bump_factor

        # 6) Place the BID with that price
        #    We'll assume your place_bid(...) now has a 'current_day' param
        simulation.marketWarehouse.place_bid(
            owner=guild,
            item=raw_item,
            quantity=shortfall,
            bid_price=max_bid_price,
            current_day=simulation.current_day  # for expiry
        )

        logging.debug(
            f"{guild.guild_name} is short of {raw_item} by {shortfall}, "
            f"days_short={days_short}, overhead={overhead_per_unit}, "
            f"min_margin={min_margin}, final_price={final_price}, "
            f"max_bid_base={max_bid_base:.2f}, bump_factor={bump_factor:.2f}, "
            f"placing BID={max_bid_price:.2f} for {shortfall}"
        )

def raw_item_to_final(raw_item):
    """
    Quick mapping from raw fish to the final meal item.
    e.g. 'sardine' -> 'meal_sardine'
    This can be more sophisticated if multiple recipes use 'sardine'.
    """
    if raw_item in ["sardine", "herring", "trout", "salmon", "swordfish", "shark"]:
        return f"meal_{raw_item}"
    elif raw_item == "beef":
        return "meal_meat"
    # fallback if we can't find a direct final item:
    return raw_item

# Gameplayer notes:
# - The guild's profession determines the recipes it can produce.
# - The guild's warehouse is where raw materials and finished goods are stored.
# - The guild's employees are the ones who produce the goods.
# - The guild's employees are paid wages in silver based on their skill level, production, and the guild's production status.
# - The guild's employee are also given some share of what they produced to do with as they please.
# - The guild's overhead and minimum margin are used to calculate the cost of production.
# - The guild's silver and gold are used for transactions.
# - The guild's loan balance is used for borrowing money.
# - The guild's number of wagons and horses are used for transport.
# - The guild's did_produce_today flag is used to determine if the guild produced anything today.
# - The guild's min_stocks dictionary is used to determine the minimum amount of raw materials the guild wants to have at any given time.
# - The guild's recipes list is used to determine what the guild can produce.
# - The guild can focus production on a single item or produce multiple items at once.
# - The guild can choose to research improvements to their production process, recipes, or guild management.
# - The guild can allow mentoring of employees by more experienced employees to improve their skills at the cost of production time.
# - The guild can choose to subsidize focused learning through the college system.
