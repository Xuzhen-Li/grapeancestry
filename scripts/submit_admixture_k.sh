#!/bin/bash
# Create Slurm log dirs THEN submit admixture_k.sbatch.
# Parent of #SBATCH -o/-e must exist before sbatch (Slurm opens logs first).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BED_PREFIX="${BED_PREFIX:-$ROOT/data/panel/admixture/bed/panel167k_nogwas}"
OUT_DIR="${OUT_DIR:-$ROOT/data/panel/admixture/bed}"
LOGDIR="${LOGDIR:-$ROOT/logs/admixture_k}"
mkdir -p "$LOGDIR" "$OUT_DIR"
cd "$ROOT"
sbatch --chdir="$ROOT" \
  --export=ALL,BED_PREFIX="$BED_PREFIX",OUT_DIR="$OUT_DIR" \
  "$ROOT/scripts/admixture_k.sbatch"
