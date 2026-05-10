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
_try_import("tx_dallas")          # 48113
_try_import("tx_tarrant")         # 48439
_try_import("tx_collin")          # 48085

# Austin metro
_try_import("tx_travis")          # 48453
_try_import("tx_williamson")      # 48491
_try_import("tx_hays")            # 48209

# Houston metro
_try_import("tx_harris")          # 48201
_try_import("tx_fortbend")        # 48157
_try_import("tx_montgomery")      # 48339
_try_import("tx_brazoria")        # 48039
_try_import("tx_galveston")       # 48167

# Miami metro (FL — disclosure state, sale prices public)
_try_import("fl_miami_dade")      # 12086
_try_import("fl_broward")         # 12011
_try_import("fl_palmbeach")       # 12099

# Raleigh / Triangle metro (NC — disclosure state)
_try_import("nc_wake")            # 37183
_try_import("nc_durham")          # 37063
_try_import("nc_orange")          # 37135
_try_import("nc_chatham")         # 37037
_try_import("nc_johnston")        # 37101
