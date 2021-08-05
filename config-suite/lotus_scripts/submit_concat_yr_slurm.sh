#!/bin/bash
#SBATCH --array=[1800-2020]
#SBATCH -q short-serial
#SBATCH --output ./logs_concat_yr/%j_%a.out
#SBATCH --error ./logs_concat_yr/%j_%a.err
#SBATCH -t 24:00:00
#SBATCH --mem 64000

source ./setenv0.sh
if [ -f concat_yr_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'concat_yr_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/concat_annual.py -work ./out/ -year ${SLURM_ARRAY_TASK_ID}

    if [ $? -eq 0 ] 
    then
	    touch concat_yr_${SLURM_ARRAY_TASK_ID}.success
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_concat_yr/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_concat_yr/successful/"
    else
	    touch concat_yr_${SLURM_ARRAY_TASK_ID}.failed
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_concat_yr/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_concat_yr/failed/"
	fi
fi

if [ ${SLURM_ARRAY_TASK_ID} == 2020 ]
then
    sbatch --dependency=after:${SLURM_JOB_ID} submit_concat_all_slurm.sh
fi
