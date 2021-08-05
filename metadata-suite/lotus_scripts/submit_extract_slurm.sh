#!/bin/bash
#SBATCH --array=[661-708]
#SBATCH --job-name merge_%a
#SBATCH -p short-serial-4hr
#SBATCH --output ./extract_logs/%j_%a.out
#SBATCH --error ./extract_logs/%j_%a.err
#SBATCH -t 04:00:00
#SBATCH --mem 4000

source ./setenv0.sh
if [ -f extract_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'extract_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/extract_for_cds.py  -config ${code_directory}/config/config_lotus.json -schema\
        ${code_directory}/config/master.json -index ${SLURM_ARRAY_TASK_ID} 
    if [ $? -eq 0 ] 
    then
	    touch extract_${SLURM_ARRAY_TASK_ID}.success
        bsub -w "done(${SLURM_JOBID})" mv ./extract_logs/${SLURM_JOBID}_${SLURM_ARRAY_TASK_ID}.* ./extract_logs/successful/
        if [ -f  extract_${SLURM_ARRAY_TASK_ID}.failed ]
        then
            rm extract_${SLURM_ARRAY_TASK_ID}.failed
        fi
    else
	    touch extract_${SLURM_ARRAY_TASK_ID}.failed
#        bsub -w "done(${SLURM_JOBID})" mv ./extract_logs/${SLURM_JOBID}_${SLURM_ARRAY_TASK_ID}.* ./extract_logs/failed/
	fi
fi
