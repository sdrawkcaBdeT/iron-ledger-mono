"""
arena_data package – runtime access to YAML tables.

Usage example:
    import importlib.resources as res, yaml, arena_data

    goods = yaml.safe_load(
        res.files(arena_data).joinpath("tables/goods.yaml").read_text()
    )
"""
__all__ = ["__version__"]
__version__ = "0.2.0"