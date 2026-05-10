"""Light multi-property search by city / zip / lat-lon radius.

Counterpart to `pipeline.run` (single-address deep audit). Search returns
a key:value summary card per candidate listing so the user can scan a
list and pick which ones deserve the full per-property analysis.

The data source is Redfin's `stingray/api/gis-csv` endpoint, which
returns CSV listings for a polygon. Free, no key, currently stable.
"""
