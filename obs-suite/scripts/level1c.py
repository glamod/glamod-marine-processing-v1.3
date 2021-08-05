#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 17 14:24:10 2019

Script to generate the C3S CDM Marine level1c data: validate 
header.report_timestamp and header.primary_station_id and apply outcome to rest
of tables, rejecting reports not validating any of these two fields.
    
    - Read header data
    
    - Initialized mask for id and datetime to True
    
    - Validate header.report_timestamp (see Notes below)
    - Validate header.primary_station_id (see Notes below)
    
    - Output all reports not validating timestamp to:
        -> /level1c/invalid/sid-dck/header-fileID-report_timsetamp.psv
    - Output all reports not validating primary_station_id to:
        -> /level1c/invalid/sid-dck/header-fileID-primary_station_id.psv
    
    - Merge report_timestamp and primary_station_id in a single validation rule
    (fail if any fails)
    - Drop corresponding records from all tables
    
    - Log to json dropped per table per validated field and final numer of 
    records in the resulting tables
    - Log to json unique primary_station_id counts
    - Log to json primary_station_id validation rules numbers:
        1. callsings
        2. rest
        3. restored because output from Liz's process

The processing unit is the source-deck monthly set of CDM tables.

On reading the table files from the source level (1b), it read:
    1. master table file (table-yyyy-mm-release-update.psv)
    2. datetime leak files (table-yyyy-mm-release-update-YYYY-MM.psv), where 
    YYYY-MM indicates the initial yyyy-mm stamp of the reports contained in that
    leak file upon arrival to level1b. 

Outputs data to /<data_path>/<release>/<dataset>/level1c/<sid-dck>/table[i]-fileID.psv
Outputs invalid data to /<data_path>/<release>/<dataset>/level1c/invalid/<sid-dck>/header-fileID-<element>.psv
Outputs quicklook info to:  /<data_path>/<release>/<dataset>/level1c/quicklooks/<sid-dck>/fileID.json

where fileID is yyyy-mm-release-update

Before processing starts:
    - checks the existence of all io subdirectories in level1b|c -> exits if fails
    - checks the existence of the source table to be converted (header only) -> exits if fails
    - removes all level1c products on input file resulting from previous runs

Inargs:
------
data_path: marine data path in file system
release: release tag
update: udpate tag
dataset: dataset tag
config_path: configuration file path
sid_dck: source-deck data partition (optional, from config_file otherwise)
year: data file year (yyyy) (optional, from config_file otherwise)
month: data file month (mm) (optional, from config_file otherwise)

Notes on validations:
--------------------
** HEADER.REPORT_TIMESTAMP VALIDATION **
This validation is just trying to convert to a datetime object the content of
the field. Where empty, this conversion (and validation) will fail. 
And will be empty if during the mapping in level1a the report_timestamp could 
not be built from the source data, or if there was any kind of messing in level1b
datetime corrections......


** HEADER.PRIMARY_STATION_ID VALIDATION **
Due to various reasons, the validation is done in 3 stages and using different methods:
    1. Callsign IDs: use set of validation patterns harcoded here
    2. Rest of IDs: use set of valid patterns per dck in NOC_ANC_INFO json files
    3. All: set all that Liz's ID linkage modified to True. We are parsing the
    history field for a "Corrected primary_station_id" text...maybe it should 
    read this from the level1b config file? But then we need to give this
    file as an argument....

Dev notes:
----------

1) This script is fully tailored to the idea of how validation and cleaning should
be at the time of developing it. It is not parameterized and is hardly flexible.

2) Why don't we just pick the NaN dates as invalid, instead of looking where conversion
fails?


.....

