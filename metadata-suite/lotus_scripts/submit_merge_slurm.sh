#!/bin/bash
#SBATCH --array=1-64
#SBATCH --job-name merge_%a
#SBATCH -p short-serial-4hr
#SBATCH --output ./merge_logs/%j_%a.out
#SBATCH --error ./merge_logs/%j_%a.err
#SBATCH -t 4:00:00
#SBATCH --mem=4000

source ./setenv0.sh
if [ -f merge_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'merge_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/merge_countries.py -config ${code_directory}/config/config_lotus.json \
        -jobs ${code_directory}/config/jobs.json -countries ${code_directory}/config/countries.json -index ${SLURM_ARRAY_TASK_ID} 
    if [ $? -eq 0 ] 
    then
	    touch merge_${SLURM_ARRAY_TASK_ID}.success
        bsub -w "done(${SLURM_JOBID})" mv ./merge_logs/${SLURM_JOBID}_${SLURM_ARRAY_TASK_ID}.* ./merge_logs/successful/
        if [ -f  merge_${SLURM_ARRAY_TASK_ID}.failed ]
        then
            rm merge_${SLURM_ARRAY_TASK_ID}.failed
        fi
    else
	    touch merge_${SLURM_ARRAY_TASK_ID}.failed
        bsub -w "done(${SLURM_JOBID})" mv ./merge_logs/${SLURM_JOBID}_${SLURM_ARRAY_TASK_ID}.* ./merge_logs/failed/
	fi
fi

if [ ${SLURM_ARRAY_TASK_ID} == 1 ]
then
sbatch --dependency=afterok:${SLURM_JOBID} python3 ${scripts_directory}/combine_master_files.py -config ${code_directory}/config/config_lotus.json \
    -countries ${code_directory}/config/countries.json
fi
