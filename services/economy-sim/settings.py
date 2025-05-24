"""
Central tweak‑sheet for balancing knobs and shared constants.
Keeping them here means no more magic numbers sprinkled everywhere.
"""

# Logistics ------------------------------------------------------------------
TRANSPORT_CAPACITY = {"hand": 8, "horse_cart": 30, "wagon": 60}

# Economy / survival ---------------------------------------------------------
MEAL_ITEMS  = [
    "bread", "meal_meat", "meal_sardine", "meal_herring",
    "meal_trout", "meal_salmon", "meal_swordfish", "meal_shark",
]
DRINK_ITEMS = ["beer", "milk"]

DEFAULT_KEEP_STOCK         = 5     # fallback when no min_stocks entry
PERSON_FOOD_NEED_DAILY     = 2
PERSON_DRINK_NEED_DAILY    = 1

# World simulation -----------------------------------------------------------
FOREST_MAX_CAPACITY        = 5_000
FOREST_REGROWTH_PER_DAY    = 80
