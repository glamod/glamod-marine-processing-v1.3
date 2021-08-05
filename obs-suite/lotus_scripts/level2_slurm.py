#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 22 09:09:41 2020

@author: iregou
"""

import sys
import os
import logging
import subprocess

import lotus_paths

# Set process params-----------------------------------------------------------
LEVEL = 'level2'
PYSCRIPT = 'level2.py'
CONFIG_FILE = 'level2.json'

QUEUE = 'short-serial-4hr'
JOB_TIME = '04:00:00'
JOB_MEMO = 500
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

# Get lotus paths
lotus_dir = lotus_paths.lotus_scripts_directory
scripts_dir = lotus_paths.scripts_directory
data_dir = lotus_paths.data_directory
scratch_dir = lotus_paths.scratch_directory

# Build process specific paths
release_tag = '-'.join([release,update])
script_config_file = os.path.join(config_path,release_tag,dataset,CONFIG_FILE)
level_dir = os.path.join(data_dir,release,dataset,LEVEL)
log_dir = os.path.join(level_dir,'log')

# Check paths
check_file_exit([script_config_file,process_list_file])
check_dir_exit([level_dir,log_dir])

# Get configuration -----------------------------------------------------------
with open(process_list_file,'r') as fO:
    process_list = fO.read().splitlines()
    
# Build jobs ------------------------------------------------------------------    
py_path = os.path.join(scripts_dir,PYSCRIPT)
pycommand='python {0} {1} {2} {3} {4} {5}'.format(py_path,data_dir,release,update,
                  dataset,script_config_file)


logging.info('SUBMITTING JOBS...')

for sid_dck in process_list:
    log_diri = os.path.join(log_dir,sid_dck)
    
    level2_job = "sbatch -J {0} -p {1} --account=short4hr".format(sid_dck,QUEUE)
    level2_job += " --output={0}/{1}.out --error={0}/{1}.out".format(log_diri,sid_dck)
    level2_job += " --open-mode=truncate --time={0} --mem={1}".format(JOB_TIME,str(JOB_MEMO))
    level2_job += " --wrap='{0} {1}'".format(pycommand,sid_dck)
    
    logging.info('{}: launching job'.format(sid_dck)) 
    process = "jid=$({} | cut -f 4 -d' ') && echo $jid".format(level2_job)
    jid = launch_process(process)

    # Rename logs and clean inputs
    clean_ok = "sbatch --dependency=afterok:{0} --kill-on-invalid-dep=yes".format(jid)
    clean_ok += " -p {0} --output=/dev/null --time=00:10:00 --mem=2 --account=short4hr".format(QUEUE)
    clean_ok += " --wrap='mv {0}/{1}.out {0}/{1}-{2}-{3}.ok'".format(log_diri,sid_dck,release,update)
    _jid = launch_process(clean_ok)

    clean_failed = "sbatch --dependency=afternotok:{0} --kill-on-invalid-dep=yes".format(jid)
    clean_failed += " -p {0} --output=/dev/null --time=00:10:00 --mem=2 --account=short4hr".format(QUEUE)
    clean_failed += " --wrap='mv {0}/{1}.out {0}/{1}-{2}-{3}.failed'".format(log_diri,sid_dck,release,update)
    _jid = launch_process(clean_failed)
