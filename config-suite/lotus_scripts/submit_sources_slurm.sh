#!/bin/bash
#SBATCH --array=[1-732]
#SBATCH -p short-serial
#SBATCH --output ./logs_sources/%j_%a.out
#SBATCH --error ./logs_sources/%j_%a.err
#SBATCH -t 24:00:00
#SBATCH --mem 64000

source ./setenv0.sh
if [ -f sources_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'sources_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/sources.py \
    -schema ${code_directory}/config/schemas/imma/imma.json \
    -code_tables ${code_directory}/config/schemas/imma/code_tables/ \
    -index ${SLURM_ARRAY_TASK_ID} \
    -imma_source ${home_directory}/data/datasets/ICOADS_R3.0.0T_original/ \
    -destination ./sources/ 

    if [ $? -eq 0 ] 
    then
	    touch sources_${SLURM_ARRAY_TASK_ID}.success
        rm sources_${SLURM_ARRAY_TASK_ID}.failed
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_sources/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_sources/successful/"
    else
	    touch sources_${SLURM_ARRAY_TASK_ID}.failed
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_sources/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_sources/failed/"
	fi
fi

if [ $SLURM_ARRAY_TASK_ID == 1 ]
then
    sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID} --wrap"cat ./sources/*.csv | grep -v 'source_id' | sort | uniq > ./sources/source.psv"
fi
