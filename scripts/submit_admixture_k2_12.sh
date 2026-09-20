#!/bin/bash
# Submit K=2–12. Run this ON THE CLUSTER from the BED directory (or set BED_DIR).
set -euo pipefail
BED_DIR="${BED_DIR:-/work/share/ac8c44ycw9/lixuzhen/array/2448_test/admix_nogwas}"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/admixture_k2_12.sbatch"
mkdir -p "${BED_DIR}/logs/admixture_k"
cd "${BED_DIR}"
sbatch --chdir="${BED_DIR}" --export=ALL,BED_DIR="${BED_DIR}" "${SCRIPT}"