@author: iregon
"""
import sys
import os
import simplejson
import json
import datetime
import cdm
import numpy as np
import glob
import logging
import pandas as pd
import re
from imp import reload
reload(logging)  # This is to override potential previous config of logging

# FUNCTIONS -------------------------------------------------------------------
class script_setup:
    def __init__(self, inargs):
        self.data_path = inargs[1]
        self.release = inargs[2]
        self.update = inargs[3]
        self.dataset = inargs[4]
        self.configfile = inargs[5]
        
        try:
            with open(self.configfile) as fileObj:
                config = json.load(fileObj)
        except:
            logging.error('Opening configuration file :{}'.format(self.configfile), exc_info=True)
            self.flag = False 
            return
        
        if len(sys.argv) > 6:
            self.sid_dck = inargs[6]
            self.year = inargs[7]
            self.month = inargs[8]    
        else:
            try:
                self.sid_dck = config.get('sid_dck')
                self.year = config.get('yyyy')
                self.month = config.get('mm') 
            except Exception:
                logging.error('Parsing configuration from file :{}'.format(self.configfile), exc_info=True)
                self.flag = False
                
        self.dck = self.sid_dck.split("-")[1]
        self.flag = True


# This is for json to handle dates
date_handler = lambda obj: (
    obj.isoformat()
    if isinstance(obj, (datetime.datetime, datetime.date))
    else None
)

def validate_id(idSeries):
    json_file = os.path.join(id_validation_path,'dck' + params.dck + '.json')
    if not os.path.isfile(json_file):
        logging.warning('NO noc ancillary info file {} available'.format(json_file))
        logging.warning('Adding match-all regex to validation patterns')
        patterns = ['.*?']
    else:
        logging.info('Reading ID validation patterns from NOC ANC FILE {}'.format(json_file))    
        try:
            with open(json_file) as fO:
                jDict = json.load(fO)
                
            valid_patterns = jDict.get('patterns')
            patterns = list(valid_patterns.values()) 
        except:
            logging.error('Error reading NOC ANC FILE {}'.format(json_file),exc_info = True)
            sys.exit(1)

    # At some point we might expect acceptance of no IDs as valid to be
    # configurable...    
    patterns.append('^$')
    logging.warning('NaN values will validate to True')

    na_values = True if '^$' in patterns else False
    combined_compiled = re.compile('|'.join(patterns))

    return idSeries.str.match(combined_compiled,na = na_values)

def read_table_files(table):
    logging.info('Reading data from {} table files'.format(table))
    table_df = pd.DataFrame()

    # First read the master file, if any, then append leaks
    # If no yyyy-mm master file, can still have reports from datetime leaks
    # On reading 'header' read null as NaN so that we can validate null ids as NaN easily
    table_df = cdm.read_tables(prev_level_path,fileID,cdm_subset=[table],na_values='null')
    try:
    	len(table_df)
    except:
        logging.warning('Empty or non-existing master {} table. Attempting \
                        to read datetime leak files'.format(table))
    leak_pattern = FFS.join([table,fileID,'????' + FFS + '??.psv'])
    leak_files = glob.glob(os.path.join(prev_level_path,leak_pattern))
    leaks_in = 0
    if len(leak_files)>0:
        for leak_file in leak_files:
            logging.info('Reading datetime leak file {}'.format(leak_file))
            file_base = os.path.splitext(os.path.basename(leak_file))[0]
            fileIDi = '-'.join(file_base.split('-')[-6:])
            table_dfi = cdm.read_tables(prev_level_path,fileIDi,cdm_subset=[table],na_values='null')
            if len(table_dfi) == 0:
                logging.error('Could not read leak file or is empty {}'.format(leak_file)) 
                sys.exit(1)
            leaks_in += len(table_dfi)
            table_df = pd.concat([table_df ,table_dfi],axis=0,sort=False)
    if len(table_df) > 0:
        validation_dict[table] = {'leaks_in':leaks_in}        
    return table_df
  
def process_table(table_df,table_name):
    if isinstance(table_df,str):
        # Open table and reindex
        table_df = read_table_files(table_name)
        if table_df is None or len(table_df) == 0:
            logging.warning('Empty or non existing table {}'.format(table_name))
            return
        table_df.set_index('report_id', inplace = True, drop = False)
     
    odata_filename = os.path.join(level_path,FFS.join([table_name,fileID]) + '.psv')
    cdm_columns = cdm_tables.get(table_name).keys()
    table_mask = mask_df.loc[table_df.index]
    if table_name == 'header':
            table_df['history'] = table_df['history'] + ';{0}. {1}'.format(history_tstmp,history)
            validation_dict['unique_ids'] = table_df.loc[table_mask['all'],'primary_station_id'].value_counts(dropna=False).to_dict()
    
    if len(table_df[table_mask['all']]) > 0:
        table_df[table_mask['all']].to_csv(odata_filename, index = False, sep = delimiter, columns = cdm_columns
                     ,header = header, mode = wmode, na_rep = 'null')
    else:
        logging.warning('Table {} is empty. No file will be produced'.format(table_name))
     
    validation_dict[table_name]['total'] = len(table_df[table_mask['all']])
    return

def clean_level(file_id):
    level_prods = glob.glob(os.path.join(level_path,'*' + FFS + file_id + '.psv'))
    level_ql = glob.glob(os.path.join(level_ql_path, file_id + '.json'))
    level_invalid = glob.glob(os.path.join(level_invalid_path,'*' + FFS + file_id + '.*'))
    for filename in level_prods + level_ql + level_invalid:
        try:
            logging.info('Removing previous file: {}'.format(filename))
            os.remove(filename)
        except:
            pass

# MAIN ------------------------------------------------------------------------

# Process input and set up some things and make sure we can do something-------
logging.basicConfig(format='%(levelname)s\t[%(asctime)s](%(filename)s)\t%(message)s',
                    level=logging.INFO,datefmt='%Y%m%d %H:%M:%S',filename=None)
if len(sys.argv)>1:
    logging.info('Reading command line arguments')
    args = sys.argv
else:
    logging.error('Need arguments to run!')
    sys.exit(1)

params = script_setup(args)

FFS = '-'
delimiter = '|'
level = 'level1c'
level_prev = 'level1b'
header = True 
wmode = 'w'
    
release_path = os.path.join(params.data_path,params.release,params.dataset)
release_id = FFS.join([params.release,params.update ]) 
fileID = FFS.join([str(params.year),str(params.month).zfill(2),release_id ])
fileID_date = FFS.join([str(params.year),str(params.month)])

prev_level_path = os.path.join(release_path,level_prev,params.sid_dck)  
level_path = os.path.join(release_path,level,params.sid_dck)
level_ql_path = os.path.join(release_path,level,'quicklooks',params.sid_dck)
level_invalid_path = os.path.join(release_path,level,'invalid',params.sid_dck)

id_validation_path = os.path.join(params.data_path,'datasets',params.dataset,'NOC_ANC_INFO','json_files')

data_paths = [prev_level_path, level_path, level_ql_path, level_invalid_path, id_validation_path]
if any([ not os.path.isdir(x) for x in data_paths ]):
    logging.error('Could not find data paths: {}'.format(','.join([ x for x in data_paths if not os.path.isdir(x)])))
    sys.exit(1)


prev_level_filename = os.path.join(prev_level_path, 'header-*' + '-'.join([str(params.year),str(params.month)]) + '*.psv')
if len(glob.glob(prev_level_filename)) == 0:
    logging.error('L1b header files not found: {}'.format(prev_level_filename))
    sys.exit(1)
 
# Clean previous L1c products and side files ----------------------------------
clean_level(fileID)
validation_dict = { table:{} for table in cdm.properties.cdm_tables}

# DO THE DATA PROCESSING ------------------------------------------------------

# -----------------------------------------------------------------------------
# Settings in configuration file
dataset_id = 'icoads_r3000'
validated = ['report_timestamp','primary_station_id']
history = 'Performed report_timestamp (date_time) and primary_station_id validation'
history_tstmp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
cdm_tables = cdm.lib.tables.tables_hdlr.load_tables()

# 1. READ THE DATA-------------------------------------------------------------

# Read the header table file(s) and init the mask to True
# Table files can be multiple for a yyyy-mm if datetime corrections
# in level1b resulted in a change in the month
table = 'header'
table_df = read_table_files(table)

if len(table_df) == 0:
    logging.error('No data could be read for file partition {}'.format(fileID))
    sys.exit(1)
            
table_df.set_index('report_id', inplace = True, drop = False)

# Initialize mask
mask_df = pd.DataFrame(index = table_df.index,columns = validated + ['all'])
mask_df[validated] = True

# 2. VALIDATE THE FIELDS-------------------------------------------------------
# 2.1. Validate datetime
field = 'report_timestamp'
mask_df[field] = pd.to_datetime(table_df[field],errors='coerce').notna()

# 2.2. Validate primary_station_id
field = 'primary_station_id'
validation_dict['id_validation_rules'] = {}

# First get callsigns:
logging.info('Applying callsign id validation')
callsigns = table_df['primary_station_id_scheme'].isin(['5']) & table_df['platform_type'].isin(['2','33'])
nocallsigns = ~callsigns
relist = ['^([0-9]{1}[A-Z]{1}|^[A-Z]{1}[0-9]{1}|^[A-Z]{2})[A-Z0-9]{1,}$','^[0-9]{5}$']
callre = re.compile('|'.join(relist))
mask_df.loc[callsigns,field] = table_df.loc[callsigns,field].str.match(callre,na = True)

# Then the rest according to general validation rules
logging.info('Applying general id validation')
mask_df.loc[nocallsigns,field]  = validate_id(table_df.loc[nocallsigns,field]) 

# And now set back to True all that the linkage provided
# Instead, read in the header history field and check if it contains
# 'Corrected primary_station_id'
logging.info('Restoring linked IDs')
linked_history = 'Corrected primary_station_id'
linked_IDs = table_df['history'].str.contains(linked_history) & \
    table_df['history'].str.contains('ID identification').notna()

linked_IDs_no = (linked_IDs).sum()

if linked_IDs_no > 0:
    mask_df.loc[linked_IDs,field] = True
    validation_dict['id_validation_rules']['idcorrected'] = linked_IDs_no

validation_dict['id_validation_rules']['callsign'] = len(np.where(callsigns)[0])
validation_dict['id_validation_rules']['noncallsign'] = len(np.where(~callsigns)[0])

# 3. OUTPUT INVALID REPORTS - HEADER ------------------------------------------
cdm_columns = cdm_tables.get(table).keys()
for field in validated:
    if False in mask_df[field].value_counts().index:
        idata_filename = os.path.join(level_invalid_path,FFS.join(['header',fileID,field]) + '.psv')
        table_df[~mask_df[field]].to_csv(idata_filename, index = False, sep = delimiter, columns = cdm_columns
                 ,header = header, mode = wmode, na_rep = 'null')


# 4. REPORT INVALIDS PER FIELD  -----------------------------------------------    
# Now clean, keep only all valid:
mask_df['all'] = mask_df.all(axis=1) 

# Report invalids
validation_dict['invalid'] = {} 
validation_dict['invalid']['total'] = len(table_df[~mask_df['all']])
for field in validated:
    validation_dict['invalid'][field] = len(mask_df[field].loc[~mask_df[field]])

# 5. CLEAN AND OUTPUT TABLES  -------------------------------------------------
# Now process tables and log final numbers and some specifics in header table
# First header table, already open
logging.info('Cleaning table header') 
process_table(table_df,table)
obs_tables = [ x for x in cdm_tables.keys() if x != 'header' ]
for table in obs_tables:
    table_pattern = FFS.join([table,fileID]) + '*.psv'
    table_files = glob.glob(os.path.join(prev_level_path,table_pattern))
    if len(table_files) > 0:
        logging.info('Cleaning table {}'.format(table))   
        process_table(table,table)
    
logging.info('Saving json quicklook')
L1b_io_filename = os.path.join(level_ql_path,fileID + '.json')
with open(L1b_io_filename,'w') as fileObj:
    simplejson.dump({'-'.join([params.year,params.month]):validation_dict},fileObj,
                     default = date_handler,indent=4,ignore_nan=True)
logging.info('End')
