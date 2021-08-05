#!/bin/bash 
# S BATCH -array=1-828
#SBATCH --array=1-72
#SBATCH --job-name preprocess-lvl4_%a
#SBATCH -p short-serial-4hr
#SBATCH --output ./logs_pp/%j_%a.out 
#SBATCH --error ./logs_pp/%j_%a.err 
#SBATCH -t 03:30:00
#SBATCH --mem 32000       

source ./setenv0.sh
if [ -f ./logs_pp/preprocess_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'preprocess_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/preprocess.py -jobs ${code_directory}/config/jobs_2015.json -job_index ${SLURM_ARRAY_TASK_ID} \
        -schema ${code_directory}/config/schemas/imma/imma.json -code_tables ${code_directory}/config/schemas/imma/code_tables/ \
        -source ${home_directory}/data/datasets/ICOADS_R3.0.1T/ORIGINAL/ -corrections ${home_directory}/data/datasets/NOC_corrections/v1x2021/ \
        -destination ${working_directory}/corrected_data/
    if [ $? -eq 0 ] 
    then
	touch ./logs_pp/preprocess_${SLURM_ARRAY_TASK_ID}.success
        if [ -f ./logs_pp/preprocess_${SLURM_ARRAY_TASK_ID}.failed ]
        then
            rm ./logs_pp/preprocess_${SLURM_ARRAY_TASK_ID}.failed
        fi
        echo "submitting clean up job: mv ./logs_pp/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_pp/successful/"
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_pp/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_pp/successful/"
    else
	touch ./logs_pp/preprocess_${SLURM_ARRAY_TASK_ID}.failed
        echo "submitting clean up job: mv ./logs_pp/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_pp/failed/"
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_pp/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_pp/failed/"
	fi
fi

