#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 17 14:24:10 2019

Script to generate the C3S CDM Marine level1d data: add external MD (pub47...):

    - Read header table and MD and see if there is anything to merge
    
    - Map MD to CDM with module cdm
    
    - Merge mapped MD with CDM tables by primary_station_id and
    save to file with function process_table()
    (if nothing to merge, just save the file to level1d...)
    
    - log, per table, total number of records and those with MD added/updated

The processing unit is the source-deck monthly set of CDM tables.

Outputs data to /<data_path>/<release>/<dataset>/level1d/<sid-dck>/table[i]-fileID.psv
Outputs quicklook info to:  /<data_path>/<release>/<dataset>/level1d/quicklooks/<sid-dck>/fileID.json
where fileID is yyyy-mm-release_tag-update_tag

Before processing starts:
    - checks the existence of all io subdirectories in level1c|d -> exits if fails
    - checks the existence of the source table to be converted (header only) -> exits if fails
    - checks the existence of the monthly MD file -> exits if fails
    - removes all level1d products on input file resulting from previous runs


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

On input data:
-------------
If the pre-processing of the MD changes, then how we map the MD in map_to_cdm()
 changes also. The mappings there as for MD pre-processing in Autumn2019

pub47 monthly files assumed to have 1 hdr line (first) with column names
pub47 monthly files with FS=';'
pub47 field names assumed: call;record;name;freq;vsslM;vssl;automation;rcnty;
                           valid_from;valid_to;uid;thmH1;platH;brmH1;
                           anmH;anHL1;wwH;sstD1;th1;hy1;st1;bm1;an1

.....

