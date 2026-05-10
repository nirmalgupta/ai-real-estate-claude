"""Build a per-property wiki page from one or more FetchResults.

Each fact preserves provenance — source + url + fetched_at — so the
analysis layer (or a human) can audit any number that ends up in the
final report.

Output shape: `wiki/properties/<address-slug>.md` with YAML frontmatter
holding the structured facts and a human-readable section listing them.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult


def _fact_to_jsonable(f: Fact) -> dict:
    return {
        "value": f.value,
        "source": f.source,
        "fetched_at": f.fetched_at,
        "raw_ref": f.raw_ref,
        "confidence": f.confidence,
        "note": f.note,
    }


def merge_facts(results: Iterable[FetchResult]) -> dict[str, Fact]:
    """First-source-wins merge across results.

    A real conflict-resolution layer comes later (Phase 3+). For now,
    if two sources provide the same key we keep the first and log the
    conflict in the fact's note.
    """
    merged: dict[str, Fact] = {}
    conflicts: dict[str, list[str]] = {}
    for r in results:
        if not r.ok:
            continue
        for k, v in r.facts.items():
            if k in merged:
                conflicts.setdefault(k, [merged[k].source]).append(v.source)
            else:
                merged[k] = v
    for k, sources in conflicts.items():
        existing = merged[k]
        merged[k] = Fact(
            value=existing.value,
            source=existing.source,
            fetched_at=existing.fetched_at,
            raw_ref=existing.raw_ref,
            confidence=existing.confidence,
            note=(existing.note or "") + f" [conflict: also reported by {', '.join(sources[1:])}]",
        )
    return merged


def render_page(address: Address, facts: dict[str, Fact], errors: list[str]) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    frontmatter = {
        "address": address.matched,
        "slug": address.slug,
        "lat": address.lat,
        "lon": address.lon,
        "tract_fips": address.full_tract_fips,
        "county_fips": address.full_county_fips,
        "county_name": address.county_name,
        "state": address.state_abbr,
        "zip": address.zip,
        "generated_at": now,
        "facts": {k: _fact_to_jsonable(v) for k, v in facts.items()},
    }

    lines = [
        "---",
        json.dumps(frontmatter, indent=2),
        "---",
        "",
        f"# {address.matched}",
        "",
        f"_Wiki page generated {now} from {len({f.source for f in facts.values()})} source(s)._",
        "",
        "## Location",
        f"- **Lat/Lon:** {address.lat:.6f}, {address.lon:.6f}",
        f"- **County:** {address.county_name} ({address.full_county_fips})",
        f"- **Census tract:** {address.full_tract_fips}",
        f"- **ZIP:** {address.zip}",
        "",
        "## Facts",
    ]

    if not facts:
        lines.append("_No facts collected — all fetchers errored or returned empty._")
    else:
        # Group facts by source for readability
        by_source: dict[str, list[tuple[str, Fact]]] = {}
        for k, v in facts.items():
            by_source.setdefault(v.source, []).append((k, v))
        for src in sorted(by_source.keys()):
            lines.append(f"\n### From `{src}`")
            for k, v in by_source[src]:
                val = v.value
                if isinstance(val, (int, float)) and k.endswith(("_income", "_value", "_rent")):
                    val_str = f"${val:,}"
                else:
                    val_str = str(val)
                note = f" — _{v.note}_" if v.note else ""
                lines.append(f"- **{k}**: {val_str}{note}")

    if errors:
        lines.append("\n## Fetch errors")
        for e in errors:
            lines.append(f"- {e}")

    lines.append("")
    return "\n".join(lines)


def write_page(
    address: Address, results: list[FetchResult], wiki_root: Path
) -> Path:
    facts = merge_facts(results)
    errors = [f"{r.source_name}: {r.error}" for r in results if not r.ok]
    properties_dir = wiki_root / "properties"
    properties_dir.mkdir(parents=True, exist_ok=True)
    out = properties_dir / f"{address.slug}.md"
    out.write_text(render_page(address, facts, errors))
    return out
