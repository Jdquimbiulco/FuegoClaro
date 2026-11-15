"""Canonicalización y hashing de respuestas HTTP para comparación semántica.

El objetivo es comparar el *contenido* de dos respuestas de la API sin que
interferan los campos que se regeneran en cada arranque (p. ej. ``loaded_at``).
La canonicalización:

- ordena las claves de los diccionarios,
- descarta un conjunto explícito de claves volátiles,
- preserva el orden de las listas (el orden es información científica),
- no redondea ni reescribe números (la API ya redondea a 6 decimales).

Cualquier diferencia real de contenido produce un hash distinto.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Claves generadas en tiempo de ejecución. No aportan información sobre el
# dominio: son marcas de carga del proceso.
VOLATILE_KEYS = frozenset({"loaded_at"})


def canonicalize(value: Any) -> Any:
    """Devuelve una estructura JSON estable y comparable."""
    if isinstance(value, dict):
        return {
            str(key): canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in VOLATILE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_hash_text(text: str) -> str:
    """Hash de un cuerpo que no es JSON (por ejemplo, la exportación CSV)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def diff_summary(before: Any, after: Any, path: str = "$", limit: int = 40) -> list[str]:
    """Diferencias estructurales legibles entre dos respuestas canonicalizadas."""
    diffs: list[str] = []
    if len(diffs) >= limit:
        return diffs
    if type(before) is not type(after) and not (
        isinstance(before, (int, float)) and isinstance(after, (int, float))
    ):
        return [f"{path}: tipo {type(before).__name__} -> {type(after).__name__}"]
    if isinstance(before, dict):
        for key in sorted(set(before) | set(after)):
            if key not in before:
                diffs.append(f"{path}.{key}: ausente antes")
            elif key not in after:
                diffs.append(f"{path}.{key}: ausente despues")
            else:
                diffs.extend(diff_summary(before[key], after[key], f"{path}.{key}", limit - len(diffs)))
            if len(diffs) >= limit:
                break
        return diffs
    if isinstance(before, list):
        if len(before) != len(after):
            diffs.append(f"{path}: longitud {len(before)} -> {len(after)}")
        for index, (left, right) in enumerate(zip(before, after)):
            diffs.extend(diff_summary(left, right, f"{path}[{index}]", limit - len(diffs)))
            if len(diffs) >= limit:
                break
        return diffs
    if before != after:
        diffs.append(f"{path}: {before!r} -> {after!r}")
    return diffs
