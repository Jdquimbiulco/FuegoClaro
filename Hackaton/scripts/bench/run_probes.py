"""Banco de pruebas reproducible: ejecuta sondas HTTP y guarda evidencia real.

Uso típico::

    python scripts/bench/run_probes.py \
        --base-url http://127.0.0.1:8010 \
        --label baseline \
        --out-dir /home/erickobando/.hermes/cache/scratch/fuegoclaro-mem/evidence

El runner usa sólo la biblioteca estándar (``urllib``) para poder ejecutarse
tanto en el host como dentro del contenedor de pruebas.

Cada sonda registra: código HTTP, duración real en milisegundos, tamaño del
cuerpo, tipo de contenido y hash canónico del contenido. Los cuerpos se
guardan aparte para permitir la comparación semántica BEFORE/AFTER.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canonical import canonical_hash, canonical_hash_text, canonical_json  # noqa: E402
from probe_spec import DYNAMIC_SOURCES, PROBES, Probe  # noqa: E402

USER_AGENT = "fuegoclaro-bench/1.0"


def _build_url(base_url: str, probe: Probe, params: dict[str, Any]) -> str:
    query = {key: value for key, value in params.items() if value is not None}
    url = base_url.rstrip("/") + probe.path
    if query:
        url = url + "?" + urllib.parse.urlencode(query)
    return url


def _run_probe(base_url: str, probe: Probe, timeout: float) -> dict[str, Any]:
    url = _build_url(base_url, probe, probe.params)
    request = urllib.request.Request(url, method=probe.method, headers={"User-Agent": USER_AGENT})
    started = time.perf_counter()
    status: int | None = None
    body_bytes = b""
    error: str | None = None
    headers: dict[str, str] = {}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            headers = {key.lower(): value for key, value in response.headers.items()}
            body_bytes = response.read()
    except urllib.error.HTTPError as exc:  # respuesta 4xx/5xx: es evidencia
        status = int(exc.code)
        headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
        body_bytes = exc.read()
        error = f"HTTPError {exc.code}"
    except Exception as exc:  # noqa: BLE001 - fallos de red son evidencia
        error = f"{type(exc).__name__}: {exc}"
    duration_ms = (time.perf_counter() - started) * 1000.0

    content_type = headers.get("content-type", "")
    record: dict[str, Any] = {
        "name": probe.name,
        "method": probe.method,
        "url": url,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "bytes": len(body_bytes),
        "content_type": content_type,
        "error": error,
    }
    text = body_bytes.decode("utf-8", errors="replace")
    if probe.body and "json" in content_type:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            record["hash"] = canonical_hash_text(text)
            record["parse_error"] = True
            record["text_prefix"] = text[:400]
            return record
        record["hash"] = canonical_hash(payload)
        record["_payload"] = payload
    else:
        record["hash"] = canonical_hash_text(text)
    return record


def _save_bodies(records: list[dict[str, Any]], out_dir: Path, label: str) -> None:
    body_dir = out_dir / "responses" / label
    body_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        payload = record.pop("_payload", None)
        if payload is None:
            continue
        path = body_dir / f"{record['name']}.json"
        path.write_text(canonical_json(payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Banco de pruebas HTTP de FuegoClaro")
    parser.add_argument("--base-url", required=True, help="Raíz del servidor, p. ej. http://127.0.0.1:8010")
    parser.add_argument("--label", required=True, help="Etiqueta de la corrida")
    parser.add_argument("--out-dir", required=True, help="Directorio de salida de la evidencia")
    parser.add_argument("--concurrency", type=int, default=1, help="Sondas simultáneas")
    parser.add_argument("--repeat", type=int, default=1, help="Repeticiones de cada sonda")
    parser.add_argument("--timeout", type=float, default=600.0, help="Timeout por sonda (s)")
    parser.add_argument("--only", default="", help="Lista de sondas a ejecutar (separada por comas)")
    parser.add_argument("--skip", default="", help="Lista de sondas a omitir (separada por comas)")
    parser.add_argument("--no-save-bodies", action="store_true", help="No guardar los cuerpos de respuesta")
    parser.add_argument("--no-dynamic", action="store_true", help="No resolver sondas con id dinámico")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    only = {item.strip() for item in args.only.split(",") if item.strip()}
    skip = {item.strip() for item in args.skip.split(",") if item.strip()}
    probes = [
        probe
        for probe in PROBES
        if (not only or probe.name in only) and probe.name not in skip
    ]

    plan: list[Probe] = []
    for _ in range(max(1, args.repeat)):
        plan.extend(probes)

    results: list[dict[str, Any]] = []
    payloads_by_name: dict[str, Any] = {}

    def _execute(probe: Probe) -> dict[str, Any]:
        record = _run_probe(args.base_url, probe, args.timeout)
        payload = record.pop("_payload", None)
        if payload is not None:
            if any(source[0] == probe.name for source in DYNAMIC_SOURCES.values()):
                payloads_by_name[probe.name] = payload
            if not args.no_save_bodies:
                body_dir = out_dir / 'responses' / args.label
                body_dir.mkdir(parents=True, exist_ok=True)
                (body_dir / f'{probe.name}.json').write_text(canonical_json(payload), encoding='utf-8')
        return record

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        for record in pool.map(_execute, plan):
            results.append(record)

    # Sondas con identificador dinámico (p. ej. detalle de evento).
    if not args.no_dynamic:
        for name, (source_name, extractor) in DYNAMIC_SOURCES.items():
            source = payloads_by_name.get(source_name)
            if source is None:
                results.append(
                    {
                        "name": name,
                        "method": "GET",
                        "url": "",
                        "status": None,
                        "duration_ms": 0.0,
                        "bytes": 0,
                        "content_type": "",
                        "error": "sin payload de origen",
                        "hash": None,
                    }
                )
                continue
            try:
                dynamic_id = extractor(source)
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "name": name,
                        "method": "GET",
                        "url": "",
                        "status": None,
                        "duration_ms": 0.0,
                        "bytes": 0,
                        "content_type": "",
                        "error": f"no se pudo resolver id: {exc}",
                        "hash": None,
                    }
                )
                continue
            probe = Probe(name=name, path=f"/api/v1/fire-events/{dynamic_id}")
            record = _run_probe(args.base_url, probe, args.timeout)
            record["url"] = record["url"]
            record["resolved_id"] = dynamic_id
            record.pop("_payload", None)
            results.append(record)

    if not args.no_save_bodies:
        _save_bodies(results, out_dir, args.label)

    ok = sum(1 for record in results if record.get("status") == 200)
    summary = {
        "label": args.label,
        "base_url": args.base_url,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "concurrency": args.concurrency,
        "repeat": args.repeat,
        "probes_planned": len(plan),
        "records": len(results),
        "status_ok": ok,
        "status_fail": len(results) - ok,
        "total_duration_ms": round(sum(float(r.get("duration_ms", 0.0)) for r in results), 3),
        "max_duration_ms": round(max((float(r.get("duration_ms", 0.0)) for r in results), default=0.0), 3),
        "results": results,
    }
    path = out_dir / f"{args.label}-results.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    print(f"resultado: {path}")
    return 0 if summary["status_fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
