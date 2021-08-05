#!/bin/bash
#BSUB -q short-serial
#BSUB -o ./logs_concat_all/%J.out
#BSUB -e ./logs_concat_all/%J.err
#BSUB -W 24:00
#BSUB -R "rusage[mem=64000]"
#BSUB -M 64000

source ./setenv0.sh
python3 ${scripts_directory}/concat_all.py -work ./out/ -index 0
