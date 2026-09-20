#!/bin/bash
#SBATCH -J admix167k
#SBATCH -o logs/admixture_k/%x_%A_%a.out
#SBATCH -e logs/admixture_k/%x_%A_%a.err
#SBATCH --array=2-7,81-83
#SBATCH -c 16
#SBATCH --mem=32G
#SBATCH -t 24:00:00
#
# Unsupervised ADMIXTURE K=2–8 on panel167k_nogwas.bed (167k minus GWAS).
# Array 2-7 = K=2..7; 81,82,83 = three K=8 seeds.
#
# BEFORE sbatch: mkdir -p logs/admixture_k
#   (Slurm opens -o/-e first; mkdir inside this script is too late.)
#
# Usage:
#   mkdir -p logs/admixture_k
#   sbatch --export=ALL,BED_PREFIX=/path/to/panel167k_nogwas \
#     grapeancestry_suite/scripts/admixture_k.sbatch
#
# Or run scripts/submit_admixture_k.sh
#
# ADMIXTURE: Alexander et al. 2009 Genome Res 19:1655 doi:10.1101/gr.094052.109
# Manual §2.3 thinning skipped (user lock); --cv required for ingest QC.

set -euo pipefail

BED_PREFIX=${BED_PREFIX:-panel167k_nogwas}
OUT_DIR=${OUT_DIR:-$(pwd)}
THREADS=${SLURM_CPUS_PER_TASK:-16}

TASK=${SLURM_ARRAY_TASK_ID:?need array task id}
SEED=""
if [[ "$TASK" -ge 2 && "$TASK" -le 7 ]]; then
  K=$TASK
  SEED=0
elif [[ "$TASK" -ge 81 && "$TASK" -le 83 ]]; then
  K=8
  SEED=$((TASK - 80))
else
  echo "unexpected array id $TASK" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
cd "${OUT_DIR}"

if [[ ! -s "${BED_PREFIX}.bed" ]]; then
  if [[ -s "${BED_PREFIX}.vcf.gz" ]]; then
    plink --vcf "${BED_PREFIX}.vcf.gz" --make-bed --out "${BED_PREFIX}" \
      --allow-extra-chr --keep-allele-order
  else
    echo "missing ${BED_PREFIX}.bed and .vcf.gz" >&2
    exit 1
  fi
fi

WORKDIR="${OUT_DIR}/work_k${K}_seed${SEED}"
mkdir -p "${WORKDIR}"
cp -f "${BED_PREFIX}.bed" "${BED_PREFIX}.bim" "${BED_PREFIX}.fam" "${WORKDIR}/"
cd "${WORKDIR}"

SEED_ARGS=()
if [[ "$K" -eq 8 ]]; then
  SEED_ARGS=(-s "$SEED")
fi

# -jN must have no space. `admixture -j 16 file K` treats 16 as the input file.
admixture --cv -j"${THREADS}" "${SEED_ARGS[@]}" "${BED_PREFIX}.bed" "$K" \
  2>&1 | tee "admixture.k${K}.seed${SEED}.log"

cp -f "${BED_PREFIX}.${K}.Q" "${OUT_DIR}/panel167k_nogwas.${K}.seed${SEED}.Q"
cp -f "${BED_PREFIX}.${K}.P" "${OUT_DIR}/panel167k_nogwas.${K}.seed${SEED}.P"
if [[ "$K" -ne 8 ]]; then
  cp -f "${BED_PREFIX}.${K}.Q" "${OUT_DIR}/panel167k_nogwas.${K}.Q"
  cp -f "${BED_PREFIX}.${K}.P" "${OUT_DIR}/panel167k_nogwas.${K}.P"
fi
cp -f "admixture.k${K}.seed${SEED}.log" "${OUT_DIR}/"

CV=$(grep -E 'CV error' "admixture.k${K}.seed${SEED}.log" | tail -n1 | awk -F: '{print $NF}' | tr -d ' ' || true)
if [[ -n "$CV" ]]; then
  printf '%s\t%s\t%s\n' "$K" "$SEED" "$CV" >> "${OUT_DIR}/cv_error.tsv"
fi
