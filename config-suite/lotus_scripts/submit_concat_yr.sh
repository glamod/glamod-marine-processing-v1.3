#!/bin/bash
#BSUB -J concat_yr_[1950-2010]
# B S U B -J concat_yr_[1966]
#BSUB -q short-serial
#BSUB -o ./logs_concat_yr/%J_%I.out
#BSUB -e ./logs_concat_yr/%J_%I.err
#BSUB -W 24:00
#BSUB -R "rusage[mem=64000]"
#BSUB -M 64000

source ./setenv0.sh
if [ -f concat_yr_${LSB_JOBINDEX}.success ]
then
    echo ""
    echo "Job previously successful, job not rerun. Remove file 'concat_yr_${LSB_JOBINDEX}.success' to force rerun."
    echo ""
else
    python3 ${scripts_directory}/concat_annual.py -work ./out/ -year ${LSB_JOBINDEX}

    if [ $? -eq 0 ] 
    then
	    touch concat_yr_${LSB_JOBINDEX}.success
        bsub -w "done(${LSB_JOBID})" mv ./logs_concat_yr/${LSB_JOBID}_${LSB_JOBINDEX}.* ./logs_concat_yr/successful/
    else
	    touch concat_yr_${LSB_JOBINDEX}.failed
        bsub -w "done(${LSB_JOBID})" mv ./logs_concat_yr/${LSB_JOBID}_${LSB_JOBINDEX}.* ./logs_concat_yr/failed/                
	fi
fi

if [ ${LSB_JOBINDEX} == 1950 ]
then
    #bsub -w "done(${LSB_JOBID})" python3 ${scripts_directory}/concat_all.py -work ./out/ -index 0
    bsub -w "done(${LSB_JOBID})" < submit_concat_all.sh
fi
