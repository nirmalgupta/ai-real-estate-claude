"""Adapter import hub.

Each county adapter is a separate module. Importing them here is what
fires their `register()` calls. Adding a new county = add an `import`
line below.

Wrapped in try/except so a single broken adapter doesn't break the
registry for others.
"""
from __future__ import annotations

# Add new county adapter imports here.
# Each import fires a `register()` call at module load time.

def _try_import(modname: str) -> None:
    """Best-effort import. A broken adapter must not break the registry."""
    try:
        __import__(f"pipeline.fetch.county.{modname}")
    except Exception:
        pass


# DFW
_try_import("tx_denton")          # 48121

# Houston metro
_try_import("tx_harris")          # 48201
_try_import("tx_fortbend")        # 48157
_try_import("tx_montgomery")      # 48339
_try_import("tx_brazoria")        # 48039
_try_import("tx_galveston")       # 48167
