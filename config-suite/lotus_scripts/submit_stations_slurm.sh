#!/bin/bash
#SBATCH -J stations_[1-732]
#SBATCH -q short-serial
#SBATCH -o ./logs_stations/%J_%I.out
#SBATCH -e ./logs_stations/%J_%I.err
#SBATCH -W 24:00
#SBATCH -R "rusage[mem=64000]"
#SBATCH -M 64000

source ./setenv0.sh
if [ -f stations_${SLURM_ARRAY_TASK_ID}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'stations_${SLURM_ARRAY_TASK_ID}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/stations.py \
    -schema ${code_directory}/config/schemas/imma/imma.json \
    -code_tables ${code_directory}/config/schemas/imma/code_tables/ \
    -pub47file ${home_directory}/data/release_4.0/wmo_publication_47/master/master_all.csv \
    -mapping ${code_directory}/config/cdm_mapping/ \
    -index ${SLURM_ARRAY_TASK_ID} \
    -imma_source ${home_directory}/data/datasets/ICOADS_R3.0.0T_original/ \
    -cdm_source ${home_directory}/data/release_4.0/ICOADS_R3.0.0T/level2/ \
    -destination ./out/ 

    if [ $? -eq 0 ] 
    then
	    touch stations_${SLURM_ARRAY_TASK_ID}.success
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_stations/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_stations/successful/"
    else
	    touch stations_${SLURM_ARRAY_TASK_ID}.failed
        sbatch --partition=short-serial-4hr --dependency=after:${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID} --wrap="mv ./logs_stations/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.* ./logs_stations/failed/"
	fi
fi

