#!/usr/bin/env bash
# Corrida aislada y reproducible del banco de pruebas con límite de memoria.
#
#   scripts/bench/bench_isolated.sh --image IMG --label LABEL [--port 8011]
#                                 [--memory 512m] [--cpus 1.0] [--concurrency 4]
#                                 [--repeat 2] [--out-dir DIR]
#
# Levanta un contenedor desechable con la imagen indicada, limitado por cgroup
# (memoria y, opcionalmente, CPU), ejecuta las sondas HTTP y recoge evidencia
# real: estado HTTP, duración, cgroup memory.current/peak/memory.events y
# `docker inspect` del estado del contenedor (incluye OOMKilled).
#
# El script nunca imprime variables de entorno ni credenciales.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HACKATON_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

IMAGE=""
LABEL=""
PORT="8011"
MEMORY="512m"
MEMORY_SWAP=""
CPUS=""
CONCURRENCY="4"
REPEAT="2"
OUT_DIR="${HOME}/.hermes/cache/scratch/fuegoclaro-mem/evidence"
CONTAINER_NAME=""
KEEP_CONTAINER="0"

usage() {
    sed -n '2,20p' "$0"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --image) IMAGE="$2"; shift 2;;
        --label) LABEL="$2"; shift 2;;
        --port) PORT="$2"; shift 2;;
        --memory) MEMORY="$2"; shift 2;;
        --memory-swap) MEMORY_SWAP="$2"; shift 2;;
        --cpus) CPUS="$2"; shift 2;;
        --concurrency) CONCURRENCY="$2"; shift 2;;
        --repeat) REPEAT="$2"; shift 2;;
        --out-dir) OUT_DIR="$2"; shift 2;;
        --container-name) CONTAINER_NAME="$2"; shift 2;;
        --keep) KEEP_CONTAINER="1"; shift;;
        -h|--help) usage;;
        *) echo "argumento desconocido: $1" >&2; usage;;
    esac
done

if [[ -z "${IMAGE}" || -z "${LABEL}" ]]; then
    usage
fi

CONTAINER_NAME="${CONTAINER_NAME:-fuegoclaro-pruebas-bench-${LABEL}}"
RUN_DIR="${OUT_DIR}/${LABEL}"
mkdir -p "${RUN_DIR}"

# El límite de swap por defecto coincide con el de RAM: cgroup sin swap.
if [[ -z "${MEMORY_SWAP}" ]]; then
    MEMORY_SWAP="${MEMORY}"
fi

cleanup() {
    if [[ "${KEEP_CONTAINER}" != "1" ]]; then
        docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

echo "[bench] imagen=${IMAGE} contenedor=${CONTAINER_NAME} puerto=${PORT}"
echo "[bench] límites: memory=${MEMORY} memory-swap=${MEMORY_SWAP} cpus=${CPUS:-sin límite}"

RUN_ARGS=(
    -d
    --name "${CONTAINER_NAME}"
    --memory "${MEMORY}"
    --memory-swap "${MEMORY_SWAP}"
    --memory-swappiness 0
    --pids-limit 512
    -p "127.0.0.1:${PORT}:8000"
    -v "${HACKATON_DIR}/data:/app/data:ro"
)
if [[ -n "${CPUS}" ]]; then
    RUN_ARGS+=(--cpus "${CPUS}")
fi
if [[ -f "${HACKATON_DIR}/backend/.env" ]]; then
    RUN_ARGS+=(--env-file "${HACKATON_DIR}/backend/.env")
fi

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
docker run "${RUN_ARGS[@]}" "${IMAGE}" >/dev/null

BASE_URL="http://127.0.0.1:${PORT}"

echo "[bench] esperando health..."
READY=0
for _ in $(seq 1 120); do
    STATUS="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/api/v1/health" || true)"
    if [[ "${STATUS}" == "200" ]]; then
        READY=1
        break
    fi
    sleep 1
done
if [[ "${READY}" != "1" ]]; then
    echo "[bench] ERROR: el contenedor no respondió health" >&2
    docker inspect "${CONTAINER_NAME}" > "${RUN_DIR}/docker-inspect.json" || true
    docker logs "${CONTAINER_NAME}" > "${RUN_DIR}/container.log" 2>&1 || true
    exit 2
fi

snapshot() {
    local phase="$1"
    docker exec "${CONTAINER_NAME}" sh /app/scripts/bench/cgroup_snapshot.sh > "${RUN_DIR}/cgroup-${phase}.txt" 2>&1 || true
    docker inspect "${CONTAINER_NAME}" > "${RUN_DIR}/docker-inspect-${phase}.json" || true
}

snapshot "startup"

echo "[bench] fase secuencial (concurrency=1, repeat=1)"
python3 "${SCRIPT_DIR}/run_probes.py" \
    --base-url "${BASE_URL}" \
    --label "${LABEL}-secuencial" \
    --out-dir "${OUT_DIR}" \
    --concurrency 1 \
    --repeat 1 \
    | tee "${RUN_DIR}/run-secuencial.log"

snapshot "after-secuencial"

echo "[bench] fase concurrente (concurrency=${CONCURRENCY}, repeat=${REPEAT})"
python3 "${SCRIPT_DIR}/run_probes.py" \
    --base-url "${BASE_URL}" \
    --label "${LABEL}-concurrente" \
    --out-dir "${OUT_DIR}" \
    --concurrency "${CONCURRENCY}" \
    --repeat "${REPEAT}" \
    | tee "${RUN_DIR}/run-concurrente.log"

snapshot "after-concurrente"

# Rondas repetidas del endpoint más pesado (detecciones con limit=20000).
echo "[bench] fase de reiterate sobre detecciones limit=20000"
python3 "${SCRIPT_DIR}/run_probes.py" \
    --base-url "${BASE_URL}" \
    --label "${LABEL}-reiterate" \
    --out-dir "${OUT_DIR}" \
    --concurrency 1 \
    --repeat 5 \
    --only detections_json,detections_geojson,protected_areas,environmental_alerts,analytics_summary \
    | tee "${RUN_DIR}/run-reiterate.log"

snapshot "after-reiterate"

docker logs "${CONTAINER_NAME}" > "${RUN_DIR}/container.log" 2>&1 || true
docker inspect "${CONTAINER_NAME}" > "${RUN_DIR}/docker-inspect-final.json" || true

{
    echo "label=${LABEL}"
    echo "image=${IMAGE}"
    echo "container=${CONTAINER_NAME}"
    echo "port=${PORT}"
    echo "memory_limit=${MEMORY}"
    echo "memory_swap_limit=${MEMORY_SWAP}"
    echo "cpus_limit=${CPUS:-sin límite}"
    echo "finished_at=$(date -Iseconds)"
} > "${RUN_DIR}/run-meta.txt"

echo "[bench] evidencia en ${RUN_DIR}"
