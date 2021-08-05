#!/bin/bash
#SBATCH --job-name=split_%a
#SBATCH --array=1-83
#SBATCH -p short-serial-4hr
#SBATCH --output=./logs/%j_%a.out
#SBATCH --error=./logs/%j_%a.err
#SBATCH -t 4:00:00
#SBATCH --mem=4000

source ./setenv0.sh
if [ -f split_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'split_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/split_pub47.py -config ${code_directory}/config/config_lotus.json \
        -jobs ${code_directory}/config/jobs.json -start ${SLURM_ARRAY_TASK_ID} -tag split_${SLURM_ARRAY_TASK_ID} \
        -log ./logs2/
    if [ $? -eq 0 ] 
    then
	    touch split_${SLURM_ARRAY_TASK_ID}.success
    #    SBATCH -w "done(${SLURM_JOBID})" mv ./logs/${SLURM_JOBID}_${SLURM_ARRAY_TASK_ID}.* ./logs/successful/
    else
	    touch split_${SLURM_ARRAY_TASK_ID}.failed
     #   SBATCH -w "done(${SLURM_JOBID})" mv ./logs/${SLURM_JOBID}_${SLURM_ARRAY_TASK_ID}.* ./logs/failed/                
	fi
fi

