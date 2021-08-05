#!/bin/bash 
#SBATCH --array=2015-2020
#SBATCH --job-name=recombine_%a
#SBATCH -p short-serial-4hr
#SBATCH --output ./logs_recombine/%j_%a.out 
#SBATCH --error ./logs_recombine/%j_%a.err 
#SBATCH --mem 32000 
#SBATCH -t 03:30:00

source ./setenv0.sh
cwd=`pwd`
cd ${working_directory}/corrected_data/

for month in "01" "02" "03" "04" "05" "06" "07" "08" "09" "10" "11" "12"
do
cat ${SLURM_ARRAY_TASK_ID}-${month}-*.csv | grep -v "^YR|" | sort -t "|" -g -k 1,1 -k 2,2 -k 3,3 -k 4,4 -k 9,9 > ${SLURM_ARRAY_TASK_ID}-${month}.psv
done

cd $cwd

