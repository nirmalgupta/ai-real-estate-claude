"""AI Real Estate pipeline — deterministic data layer + LLM analysis.

Layered:
    fetch/      raw data from authoritative sources
    extract/    raw -> structured facts (LLM-assisted)
    wiki/       canonical knowledge base, one page per entity
    analyze/    section drafters that read wiki facts
"""
