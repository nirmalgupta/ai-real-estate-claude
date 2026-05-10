"""Read a wiki page back into a facts dict.

The page has JSON frontmatter wrapped in `---` fences. We pull just the
JSON, strip fact provenance metadata, and return a flat
`{key: value}` dict for downstream computation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_wiki_facts(wiki_page: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse a wiki property page.

    Returns:
        (frontmatter, facts) where frontmatter has top-level metadata
        (address, lat, lon, tract_fips...) and facts is `{key: value}`
        with provenance flattened out.
    """
    text = wiki_page.read_text()
    if not text.startswith("---"):
        raise ValueError(f"{wiki_page} doesn't start with --- frontmatter")

    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError(f"{wiki_page} has no closing --- fence")

    fm_text = text[3:end].strip()
    fm = json.loads(fm_text)

    # `facts` field has {key: {value, source, ...}}; flatten to {key: value}
    raw_facts = fm.pop("facts", {})
    flat = {k: v["value"] for k, v in raw_facts.items()}
    return fm, flat
