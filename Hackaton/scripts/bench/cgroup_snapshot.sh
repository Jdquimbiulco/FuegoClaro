#!/bin/sh
# Snapshot de métricas cgroup v2 de un contenedor (uso interno del banco de pruebas).
# Se ejecuta con `docker exec <contenedor> sh /app/scripts/bench/cgroup_snapshot.sh`.
# No imprime secretos: sólo métricas del kernel.
set -eu

CG=/sys/fs/cgroup

read_or_zero() {
    if [ -r "$1" ]; then
        cat "$1" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

echo "memory.current=$(read_or_zero $CG/memory.current)"
echo "memory.peak=$(read_or_zero $CG/memory.peak)"
echo "memory.max=$(read_or_zero $CG/memory.max)"
echo "memory.swap.current=$(read_or_zero $CG/memory.swap.current)"
echo "memory.swap.max=$(read_or_zero $CG/memory.swap.max)"
echo "memory.events.high=$(awk '$1=="high"{print $2}' $CG/memory.events 2>/dev/null || echo 0)"
echo "memory.events.max=$(awk '$1=="max"{print $2}' $CG/memory.events 2>/dev/null || echo 0)"
echo "memory.events.oom=$(awk '$1=="oom"{print $2}' $CG/memory.events 2>/dev/null || echo 0)"
echo "memory.events.oom_kill=$(awk '$1=="oom_kill"{print $2}' $CG/memory.events 2>/dev/null || echo 0)"
echo "memory.stat.anon=$(awk '$1=="anon"{print $2}' $CG/memory.stat 2>/dev/null || echo 0)"
echo "memory.stat.file=$(awk '$1=="file"{print $2}' $CG/memory.stat 2>/dev/null || echo 0)"
echo "memory.stat.kernel=$(awk '$1=="kernel"{print $2}' $CG/memory.stat 2>/dev/null || echo 0)"
echo "pids.current=$(read_or_zero $CG/pids.current)"
echo "pids.max=$(read_or_zero $CG/pids.max)"
