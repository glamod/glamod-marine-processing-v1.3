#!/bin/bash
#BSUB -J stations_[1-732]
#BSUB -q short-serial
#BSUB -o ./logs_stations/%J_%I.out
#BSUB -e ./logs_stations/%J_%I.err
#BSUB -W 24:00
#BSUB -R "rusage[mem=64000]"
#BSUB -M 64000

source ./setenv0.sh
if [ -f stations_${LSB_JOBINDEX}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'stations_${LSB_JOBINDEX}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/stations.py \
    -schema ${code_directory}/config/schemas/imma/imma.json \
    -code_tables ${code_directory}/config/schemas/imma/code_tables/ \
    -pub47file ${home_directory}/data/r092019/wmo_publication_47/master/master_all.csv \
    -mapping ${code_directory}/config/cdm_mapping/ \
    -index ${LSB_JOBINDEX} \
    -imma_source ${home_directory}/data/datasets/ICOADS_R3.0.0T_original/ \
    -cdm_source ${home_directory}/data/r092019/ICOADS_R3.0.0T/level2/ \
    -destination ./out/ 

    if [ $? -eq 0 ] 
    then
	    touch stations_${LSB_JOBINDEX}.success
        bsub -w "done(${LSB_JOBID})" mv ./logs_stations/${LSB_JOBID}_${LSB_JOBINDEX}.* ./logs_stations/successful/
    else
	    touch stations_${LSB_JOBINDEX}.failed
        bsub -w "done(${LSB_JOBID})" mv ./logs_stations/${LSB_JOBID}_${LSB_JOBINDEX}.* ./logs_stations/failed/                
	fi
fi

