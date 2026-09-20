#!/bin/bash
#SBATCH -J admix_k2_12
#SBATCH -o logs/admixture_k/%x_%A_%a.out
#SBATCH -e logs/admixture_k/%x_%A_%a.err
#SBATCH --array=2-12
#SBATCH -c 16
#SBATCH --mem=48G
#SBATCH -t 48:00:00
#
# Unsupervised ADMIXTURE K=2–12 on panel167k_nogwas.bed (chip minus GWAS).
# No --cv. One job per K. Outputs: panel167k_nogwas.{K}.Q / .{K}.P
#
# BEFORE sbatch (Slurm opens -o/-e first):
#   cd /work/share/ac8c44ycw9/lixuzhen/array/2448_test/admix_nogwas
#   mkdir -p logs/admixture_k
#   # conda env (vcf) must have `admixture` on PATH, or:
#   #   export ADMIX=/path/to/admixture
#   sbatch --chdir="$PWD" --export=ALL /path/to/admixture_k2_12.sbatch
#
# -jN has no space. `admixture -j 16 bed K` treats 16 as the input file.

set -euo pipefail

BED_DIR=${BED_DIR:-/work/share/ac8c44ycw9/lixuzhen/array/2448_test/admix_nogwas}
PREFIX=${PREFIX:-panel167k_nogwas}
K=${SLURM_ARRAY_TASK_ID:?need --array=2-12}
THREADS=${SLURM_CPUS_PER_TASK:-16}
ADMIX=${ADMIX:-admixture}

cd "${BED_DIR}"
test -s "${PREFIX}.bed"
test -s "${PREFIX}.bim"
test -s "${PREFIX}.fam"
command -v "${ADMIX}" >/dev/null

echo "host=$(hostname) k=${K} threads=${THREADS} $(date)"
which "${ADMIX}"
"${ADMIX}" -j"${THREADS}" "${PREFIX}.bed" "${K}"
echo "done k=${K} $(date)"
ls -l "${PREFIX}.${K}.Q" "${PREFIX}.${K}.P"
