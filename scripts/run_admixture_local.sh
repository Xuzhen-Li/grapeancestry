#!/bin/bash
# Local unsupervised ADMIXTURE on panel167k_nogwas.bed (chip minus GWAS).
# K=8 first, then 2–7. No --cv (Mac). Does not overwrite science_k*.Q.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIT="${FIT:-$ROOT/results/admixture_fit}"
ADMIX="${ADMIX:-$ROOT/bin/admixture}"
LOG="${FIT}/admixture_run.log"
cd "$FIT"
echo "=== local runner start $(date) pid=$$ ===" | tee -a "$LOG"
for K in 8 2 3 4 5 6 7; do
  if [[ -s "panel167k_nogwas.${K}.Q" && -s "panel167k_nogwas.${K}.P" ]]; then
    echo "=== skip K=$K (Q/P exist) $(date) ===" | tee -a "$LOG"
    continue
  fi
  echo "=== START K=$K $(date) ===" | tee -a "$LOG"
  "$ADMIX" -j6 panel167k_nogwas.bed "$K" 2>&1 | tee -a "$LOG"
  echo "=== DONE K=$K $(date) ===" | tee -a "$LOG"
done
echo "=== all K finished $(date) ===" | tee -a "$LOG"
