#!/bin/bash
#SBATCH -p short-serial
#SBATCH --output ./logs_concat_all/%J.out
#SBATCH --error ./logs_concat_all/%J.err
#SBATCH -t 24:00:00
#SBATCH --mem 64000

source ./setenv0.sh
python3 ${scripts_directory}/concat_all.py -work ./out/ -index 0
