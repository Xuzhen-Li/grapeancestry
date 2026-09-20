#!/bin/bash
# Generate 11 independent Slurm jobs (K=2..12) and submit them all.
# Paste this whole file on the cluster. Does not run ADMIXTURE in a loop.
set -euo pipefail
DIR=/work/share/ac8c44ycw9/lixuzhen/array/2448_test/admix_nogwas
cd "$DIR"
mkdir -p logs/admixture_k jobs
test -s panel167k_nogwas.bed

write_one() {
  local K=$1
  cat > "jobs/admix_k${K}.sbatch" << EOF
#!/bin/bash
#SBATCH -J admix_k${K}
#SBATCH -o logs/admixture_k/admix_k${K}_%j.out
#SBATCH -e logs/admixture_k/admix_k${K}_%j.err
#SBATCH -c 16
#SBATCH --mem=48G
#SBATCH -t 48:00:00
set -euo pipefail
cd ${DIR}
admixture -j16 panel167k_nogwas.bed ${K}
EOF
}

write_one 2
write_one 3
write_one 4
write_one 5
write_one 6
write_one 7
write_one 8
write_one 9
write_one 10
write_one 11
write_one 12

sbatch --chdir="$DIR" --export=ALL jobs/admix_k2.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k3.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k4.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k5.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k6.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k7.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k8.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k9.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k10.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k11.sbatch
sbatch --chdir="$DIR" --export=ALL jobs/admix_k12.sbatch
