"""Bounded referential-stakes signals; a negative result is not clearance."""
import re
import unicodedata

PATTERNS = {
    'protected-reference': r'\bprotected[\s_-]+(?:drawer|records?|family|material|bod(?:y|ies)|archives?)\b',
    'designated-reference': r'\bdesignated[\s_-]+(?:records?|stakes|material)\b',
    'coupled-stakes': r'\bcoupled[\s_-]+(?:stakes|context)\b',
    'witness-ledger': r'\bwitness[\s_-]+ledger\b',
    'sealed-reference': r'\bsealed[\s_-]+(?:drawer|records?|family|archive|witness)\b',
    'reserved-four': r'\breserved[\s_-]+four\b',
    'protected-ledger': r'\bprotected\.jsonl\b',
}


def stakes_signals(value) -> list[str]:
    """Inspect text values, never trust a clear metadata flag or retrieve a body."""
    def strings(item):
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            for child in item.values():
                yield from strings(child)
        elif isinstance(item, list):
            for child in item:
                yield from strings(child)
    text = unicodedata.normalize('NFKC', '\n'.join(strings(value))).casefold()
    text = text.translate(str.maketrans({'–': '-', '—': '-', '‑': '-'}))
    return sorted(name for name, pattern in PATTERNS.items() if re.search(pattern, text))
