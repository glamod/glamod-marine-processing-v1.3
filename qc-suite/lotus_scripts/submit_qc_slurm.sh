#!/bin/bash 
#SBATCH --array=1-72
#SBATCH --job-name moqc_%a
#SBATCH -p short-serial
#SBATCH --output ./logs_qc/%j_%a.out 
#SBATCH --error ./logs_qc/%j_%a.err 
#SBATCH -t 12:00:00
#SBATCH --mem 64000       

source ./setenv0.sh

if [ -f ./logs_qc/qc_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'qc_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/marine_qc.py -jobs ${code_directory}/config/jobs_2015.json -job_index ${SLURM_ARRAY_TASK_ID} \
        -config ${code_directory}/config/configuration.txt -tracking
    if [ $? -eq 0 ] 
    then
	touch ./logs_qc/qc_${SLURM_ARRAY_TASK_ID}.success
        if [ -f ./logs_qc/qc_${SLURM_ARRAY_TASK_ID}.failed ]
        then
            rm ./logs_qc/qc_${SLURM_ARRAY_TASK_ID}.failed
        fi
        echo "submitting clean up job: mv ./logs_qc/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc/successful/"
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_qc/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc/successful/"
    else
	touch ./logs_qc/qc_${SLURM_ARRAY_TASK_ID}.failed
        echo "submitting clean up job: mv ./logs_qc/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc/failed/"
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_qc/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc/failed/"
	fi
fi