@author: iregon
"""
import sys
import os
import json
import simplejson
import datetime
import cdm
from collections import Counter
import glob
import logging
import pandas as pd
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

        # However md_subdir is then nested in monthly....and inside monthly files
        # Other MD sources would stick to this? Force it otherwise?
        process_options = ['md_model','md_subdir', 'history_explain',
                           'md_first_yr_avail', 'md_last_yr_avail',
                           'md_not_avail']
        try:            
            for opt in process_options: 
                if not config.get(self.sid_dck,{}).get(opt):
                    setattr(self, opt, config.get(opt))
                else:
                    setattr(self, opt, config.get(self.sid_dck).get(opt))
            self.flag = True
        except Exception:
            logging.error('Parsing configuration from file :{}'.format(self.configfile), exc_info=True)
            self.flag = False
            
# This is for json to handle dates
date_handler = lambda obj: (
    obj.isoformat()
    if isinstance(obj, (datetime.datetime, datetime.date))
    else None
)

def map_to_cdm(md_model,meta_df):
    # Atts is a minimum info on vars the cdm mocule requires
    atts = {k:{'column_type':'object'} for k in meta_df.columns}
    meta_cdm_dict = cdm.map_model(md_model, meta_df, atts)
    meta_cdm = pd.DataFrame()
    table = 'header'
    meta_cdm_columns = [ (table,x) for x in meta_cdm_dict[table]['data'].columns ]
    meta_cdm[meta_cdm_columns] = meta_cdm_dict[table]['data']
    for table in obs_tables:
        print(table) # dyb
        meta_cdm_columns = [ (table,x) for x in meta_cdm_dict[table]['data'].columns ]
        meta_cdm[meta_cdm_columns] = meta_cdm_dict[table]['data']
    return meta_cdm


def process_table(table_df,table_name):
    logging.info('Processing table {}'.format(table_name))
    if isinstance(table_df,str):
        # Assume 'header' and in a DF in table_df otherwise
        # Open table and reindex
        table_df = pd.DataFrame()
        table_df = cdm.read_tables(prev_level_path,fileID,cdm_subset=[table_name])
        if table_df is None or len(table_df) == 0:
            logging.warning('Empty or non existing table {}'.format(table_name))
            return
        table_df.set_index('report_id',inplace=True,drop=False)
        # by this point, header_df has its index set to report_id, hopefully ;)
        table_df['primary_station_id'] = header_df['primary_station_id'].loc[table_df.index]

    meta_dict[table_name] = {'total':len(table_df),'updated':0}
    if merge:
        meta_dict[table_name] = {'total':len(table_df),'updated':0}
        table_df.set_index('primary_station_id',drop=False,inplace=True)

        meta_table = meta_cdm[[ x for x in meta_cdm if x[0] == table_name ]]
        meta_table.columns = [ x[1] for x in meta_table ]
        if table_name != 'header':
            meta_table['primary_station_id'] = meta_cdm[('header','primary_station_id')]
        meta_table.set_index('primary_station_id',drop=False,inplace=True)
        table_df.update(meta_table)

        updated_locs =  [ x for x in table_df.index if x in meta_table.index ]
        meta_dict[table_name]['updated'] = len(updated_locs)

        if table_name == 'header':
            missing_ids = [ x for x in table_df.index if x not in meta_table.index ]
            if len(missing_ids)>0:
                meta_dict['non ' + params.md_model + ' ids'] = {k:v for k,v in Counter(missing_ids).items()}
            history_add = ';{0}. {1}'.format(history_tstmp,params.history_explain)
            locs = table_df['primary_station_id'].isin(updated_locs)
            table_df['history'].loc[locs] = table_df['history'].loc[locs] + history_add

    cdm_columns = cdm_tables.get(table_name).keys()
    odata_filename = os.path.join(level_path,FFS.join([table_name,fileID]) + '.psv')
    table_df.to_csv(odata_filename, index = False, sep = delimiter, columns = cdm_columns
                 ,header = header, mode = wmode, na_rep = 'null')

    return

def clean_level(file_id):
    level_prods = glob.glob(os.path.join(level_path,'*-' + file_id + '.psv'))
    level_logs = glob.glob(os.path.join(level_log_path, file_id + '.*'))
    level_ql = glob.glob(os.path.join(level_ql_path, file_id + '.*'))
    for filename in level_prods + level_ql + level_logs:
        try:
            logging.info('Removing previous file: {}'.format(filename))
            os.remove(filename)
        except:
            pass

# END FUNCTIONS ---------------------------------------------------------------


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
md_delimiter = '|'
level = 'level1d'
level_prev = 'level1c'
header = True
wmode = 'w'

release_path = os.path.join(params.data_path,params.release,params.dataset)
release_id = FFS.join([params.release,params.update ])
fileID = FFS.join([str(params.year),str(params.month).zfill(2),release_id ])
fileID_date = FFS.join([str(params.year),str(params.month)])

prev_level_path = os.path.join(release_path,level_prev,params.sid_dck)
level_path = os.path.join(release_path,level,params.sid_dck)
level_ql_path = os.path.join(release_path,level,'quicklooks',params.sid_dck)
level_log_path = os.path.join(release_path,level,'log',params.sid_dck)

data_paths = [prev_level_path, level_path, level_ql_path, level_log_path]
if any([ not os.path.isdir(x) for x in data_paths ]):
    logging.error('Could not find data paths: {}'.format(','.join([ x for x in data_paths if not os.path.isdir(x)])))
    sys.exit(1)

prev_level_filename = os.path.join(prev_level_path, 'header-' + fileID + '.psv')
if not os.path.isfile(prev_level_filename):
    logging.error('L1c header file not found: {}'.format(prev_level_filename))
    sys.exit(1)
    
md_avail = True if not params.md_not_avail else False

if md_avail:
    md_path = os.path.join(params.data_path,params.release,params.md_subdir,'monthly')
    logging.info('Setting MD path to {}'.format(md_path))
    metadata_filename = os.path.join(md_path, FFS.join([params.year,params.month,'01.csv']))

    if not os.path.isfile(metadata_filename):
        if int(params.year) > params.md_last_yr_avail or int(params.year) < params.md_first_yr_avail:
            md_avail = False
            logging.warning('Metadata source available only in period {0}-{1}'
                            .format(str(params.md_first_yr_avail),str(params.md_last_yr_avail)))
            logging.warning('level1d data will be created with no merging') 
        else:
            logging.error('Metadata file not found: {}'.format(metadata_filename))
            sys.exit(1)
else:
    logging.info('Metadata not available for data source-deck {}'.format(params.sid_dck))
    logging.info('level1d data will be created with no merging')
        
# Clean previous L1a products and side files ----------------------------------
clean_level(fileID)
meta_dict = {}

# DO THE DATA PROCESSING ------------------------------------------------------
# -----------------------------------------------------------------------------
history_tstmp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
cdm_tables = cdm.lib.tables.tables_hdlr.load_tables()
obs_tables = [ x for x in cdm_tables.keys() if x != 'header' ]

# 1. SEE STATION ID's FROM BOTH DATA STREAMS AND SEE IF THERE'S ANYTHING TO
# MERGE AT ALL
# Read the header table
table = 'header'
header_df = pd.DataFrame()
header_df = cdm.read_tables(prev_level_path,fileID,cdm_subset=[table],na_values='null')
if len(header_df) == 0:
    logging.error('Empty or non-existing header table')
    sys.exit(1)

# Read the metadona
if md_avail:
    meta_df = pd.DataFrame()
    meta_df = pd.read_csv(metadata_filename,delimiter = md_delimiter, dtype = 'object',
                               header = 0, na_values='MSNG')
    if len(meta_df) == 0:
        logging.error('Empty or non-existing metadata file')
        sys.exit(1)

# See if there's anything to do
header_df.set_index('primary_station_id',drop = False, inplace = True)
merge = True if md_avail else False
if md_avail:
    meta_df = meta_df.loc[meta_df['call'].isin(header_df['primary_station_id'])]
    if len(meta_df) == 0:
        logging.warning('No metadata to merge in file')
        merge = False

# 2. MAP PUB47 MD TO CDM FIELDS -----------------------------------------------
if merge:
    logging.info('Mapping metadata to CDM')
    meta_cdm = map_to_cdm(params.md_model,meta_df)

# 3. UPDATE CDM WITH PUB47 OR JUST COPY PREV LEVEL TO CURRENT -----------------
# This is only valid for the header
table =  'header'
process_table(header_df,table)

header_df.set_index('report_id',inplace=True,drop=False)
# for obs
for table in obs_tables:
    process_table(table,table)

# 4. SAVE QUICKLOOK -----------------------------------------------------------
logging.info('Saving json quicklook')
level_io_filename = os.path.join(level_ql_path,fileID + '.json')
with open(level_io_filename,'w') as fileObj:
    simplejson.dump({'-'.join([params.year,params.month]):meta_dict},fileObj,
                     default = date_handler,indent=4,ignore_nan=True)
logging.info('End')
