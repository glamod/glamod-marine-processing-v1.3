#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 22 09:09:41 2020

@author: iregou
"""

import sys
import os
import json
import argparse
import logging
import glob
import subprocess

import lotus_paths
import config_array


# Set process params-----------------------------------------------------------
LEVEL = 'level1a'
LEVEL_SOURCE = 'level0'
SOURCE_PATTERN = '????-??.imma'
PYSCRIPT = 'level1a.py'
CONFIG_FILE = 'level1a.json'
PERIODS_FILE = 'source_deck_periods.json'
PYCLEAN = 'array_output_hdlr.py'
QUEUE = 'short-serial'
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
def check_file_exit(files):
    files = [files] if not isinstance(files,list) else files
    for filei in files:
        if not os.path.isfile(filei):
            logging.error('File {} does not exist. Exiting'.format(filei))
            sys.exit(1)
    return

def check_dir_exit(dirs):
    dirs = [dirs] if not isinstance(dirs,list) else dirs
    for diri in dirs:
        if not os.path.isdir(diri):
            logging.error('Directory {} does not exist. Exiting'.format(diri))
            sys.exit(1)
    return

def launch_process(process):

    proc = subprocess.Popen([process],shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    jid_by, err = proc.communicate()
    if len(err)>0:
        logging.error('Error launching process. Exiting')
        logging.info('Error is: {}'.format(err))
        sys.exit(1)
    jid = jid_by.decode('UTF-8').rstrip()

    return jid.split(' ')[-1]

#------------------------------------------------------------------------------


logging.basicConfig(format='%(levelname)s\t[%(asctime)s](%(filename)s)\t%(message)s',
                    level=logging.INFO,datefmt='%Y%m%d %H:%M:%S',filename=None)

# Get process coordinates and build paths -------------------------------------
release = sys.argv[1]
update = sys.argv[2]
dataset = sys.argv[3]
config_path = sys.argv[4]
process_list_file = sys.argv[5]

parser = argparse.ArgumentParser()
parser.add_argument('positional', metavar='N', type=str, nargs='+')
parser.add_argument('--failed_only')

args = parser.parse_args()
if args.failed_only:
    failed_only = True if args.failed_only== 'yes' else False
else:
    failed_only = False


# Get lotus paths
lotus_dir = lotus_paths.lotus_scripts_directory
scripts_dir = lotus_paths.scripts_directory
data_dir = lotus_paths.data_directory
scratch_dir = lotus_paths.scratch_directory

# Build process specific paths
release_tag = '-'.join([release,update])
script_config_file = os.path.join(config_path,release_tag,dataset,CONFIG_FILE)
release_periods_file = os.path.join(config_path,release_tag,dataset,PERIODS_FILE)
level_dir = os.path.join(data_dir,release,dataset,LEVEL)
level_source_dir = os.path.join(data_dir,'datasets',dataset,LEVEL_SOURCE)
log_dir = os.path.join(level_dir,'log')

# Check paths
check_file_exit([script_config_file,release_periods_file,process_list_file])
check_dir_exit([level_dir,level_source_dir,log_dir])

# Get configuration -----------------------------------------------------------
with open(script_config_file,'r') as fO:
    script_config = json.load(fO)
    
with open(process_list_file,'r') as fO:
    process_list = fO.read().splitlines()

with open(release_periods_file,'r') as fO:
    release_periods = json.load(fO)
    
# Build array input files -----------------------------------------------------
logging.info('CONFIGURING JOB ARRAYS...')


# check if SOURCE_PATTERN in config, if so overwrite SOURCE_PATTERN
if 'source_pattern' in script_config:
    SOURCE_PATTERN = script_config['source_pattern']

status = config_array.main(level_source_dir,SOURCE_PATTERN,log_dir,
                           script_config,release_periods,process_list,
                           failed_only = failed_only) 
if status != 0:
    logging.error('Creating array inputs')
    sys.exit(1)
    
# Build jobs ------------------------------------------------------------------    
py_path = os.path.join(scripts_dir,PYSCRIPT)
py_clean_path = os.path.join(lotus_dir,PYCLEAN)
pycommand='python {0} {1} {2} {3} {4}'.format(py_path,data_dir,release,update,
                  dataset)

# Set default job params
mem = script_config['job_memo_mb']
t_hh = script_config['job_time_hr']
t_mm = script_config['job_time_min']
t = ':'.join([t_hh,t_mm,'00'])

logging.info('SUBMITTING ARRAYS...')

for sid_dck in process_list:
    log_diri = os.path.join(log_dir,sid_dck)
    array_size = len(glob.glob(os.path.join(log_diri,'*.input')))
    if array_size == 0:
        logging.warning('{}: no jobs for partition'.format(sid_dck))
        continue
    
    job_file = os.path.join(log_diri,sid_dck + '.slurm')
    
    memi = script_config.get(sid_dck,{}).get('job_memo_mb')
    memi = mem if not memi else memi
    
    t_hhi = script_config.get(sid_dck,{}).get('job_time_hr')
    t_mmi = script_config.get(sid_dck,{}).get('job_time_min')
    if t_hhi and t_mmi:
        ti = ':'.join([t_hhi,t_mmi,'00'])
    else:
        ti = t
    
    with open(job_file,'w') as fh:
        fh.writelines('#!/bin/bash\n')
        fh.writelines('#SBATCH --job-name={}.job\n'.format(sid_dck))
        fh.writelines('#SBATCH --array=1-{}\n'.format(str(array_size)))
        fh.writelines('#SBATCH --partition={}\n'.format(QUEUE))
        fh.writelines('#SBATCH --output={}/%a.out\n'.format(log_diri))
        fh.writelines('#SBATCH --error={}/%a.out\n'.format(log_diri))
        fh.writelines('#SBATCH --time={}\n'.format(ti))
        fh.writelines('#SBATCH --mem={}\n'.format(memi))
        fh.writelines('#SBATCH --open-mode=truncate\n')
        fh.writelines('{0} {1}/$SLURM_ARRAY_TASK_ID.input\n'.format(pycommand,log_diri))
    
    logging.info('{}: launching array'.format(sid_dck)) 
    process = "jid=$(sbatch {} | cut -f 4 -d' ') && echo $jid".format(job_file)
    jid = launch_process(process)

    # Rename logs and clean inputs
    # First rename with aftercorr succesfull array elements: aftercorr work on an element by element basis, if exit 0
    clean_ok = "sbatch --dependency=aftercorr:{0} --kill-on-invalid-dep=yes --array=1-{1}".format(jid,str(array_size))
    clean_ok += " -p {0} --output=/dev/null --time=00:02:00 --mem=2".format(QUEUE)
    clean_ok += " --wrap='python {0} {1} {2} {3}/$SLURM_ARRAY_TASK_ID.input 0 0'".format(py_clean_path,release,update,log_diri)
    ok_jid = launch_process(clean_ok)
    # There is no aftercorr"notok", so after successfull are renamed to ok, rename the rest to *.failed
    clean_failed = "sbatch --dependency=afterany:{0} --kill-on-invalid-dep=yes --array=1-{1}".format(ok_jid,str(array_size))
    clean_failed += " -p {0} --output=/dev/null --time=00:02:00 --mem=2".format(QUEUE)
    clean_failed += " --wrap='python {0} {1} {2} {3}/$SLURM_ARRAY_TASK_ID.input 1 0'".format(py_clean_path,release,update,log_diri)
    _jid = launch_process(clean_failed) 
