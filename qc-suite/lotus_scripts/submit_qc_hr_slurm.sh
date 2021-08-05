#!/bin/bash 
#SBATCH --array=1-72
#SBATCH --job-name moqchr_%a
#SBATCH -p short-serial
#SBATCH --output ./logs_qc_hr/%j_%a.out 
#SBATCH --error ./logs_qc_hr/%j_%a.err 
#SBATCH -t 24:00:00
#SBATCH --mem 64000

source ./setenv0.sh
if [ -f ./logs_qc_hr/qc_hr_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'qc_hr_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/marine_qc_hires.py -jobs ${code_directory}/config/jobs.json -job_index ${SLURM_ARRAY_TASK_ID} \
        -config ${code_directory}/config/configuration.txt -tracking
    if [ $? -eq 0 ] 
    then
	    touch ./logs_qc_hr/qc_hr_${SLURM_ARRAY_TASK_ID}.success
        if [ -f ./logs_qc_hr/qc_hr_${SLURM_ARRAY_TASK_ID}.failed ]
        then
            rm ./logs_qc_hr/qc_hr_${SLURM_ARRAY_TASK_ID}.failed
        fi
        echo "submitting clean up job: mv ./logs_qc_hr/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc_hr/successful/"
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_qc_hr/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc_hr/successful/"
    else
	    touch ./logs_qc_hr/qc_hr_${SLURM_ARRAY_TASK_ID}.failed
        echo "submitting clean up job: mv ./logs_qc_hr/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc_hr/failed/"
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_qc_hr/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_qc_hr/failed/"
	fi
fi
