#!/bin/bash
#SBATCH --array=1-396
#SBATCH --job-name lvl1f_%a
#SBATCH -p short-serial
#SBATCH --output ./logs_merge_lvl1e/%j_%a.out 
#SBATCH --error ./logs_merge_lvl1e/%j_%a.err 
#SBATCH -t 24:00:00
#SBATCH --mem 64000 

touch merge_lvl1e_${SLURM_TASK_ARRAY_ID}.fail
source ./setenv0.sh
python3 ${scripts_directory}/merge_level1e.py  -index ${SLURM_TASK_ARRAY_ID} \
  -source ${home_directory}/data/release_4.0/ICOADS_R3.0.0T/metoffice_qc/dbuoy_track/merged/ \
  -cdmpath ${home_directory}/data/release_4.0/ICOADS_R3.0.0T/

if [ $? -eq 0 ]
then
  rm merge_lvl1e_${SLURM_TASK_ARRAY_ID}.fail
  touch merge_lvl1e_${SLURM_TASK_ARRAY_ID}.success
fi
