#!/bin/bash
# Paste on the cluster. Writes K=1..12 jobs with --cv, --ntasks-per-node=16.
# Matches grapeancestry_suite/scripts/admixture_k.sbatch: `admixture --cv -jN`
set -euo pipefail
DIR=/work/share/ac8c44ycw9/lixuzhen/array/2448_test/admix_nogwas
cd "$DIR"
mkdir -p logs/admixture_k jobs
test -s panel167k_nogwas.bed
for K in $(seq 1 12); do
  cat > "jobs/admix_k${K}.sbatch" << EOF
#!/bin/bash
#SBATCH -J admix_k${K}
#SBATCH -o logs/admixture_k/admix_k${K}.out
#SBATCH -e logs/admixture_k/admix_k${K}.err
#SBATCH --ntasks-per-node=16
set -euo pipefail
cd ${DIR}
admixture --cv -j16 panel167k_nogwas.bed ${K}
EOF
done
for K in $(seq 1 12); do
  sbatch --chdir="$DIR" --export=ALL "jobs/admix_k${K}.sbatch"
done
