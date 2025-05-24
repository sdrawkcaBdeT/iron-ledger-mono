"""
resource_loader.py
---------------------------------
Loads all economic & crafting metadata from the 'arena_data' package 
and exposes a global CATALOG. Requires: `pip install pyyaml numpy arena_data`.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple # Added Tuple

import yaml
import numpy as np
from importlib import resources

# --- Dataclasses (incorporating new fields) ---
@dataclass
class Good:
    name: str
    vec: List[float]
    base_price: float
    weight: float
    durability: int # For tools, this is base max durability
    tech_tier: int
    tool_type: Optional[str] = None # NEW: e.g., "AXE", "PICKAXE", "SAW" (for tools)
    # Add any other common fields from goods.yaml if consistently present

@dataclass
class Station:
    name: str
    slots: int
    durability: int # Renamed from 'dur' for consistency if Good uses 'durability'
    tier: int
    build_labour: float
    build_capital: float # Renamed from 'build_cap'

@dataclass
class Recipe:
    key: str
    output: str
    out_per_batch: int
    inputs: Dict[str, int]
    labour: float
    station_required: Optional[str]
    time: float # In-game days per batch
    profession_id: str # e.g., "LUMBERJACK", "CARPENTER" (maps to Profession enum string value)
    level_required: int # Benchmark level (1-10)
    exp_yield: int
    tool_type_required: Optional[str] = None # e.g., "SAW", "FORGE_HAMMER"

@dataclass
class Material:
    name: str
    harvest_speed_range: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    durability_modifier_range: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    weight_factor: float = 1.0

@dataclass
class CraftQuality: # From craft_quality.yaml
    name: str
    gather_speed_range: Tuple[float, float]
    durability_range: Tuple[float, float]
    move_speed_range: Tuple[float, float]

@dataclass
class RepairState: # From repair_state.yaml
    name: str
    gather_speed_mult: float
    move_speed_mult: float
    durability_floor: float

@dataclass
class ToolDefinition: # From tools.yaml
    name: str # Key from tools.yaml, e.g., "bronze_pickaxe"
    tool_class: str # e.g., "pickaxe", "hatchet" (gameplay system usage)
    material: str # Default material ID (e.g., "Bronze", "Iron")
    base_speed: float # Baseline gather speed multiplier
    base_durability: int # Reference durability before material/quality
    weight_base: float # Base weight before material factor
    # tool_type can be derived from toolClass or goods.yaml if tools are also goods


# Helper function to load YAML from the package
def _load_yaml_from_package(file_name: str) -> Dict:
    """Loads a YAML file from the 'arena_data.tables' subpackage."""
    try:
        # The package name is 'arena_data', and 'tables' is a directory within it.
        with resources.open_text("arena_data.tables", file_name, encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if data is not None else {}
    except FileNotFoundError:
        print(f"ERROR: YAML file not found in package: arena_data.tables/{file_name}")
        raise # Or return {} and handle upstream
    except Exception as e:
        print(f"ERROR: Could not load YAML file arena_data.tables/{file_name}: {e}")
        raise # Or return {}

class ResourceCatalog:
    def __init__(self) -> None:
        self.goods: Dict[str, Good] = {}
        self.stations: Dict[str, Station] = {}
        self.recipes: Dict[str, Recipe] = {}
        self.materials: Dict[str, Material] = {}
        self.craft_qualities: Dict[str, CraftQuality] = {}
        self.repair_states: Dict[str, RepairState] = {}
        self.tool_definitions: Dict[str, ToolDefinition] = {}
        self.professions_yaml_data: Dict[str, Any] = {} # For the stubby professions.yaml

        self._load_all_data()

        if self.goods:
            valid_goods_for_vec = [g for g in self.goods.values() if g.vec and len(g.vec) == 9]
            self._vec_matrix = np.array([g.vec for g in valid_goods_for_vec])
            self._item_index = {g.name: i for i, g in enumerate(valid_goods_for_vec)}
        else:
            self._vec_matrix = np.array([])
            self._item_index = {}

    def _load_all_data(self):
        # Goods
        goods_data_raw = _load_yaml_from_package("goods.yaml")
        for name, entry in goods_data_raw.items():
            self.goods[name] = Good(
                name=name,
                vec=entry.get("vec", [0.0]*9),
                base_price=entry.get("base_price", 0.0),
                weight=entry.get("weight", 1.0),
                durability=entry.get("durability", 1),
                tech_tier=entry.get("tech", 0),
                tool_type=entry.get("tool_type")
            )

        # Stations
        stations_data_raw = _load_yaml_from_package("stations.yaml")
        for name, entry in stations_data_raw.items():
            self.stations[name] = Station(
                name=name,
                slots=entry["slots"],
                durability=entry["dur"],
                tier=entry["tier"],
                build_labour=entry["build_lab"],
                build_capital=entry["build_cap"]
            )

        # Recipes
        recipes_data_raw = _load_yaml_from_package("recipes.yaml")
        for key, entry in recipes_data_raw.items():
            self.recipes[key] = Recipe(
                key=key,
                output=entry["output"],
                out_per_batch=entry["out"],
                inputs=entry["inputs"],
                labour=entry["labour"],
                station_required=entry.get("station"), # station_required for clarity
                time=entry["time"],
                profession_id=entry.get("profession_id"),
                level_required=entry.get("level_required", 0),
                exp_yield=entry.get("exp_yield", 0),
                tool_type_required=entry.get("tool_type_required")
            )
        
        # Materials
        materials_metal_data = _load_yaml_from_package("materials_metal.yaml")
        materials_cloth_data = _load_yaml_from_package("materials_cloth.yaml")
        materials_leather_data = _load_yaml_from_package("materials_leather.yaml")
        combined_materials_raw = {**materials_metal_data, **materials_cloth_data, **materials_leather_data}
        for name, entry in combined_materials_raw.items():
            self.materials[name] = Material(
                name=name,
                harvest_speed_range=tuple(entry.get("harvestSpeedRange", [0.0, 0.0])),
                durability_modifier_range=tuple(entry.get("durabilityModifierRange", [0.0, 0.0])), # Mapped from durabilityRange
                weight_factor=entry.get("weightFactor", 1.0)
            )

        # Craft Qualities
        craft_qualities_data = _load_yaml_from_package("craft_quality.yaml")
        for name, entry in craft_qualities_data.items():
            self.craft_qualities[name] = CraftQuality(
                name=name,
                gather_speed_range=tuple(entry["gatherSpeedRange"]),
                durability_range=tuple(entry["durabilityRange"]),
                move_speed_range=tuple(entry["moveSpeedRange"])
            )

        # Repair States
        repair_states_data = _load_yaml_from_package("repair_state.yaml")
        for name, entry in repair_states_data.items():
            self.repair_states[name] = RepairState(
                name=name,
                gather_speed_mult=entry["gatherSpeedMult"],
                move_speed_mult=entry["moveSpeedMult"],
                durability_floor=entry["durabilityFloor"]
            )

        # Tool Definitions (from tools.yaml)
        tool_definitions_data = _load_yaml_from_package("tools.yaml")
        for name, entry in tool_definitions_data.items():
            # Try to get tool_type from goods.yaml if this tool is also a good,
            # otherwise try to derive or get from tools.yaml itself.
            tool_good_entry = self.goods.get(name)
            derived_tool_type = tool_good_entry.tool_type if tool_good_entry else None
            if not derived_tool_type: # Fallback if also defined in tools.yaml
                 derived_tool_type = entry.get("tool_type") # If you add it to tools.yaml
            
            self.tool_definitions[name] = ToolDefinition(
                name=name,
                tool_class=entry["toolClass"],
                material=entry["material"],
                base_speed=entry["baseSpeed"],
                base_durability=entry["baseDurability"],
                weight_base=entry["weightBase"],
                tool_type=derived_tool_type # Assign derived or directly defined tool_type
            )
        
        # Load the stubby professions.yaml if other sim parts use it
        self.professions_yaml_data = _load_yaml_from_package("professions.yaml")

    def get_good(self, item_name: str) -> Optional[Good]:
        return self.goods.get(item_name)

    def get_recipe(self, recipe_key: str) -> Optional[Recipe]:
        return self.recipes.get(recipe_key)

    def get_station(self, station_name: str) -> Optional[Station]:
        return self.stations.get(station_name)

    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        return self.tool_definitions.get(tool_name)
        
    def get_material(self, material_name: str) -> Optional[Material]:
        return self.materials.get(material_name)

    def get_craft_quality(self, quality_name: str) -> Optional[CraftQuality]:
        return self.craft_qualities.get(quality_name)
        
    def get_repair_state(self, state_name: str) -> Optional[RepairState]:
        return self.repair_states.get(state_name)

    def vec(self, item: str) -> np.ndarray: # Kept for compatibility
        good = self.get_good(item)
        if good and good.vec and len(good.vec) == 9:
            return np.asarray(good.vec, dtype=float)
        # print(f"Warning: Item '{item}' not found or has invalid vector in CATALOG.goods for vec() method.")
        return np.zeros(9, dtype=float)


# Global CATALOG instance, created when this module is imported.
CATALOG = ResourceCatalog()

if __name__ == "__main__":
    print(f"Loaded {len(CATALOG.goods)} goods.")
    print(f"Loaded {len(CATALOG.recipes)} recipes.")
    print(f"Loaded {len(CATALOG.stations)} stations.")
    print(f"Loaded {len(CATALOG.tool_definitions)} tool definitions.")
    
    if "bread_basic" in CATALOG.recipes:
        print(f"\nRecipe 'bread_basic': {CATALOG.recipes['bread_basic']}")
    if "steel_axe" in CATALOG.goods: # Assuming steel_axe is now in goods.yaml
        print(f"\nGood 'steel_axe': {CATALOG.goods['steel_axe']}")
    elif "steel_hatchet" in CATALOG.tool_definitions: # Fallback to tool_definitions if not in goods
         print(f"\nTool Definition 'steel_hatchet': {CATALOG.tool_definitions['steel_hatchet']}")