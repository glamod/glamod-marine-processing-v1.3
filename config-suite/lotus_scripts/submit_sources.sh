#!/bin/bash
#BSUB -J sources_[1-732]
#BSUB -q short-serial
#BSUB -o ./logs_sources/%J_%I.out
#BSUB -e ./logs_sources/%J_%I.err
#BSUB -W 24:00
#BSUB -R "rusage[mem=64000]"
#BSUB -M 64000

source ./setenv0.sh
if [ -f sources_${LSB_JOBINDEX}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'sources_${LSB_JOBINDEX}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/sources.py \
    -schema ${code_directory}/config/schemas/imma/imma.json \
    -code_tables ${code_directory}/config/schemas/imma/code_tables/ \
    -index ${LSB_JOBINDEX} \
    -imma_source ${home_directory}/data/datasets/ICOADS_R3.0.0T_original/ \
    -destination ./sources/ 

    if [ $? -eq 0 ] 
    then
	    touch sources_${LSB_JOBINDEX}.success
        rm sources_${LSB_JOBINDEX}.failed
        bsub -w "done(${LSB_JOBID})" mv ./logs_sources/${LSB_JOBID}_${LSB_JOBINDEX}.* ./logs_sources/successful/
    else
	    touch sources_${LSB_JOBINDEX}.failed
        bsub -w "done(${LSB_JOBID})" mv ./logs_sources/${LSB_JOBID}_${LSB_JOBINDEX}.* ./logs_sources/failed/                
	fi
fi

if [ $LSB_JOBINDEX == 1 ]
then
    bsub -w "done(${LSB_JOBID})" cat ./sources/*.csv | grep -v 'source_id' | sort | uniq > ./sources/source.psv
fi
