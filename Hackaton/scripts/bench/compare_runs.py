"""Comparador semántico BEFORE/AFTER de las corridas del banco de pruebas.

Compara dos archivos ``<label>-results.json`` generados por ``run_probes.py``:

-Equaleranza de hash canónico por sonda (contenido idéntico).
-Informe de las diferencias estructurales de las sondas que cambian.
-Tabla de estado HTTP y duración por sonda.
-Código de salida distinto de cero si alguna sonda cambia de estado o de hash.

Uso::

    python scripts/bench/compare_runs.py BEFORE.json AFTER.json [--out informe.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canonical import canonical_json, diff_summary  # noqa: E402


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "results" not in payload:
        raise SystemExit(f"{path} no tiene la clave 'results'")
    return payload


def _index(payload: dict) -> dict[str, dict]:
    """Última ejecución por nombre de sonda (el runner puede repetir)."""
    indexed: dict[str, dict] = {}
    for record in payload["results"]:
        indexed[record["name"]] = record
    return indexed


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparador semántico BEFORE/AFTER")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--out", default="")
    parser.add_argument("--bodies-dir", default="", help="Directorio con los cuerpos guardados")
    args = parser.parse_args()

    before = _load(Path(args.before))
    after = _load(Path(args.after))
    before_index = _index(before)
    after_index = _index(after)

    names = sorted(set(before_index) | set(after_index))
    rows: list[dict] = []
    changed: list[dict] = []
    status_changed: list[str] = []

    for name in names:
        left = before_index.get(name)
        right = after_index.get(name)
        if left is None:
            status_changed.append(f"{name}: sólo existe en AFTER")
            continue
        if right is None:
            status_changed.append(f"{name}: sólo existe en BEFORE")
            continue
        same_hash = bool(left.get("hash")) and left.get("hash") == right.get("hash")
        same_status = left.get("status") == right.get("status") == 200
        row = {
            "name": name,
            "status_before": left.get("status"),
            "status_after": right.get("status"),
            "duration_ms_before": left.get("duration_ms"),
            "duration_ms_after": right.get("duration_ms"),
            "bytes_before": left.get("bytes"),
            "bytes_after": right.get("bytes"),
            "hash_before": left.get("hash"),
            "hash_after": right.get("hash"),
            "identical": bool(same_hash and same_status),
        }
        rows.append(row)
        if not same_status:
            status_changed.append(f"{name}: estado {left.get('status')} -> {right.get('status')}")
        if not same_hash:
            entry = dict(row)
            if args.bodies_dir:
                left_body = Path(args.bodies_dir) / before["label"] / f"{name}.json"
                right_body = Path(args.bodies_dir) / after["label"] / f"{name}.json"
                if left_body.exists() and right_body.exists():
                    entry["diff"] = diff_summary(
                        json.loads(left_body.read_text(encoding="utf-8")),
                        json.loads(right_body.read_text(encoding="utf-8")),
                    )
            changed.append(entry)

    identical = sum(1 for row in rows if row["identical"])
    report = {
        "before_label": before.get("label"),
        "after_label": after.get("label"),
        "probes_compared": len(rows),
        "identical": identical,
        "changed": len(changed),
        "status_changed": status_changed,
        "changed_rows": changed,
        "rows": rows,
        "before_summary": {key: value for key, value in before.items() if key != "results"},
        "after_summary": {key: value for key, value in after.items() if key != "results"},
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"sondas comparadas : {len(rows)}")
    print(f"idénticas         : {identical}")
    print(f"con diferencias   : {len(changed)}")
    if status_changed:
        print("cambios de estado HTTP:")
        for item in status_changed:
            print(f"  - {item}")
    for entry in changed:
        print(f"  * {entry['name']}: hash {entry['hash_before'][:12]} -> {entry['hash_after'][:12]}")
        for line in entry.get("diff", [])[:10]:
            print(f"      {line}")
    print(f"duración total BEFORE={report['before_summary'].get('total_duration_ms')} ms "
          f"AFTER={report['after_summary'].get('total_duration_ms')} ms")
    return 0 if (not changed and not status_changed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
