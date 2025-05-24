"""
Loads arena-data tables exactly once, validates them against JSON-Schema
(if present), and provides typed helpers.
"""
from importlib import resources
from pathlib import Path
import yaml, jsonschema, json

_TABLE_DIR = resources.files("arena_data") / "tables"
_SCHEMA_DIR = resources.files("arena_data") / "schema"

_cache: dict[str, dict] = {}

def _validate(name: str, data: dict):
    schema_path = _SCHEMA_DIR / f"{name}.schema.json"
    if schema_path.exists():
        schema = yaml.safe_load(schema_path.read_text()) \
                 if schema_path.suffix in (".yaml", ".yml") \
                 else json.loads(schema_path.read_text())
        jsonschema.validate(data, schema)

def load_table(name: str) -> dict:
    if name in _cache:
        return _cache[name]
    file_path = _TABLE_DIR / f"{name}.yaml"
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    _validate(name, data)
    _cache[name] = data
    return data
