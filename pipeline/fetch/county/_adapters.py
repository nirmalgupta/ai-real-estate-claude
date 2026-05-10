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

try:
    from pipeline.fetch.county import tx_denton  # noqa: F401
except Exception:
    pass
