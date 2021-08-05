#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 17 14:24:10 2019

See IMPORTANT NOTE!

Script to generate level1e CDM data: adding MO-QC (a.k.a. John's QC) flags

    - Reads QC files and creates unique flag per QC file (observed parameter)
    using columns from each QC file as parameterized at the very beginning.
    This is done with function get_qc_flags()
    See notes below on how QC files are expected to be
    
    - Creates the report_quality CDM field with function add_report_quality()
    See below notes on the rules to create it
    
    - Merge quality flags with CDM tables with function process_table()
    Here, additionally,  we set 'report_time_quality' to '2' to all reports
    
    - Log, per table, total number of records and qc flag counts

Note again that the following flagging is decided/set here, does not come from QC files:
    
    1) header.report_time_quality = '2', as by the time a report gets here we know
    that it is at least a valid datetime 
    2) header.report_quality = following the rules in the notes below

Note also that if a report is not qced (not in QC files, like worst duplicates) we override the default
settings in the initial mappings (not all not-checked...) to not-checked with:
            observations*.quality_flag = '2'
            header.'report_time_quality' = '2'
            header.'report_quality' = '2'
            header.'location_quality' = '3'

The processing unit is the source-deck monthly set of CDM tables.

Outputs data to /<data_path>/<release>/<source>/level1e/<sid-dck>/table[i]-fileID.psv
Outputs quicklook info to:  /<data_path>/<release>/<source>/level1c/quicklooks/<sid-dck>/fileID.json

where fileID is yyyy-mm-release_tag-update_tag

Before processing starts:
    - checks the existence of all io subdirectories in level1d|e -> exits if fails
    - checks availability of the source header table -> exits if fails
    - checks existence of source observation tables -> exits if no obs tables -> requirement removed to
    give way to sid-dck monthly partitions with no obs tables
    - checks of existence of the monthly QC (POS) file -> exits if fails. See IMPORTANT NOTE!!!!
    - removes all level1e products on input file resulting from previous runs

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


On expected format and content of QC files:
------------------------------------------

- qc monthly files in <data_path/<release>/<source>/metoffice_qc/base/<yyyy>/<mm>/<id>_qc_yyyymm_CCIrun.csv
with id in [POS,SST,AT,SLP,DPT,W]
- qc monthly files assumed to have 1 hdr line (first) with column names
- qc monthly files with FS=','
- qc field names assumed as those listed in qc_columns below

Note that all the qc files have an entry per qced** report in its header table,
even if the corresponfing observed parameter does not have an entry in that report,
in which case has the 'noval' flag set to '1'

WE ASSUME HERE THAT ALL MEASURED PARAMETERS HAVE A NOVAL FLAG THAT WE USE TO
TELL APART MISSING AND FAILED 

** per qced report, but duplicates are not qced....vaya caña!

Note also that since the qc files have a UID that is the imma UID, not the CDM
report_id, with the source preprended (ICOADS-30-UID for source ICOADS_R3.0.0),
and I still don't have the rules to build the CDM report_id from the source (any)
UID:
    THE WAY QC-FILES UID AND CDM-TABLES REPORT_ID ARE LINKED HERE IS HARDCODED
    IN FUNCTION get_qc_flags() TO RELEASE1 SOURCE ICOADS_R3.0.0T


