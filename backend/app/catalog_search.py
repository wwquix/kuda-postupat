from __future__ import annotations

import re
import unicodedata

DASH_TRANSLATION = str.maketrans({character: "-" for character in "‐‑‒–—―−"})


def normalize_search_text(value: object | None) -> str:
    """Return the public catalog's stable Unicode search representation."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).translate(DASH_TRANSLATION)
    normalized = normalized.casefold().replace("ё", "е")
    return re.sub(r"\s+", " ", normalized).strip()


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def register_catalog_sqlite_functions(dbapi_connection: object) -> None:
    create_function = getattr(dbapi_connection, "create_function", None)
    if create_function is None:
        return
    create_function("catalog_normalize", 1, normalize_search_text, deterministic=True)
