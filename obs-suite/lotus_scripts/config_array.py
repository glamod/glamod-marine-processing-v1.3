# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
import sys
import os
import logging
import glob
import json
import re

DATE_REGEX="([1-2]{1}[0-9]{3}\-(0[1-9]{1}|1[1-2]{1}))"

# FUNCTIONS -------------------------------------------------------------------
def config_element(sid_dck_log_dir,ai,script_config,sid_dck,yyyy,mm):
    script_config.update({'sid_dck':sid_dck})
    script_config.update({'year':int(yyyy)})
    script_config.update({'month':int(mm)})
    ai_config_file = os.path.join(sid_dck_log_dir,str(ai) + '.input')
    with open(ai_config_file,'w') as fO:
        json.dump(script_config,fO,indent = 4)
    return

def get_yyyymm(filename):
    yyyy_mm = re.search(DATE_REGEX,os.path.basename(filename))
    return yyyy_mm.split('-')
# -----------------------------------------------------------------------------


def main(source_dir,source_pattern,log_dir,script_config,process_list,failed_only = False): 
    logging.basicConfig(format='%(levelname)s\t[%(asctime)s](%(filename)s)\t%(message)s',
                    level=logging.INFO,datefmt='%Y%m%d %H:%M:%S',filename=None)
    if failed_only:
        logging.info('Configuration using failed only mode')
    
    for sid_dck in process_list: 
        
        sid_dck_log_dir = os.path.join(log_dir,sid_dck)
        job_file = glob.glob(os.path.join(sid_dck_log_dir,sid_dck + '.slurm'))
        if os.path.isfile(job_file):
            os.remove(job_file)
            
        logging.info('Configuring data partition: {}'.format(sid_dck))
        ai = 1
        if not os.path.isdir(sid_dck_log_dir):
            logging.error('Data partition log diretory does not exist: {}'.format(sid_dck_log_dir))
            sys.exit(1)
        
        # Make sure there are not previous input files
        i_files = glob.glob(os.path.join(sid_dck_log_dir,'*.input'))
        for i_file in i_files:
            os.remove(i_file)
    
        ok_files = glob.glob(os.path.join(sid_dck_log_dir,'*.ok'))
        failed_files = glob.glob(os.path.join(sid_dck_log_dir,'*.failed'))
        source_files = glob.glob(os.path.join(source_dir,sid_dck,source_pattern))
        if failed_only:
            if len(failed_files) > 0:
                logging.info('{0}: found {1} failed jobs'.format(sid_dck,str(len(failed_files))))
                for failed_file in failed_files:
                    yyyy,mm = get_yyyymm(failed_file)
                    config_element(sid_dck_log_dir,ai,script_config,sid_dck,yyyy,mm)
                    ai += 1
            else:
                logging.info('{}: no failed files'.format(sid_dck))
        else:
            # Clean previous ok logs
            if len(ok_files) > 0:
                for x in ok_files:
                    os.remove(x)              
            for source_file in source_files:
                yyyy,mm = get_yyyymm(source_file)
                config_element(sid_dck_log_dir,ai,script_config,sid_dck,yyyy,mm)
                ai +=1
            logging.info('{0}: {1} elements configured'.format(sid_dck,str(ai)))
                
        if len(failed_files) > 0:
            for x in failed_files:
                os.remove(x)    
                
    return 0

if __name__ == "__main__":
    main()