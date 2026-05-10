"""Adapter import hub.

Each county adapter is a separate module. Importing them here is what
fires their `register()` calls. Adding a new county = add an `import`
line below.

Wrapped in try/except so a single broken adapter doesn't break the
registry for others.
"""
from __future__ import annotations

# Add new county adapter imports here.
# Example: `from pipeline.fetch.county import tx_montgomery  # noqa: F401`

# Currently no adapters are registered — the pipeline runs without
# county data and notes that gap in the report.