report_quality flag rules:
-------------------------

    POS             PARAMS              report_quality
    ----------------------------------------------------
    passed          all failed          fail
                    rest                pass
                
    failed          all                 fail
                            
    not checked     at least 1 passed   pass
    (3              all failed          fail
                    all not checked     not checked
    ---------------------------------------------------



Dev NOTES:
---------
There are some hardcoding for ICOADS_R3.0.0.T: we are looking for report_id in CDM
adding 'ICOADS_30' to the UID in the QC flags!!!!!

Maybe should pass a QC version configuration file, with the path
of the QC files relative to a set path (i.e. informing of the QC version)


.....

@author: iregon
"""

import sys
import os
import simplejson
import json
import datetime
import cdm
import glob
import numpy as np
import logging
import pandas as pd
from imp import reload
reload(logging)  # This is to override potential previous config of logging


# Functions--------------------------------------------------------------------
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
        process_options = ['history_explain', 'qc_first_date_avail',
                           'qc_last_date_avail']
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

# This is to get the unique flag per parameter
def get_qc_flags(qc,qc_df_full):
    print('Here!') # dyb
    qc_avail = True
    bad_flag = '1' if qc != 'POS' else '2'
    good_flag = '0'
    qc_filename = os.path.join(qc_path,params.year,params.month,"_".join([qc,'qc',params.year+params.month,'CCIrun.csv']))
    logging.info('Reading {0} qc file: {1}'.format(qc,qc_filename))
    qc_df = pd.read_csv(qc_filename,dtype = qc_dtype,usecols=qc_columns.get(qc),
                          delimiter = qc_delimiter, error_bad_lines = False, warn_bad_lines = True )
    # Map UID to CDM (harcoded source ICOADS_R3.0.0T here!!!!!)
    # and keep only reports from current monthly table
    qc_df['UID'] = 'ICOADS-30-' + qc_df['UID']
    qc_df.set_index('UID',inplace=True,drop=True)
    print( " ======================================================== " )
    print( qc_df.index.duplicated()) # dyb
    print( " ======================================================== " )
    print( qc_df.loc[ qc_df.index.duplicated() ] )
    print( " ======================================================== " )
    print( header_df.index.duplicated()) # dyb
    print( " ======================================================== " )
    print( header_df.loc[ header_df.index.duplicated() ] )
    print( " ======================================================== " )

    qc_df = qc_df.reindex(header_df.index)
    if len(qc_df.dropna(how='all')) == 0:
        # We can have files with nothing other than duplicates (which are not qced):
        # set qc to not available but don't fail: keep on generating level1e prodcut afterwards
        logging.warning('No {} flags matching'.format(qc)) 
        qc_avail = False
        return qc_avail, qc_df_full

    locs_notna = qc_df.notna().all(axis=1)
    qc_df.loc[locs_notna,'total'] = qc_df.loc[locs_notna].sum(axis=1)
    qc_df.loc[locs_notna,'global'] = qc_df['total'].apply(lambda x: good_flag if x == 0 else bad_flag  )
    qc_df.rename({'global':qc},axis=1,inplace=True) 
    # For measured params, eliminate resulting quality_flag when that parameter
    # is not available in a report ('noval'==1)
    # Mixing failing and missing is annoying for several things afterwards
    if qc != 'POS':
        qc_df.loc[qc_df['noval'] == '1',qc] = np.nan
    qc_df_full[qc] = qc_df[qc]
    return qc_avail, qc_df_full

def add_report_quality(qc_df_full):
    failed_location = '2'
    pass_report = '0'
    failed_report = '1'
    not_checked_report = '2'
    # Initialize to not checked: there were lots of discussions with this!
    # override ICOADS IRF flag if not checked in C3S system? In the end we said yes.
    qc_df_full['report_quality'] = not_checked_report
    # First: all observed params fail -> report_quality = '1'
    qc_param = [ x for x in qc_list if x!= 'POS' ]
    qc_param_applied = qc_df_full[qc_param].count(axis=1)
    qc_param_sum = qc_df_full[qc_param].astype(float).sum(axis=1)
    qc_df_full.loc[(qc_param_sum >= qc_param_applied) & (qc_param_applied > 0),'report_quality'] = failed_report
    # Second: at least one observed param passed -> report_quality = '0'
    qc_df_full.loc[qc_param_sum < qc_param_applied,'report_quality'] = pass_report
    # Third: POS qc fails, no matter how good the observed params are -> report_quality '1'
    qc_df_full.loc[qc_df_full['POS'] == failed_location,'report_quality'] = failed_report
    
    return qc_df_full

# This is to apply the qc flags and write out fllgged tables
def process_table(table_df,table_name):
    pass_time = '2'
    not_checked_report = '2'
    not_checked_location = '3'
    not_checked_param = '2'
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

    qc_dict[table_name] = {'total':len(table_df)}
    if flag:
        qc = table_qc.get(table_name).get('qc')
        element = table_qc.get(table_name).get('element')
        qc_table = qc_df[[qc]]
        qc_table.rename({qc:element},axis=1,inplace=True) 
        table_df.update(qc_table)

        updated_locs = qc_table.loc[qc_table.notna().all(axis=1)].index

        if table_name != 'header':
            qc_dict[table_name]['quality_flags'] = table_df[element].value_counts(dropna=False).to_dict()

        if table_name == 'header':
            table_df.update(qc_df['report_quality'])
            history_add = ';{0}. {1}'.format(history_tstmp,params.history_explain)
            table_df['report_time_quality'] = pass_time
            qc_dict[table_name]['location_quality_flags'] = table_df['location_quality'].value_counts(dropna=False).to_dict()
            qc_dict[table_name]['report_quality_flags'] = table_df['report_quality'].value_counts(dropna=False).to_dict()
            table_df['history'].loc[updated_locs] = table_df['history'].loc[updated_locs] + history_add
    # Here very last minute change to account for reports not in QC files: need to make sure it is all not-checked!
    # Test new things with 090-221. See 1984-03. What happens if not POS flags matching?
    else:
        if table_name != 'header':
            table_df['quality_flag'] = not_checked_param
        else:
            table_df['report_time_quality'] = pass_time
            table_df['report_quality'] = not_checked_report
            table_df['location_quality'] = not_checked_location
        
    cdm_columns = cdm_tables.get(table_name).keys()
    odata_filename = os.path.join(level_path,filename_field_sep.join([table_name,fileID]) + '.psv')
    table_df.to_csv(odata_filename, index = False, sep = delimiter, columns = cdm_columns
                 ,header = header, mode = wmode, na_rep = 'null')

    return

# This is to remove files of a previous process on this same level file
def clean_level(file_id):
    level_prods = glob.glob(os.path.join(level_path,'*-' + file_id + '.psv'))
    level_logs = glob.glob(os.path.join(level_log_path, file_id + '.*'))
    level_ql = glob.glob(os.path.join(level_ql_path, '*' + file_id + '*.*'))
    for filename in level_prods + level_ql + level_logs:
        try:
            logging.info('Removing previous file: {}'.format(filename))
            os.remove(filename)
        except:
            logging.warning('Could not remove previous file: {}'.format(filename))
            pass
#------------------------------------------------------------------------------

# PARAMETERIZE HOW TO HANDLE QC FILES AND HOW TO APPLY THESE TO THE CDM FIELDS-
# -----------------------------------------------------------------------------            
# 1. These are the columns we actually use from the qc files, regardless of the
# existence of others. These names must be the same as the ones in the QC file 
# header (1st line)
qc_columns = dict()
qc_columns['SST'] = ['UID','bud', 'clim', 'nonorm', 'freez', 'noval', 'hardlimit']
qc_columns['AT'] = ['UID','bud', 'clim', 'nonorm', 'noval', 'mat_blacklist', 'hardlimit']
qc_columns['SLP'] = ['UID','bud', 'clim', 'nonorm', 'noval']
qc_columns['DPT'] = ['UID','bud', 'clim', 'nonorm', 'ssat', 'noval', 'rep', 'repsat']
qc_columns['POS'] = ['UID','trk', 'date', 'time', 'pos', 'blklst']
qc_columns['W'] = ['UID','noval','hardlimit','consistency','wind_blacklist']

# 2. This is to what table-element pair each qc file is pointing to
qc_cdm = {'SST':('observations-sst','quality_flag'),
            'SLP':('observations-slp','quality_flag'),
            'AT':('observations-at','quality_flag'),
            'DPT':[('observations-dpt','quality_flag'),('observations-wbt','quality_flag')],
            'W':[('observations-ws','quality_flag'),('observations-wd','quality_flag')],
            'POS':('header','location_quality')
            }

# 3. This is the same as above but with different indexing, 
#to ease certain operations
table_qc = {}
for k,v in qc_cdm.items():
    if isinstance(v,list):
        for t in v:
            table_qc[t[0]] = {'qc':k,'element':t[1]}
    else:
        table_qc[v[0]] = {'qc':k,'element':v[1]}
        
qc_dtype = {'UID':'object'}
qc_delimiter = ','
# -----------------------------------------------------------------------------
        
# Some other parameters -------------------------------------------------------
filename_field_sep = '-'
delimiter = '|'
level = 'level1e'
level_prev = 'level1d'
header = True
wmode = 'w'

cdm_tables = cdm.lib.tables.tables_hdlr.load_tables()
obs_tables = [ x for x in cdm_tables.keys() if x != 'header' ]

history_tstmp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
# -----------------------------------------------------------------------------

# MAIN ------------------------------------------------------------------------

# Process input, set up some things and make sure we can do something   -------
logging.basicConfig(format='%(levelname)s\t[%(asctime)s](%(filename)s)\t%(message)s',
                    level=logging.INFO,datefmt='%Y%m%d %H:%M:%S',filename=None)
if len(sys.argv)>1:
    logging.info('Reading command line arguments')
    args = sys.argv
else:
    logging.error('Need arguments to run!')
    sys.exit(1)

params = script_setup(args)

release_path = os.path.join(params.data_path,params.release,params.dataset)
release_id = filename_field_sep.join([params.release,params.update ])
fileID = filename_field_sep.join([str(params.year),str(params.month).zfill(2),release_id ])
fileID_date = filename_field_sep.join([str(params.year),str(params.month)])

prev_level_path = os.path.join(release_path,level_prev,params.sid_dck)
level_path = os.path.join(release_path,level,params.sid_dck)
level_ql_path = os.path.join(release_path,level,'quicklooks',params.sid_dck)
level_log_path = os.path.join(release_path,level,'log',params.sid_dck)

qc_path = os.path.join(release_path,'metoffice_qc','base')

# Check we have all the dirs!
data_paths = [prev_level_path, level_path, level_ql_path, level_log_path, qc_path ]
if any([ not os.path.isdir(x) for x in data_paths ]):
    logging.error('Could not find data paths: {}'.format(','.join([ x for x in data_paths if not os.path.isdir(x)])))
    sys.exit(1)

# Check we have QC files!
logging.info('Using qc files in {}'.format(qc_path))
qc_pos_filename = os.path.join(qc_path,params.year,params.month,"_".join(['POS','qc',params.year+params.month,'CCIrun.csv']))
qc_avail = True
if not os.path.isfile(qc_pos_filename):
    file_date = datetime.datetime.strptime(str(params.year) + '-' + str(params.month),'%Y-%m')
    last_date = datetime.datetime.strptime(params.qc_last_date_avail,'%Y-%m')
    first_date = datetime.datetime.strptime(params.qc_first_date_avail,'%Y-%m')
    if file_date > last_date or file_date < first_date:
        qc_avail = False
        logging.warning('QC only available in period {0} to {1}'
                        .format(str(params.qc_first_date_avail),str(params.qc_last_date_avail)))
        logging.warning('level1e data will be created with no merging') 
    else:
        logging.error('POSITION QC file not found: {}'.format(qc_pos_filename))
        sys.exit(1)

# Do some additional checks before clicking go, do we have a valid header?
header_filename = os.path.join(prev_level_path,filename_field_sep.join(['header',fileID]) + '.psv')
if not os.path.isfile(header_filename):
    logging.error('Header table file not found: {}'.format(header_filename))
    sys.exit(1)
table = 'header'
header_df = pd.DataFrame()
header_df = cdm.read_tables(prev_level_path,fileID,cdm_subset=[table],na_values='null')
if len(header_df) == 0:
    logging.error('Empty or non-existing header table')
    sys.exit(1)

# See what CDM tables are available for this fileID
tables_in = ['header']     
for table in obs_tables:
    table_filename = os.path.join(prev_level_path,filename_field_sep.join([table,fileID]) + '.psv')
    if not os.path.isfile(table_filename):
        logging.warning('CDM table not available: {}'.format(table_filename))
    else:
        tables_in.append(table)

if len(tables_in) == 1:
    logging.warning('NO OBS TABLES AVAILABLE: {0}, period {1}-{2}'.format(params.sid_dck,params.year,params.month))

# DO THE DATA PROCESSING ------------------------------------------------------
header_df.set_index('report_id', inplace=True,drop=False)   
qc_dict = {}
clean_level(fileID)

# 1. PROCESS QC FLAGS ---------------------------------------------------------
# GET THE QC FILES WE NEED FOR THE CURRENT SET OF CDM TABLES
# AND CREATE A DF WITH THE UNIQUE FLAGS PER QC AND HAVE IT INDEXED TO FULL CDM 
# TABLE (ALL REPORTS)
# ALSO BUILD FROM FULL QC FLAGS SET THE REPORT_QUALITY FLAG
if qc_avail:       
    qc_list = list(set([ table_qc.get(table).get('qc') for table in tables_in ]))
    qc_df = pd.DataFrame(index = header_df.index, columns = qc_list)
    # Make sure POS is first as we need it to process the rest!
    # The use of POS in other QCs is probably a need inherited from BetaRelease,
    # where param qc was merged with POS QC. Now we don't do that, so I am quite
    # positive we don't use POS in assigning quality_flag in obs table
    qc_list.remove('POS')
    qc_list.insert(0,'POS')
    for qc in qc_list: 
        qc_avail,qc_df = get_qc_flags(qc,qc_df)
        if not qc_avail:
            break
    
if qc_avail:    
    qc_df = add_report_quality(qc_df)

# 2. APPLY FLAGS, LOOP THROUGH TABLES -----------------------------------------

# Test new things with 090-221. See 1984-03. What happens if not POS flags matching?
# Need to make sure we override with 'not-checked'(2 or 3 depending on element!) default settings:
#    header.report_quality = default ICOADS IRF flag to not-checked ('2')
#    observations.quality_flag = default not-checked ('2') to not-checked('2')
#    header.location_quality = default not-checked ('3') to not-checked('3')
 
# First header, then rest.
flag = True if qc_avail else False
process_table(header_df,'header')

for table in obs_tables:
    flag = True if table in tables_in and qc_avail else False
    process_table(table,table)

# CHECKOUT --------------------------------------------------------------------
qc_dict['date processed'] = datetime.datetime.now()  
      
logging.info('Saving json quicklook')
level_io_filename = os.path.join(level_ql_path,fileID + '.json')
with open(level_io_filename,'w') as fileObj:
    simplejson.dump({'-'.join([params.year,params.month]):qc_dict},fileObj,
                     default = date_handler,indent=4,ignore_nan=True)

logging.info('End') 
