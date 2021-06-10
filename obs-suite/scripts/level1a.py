#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 17 14:24:10 2019

Script to generate the C3S CDM Marine level1a data. 

    - Reads dataset data (and supp if avail) file with module mdf_reader. This 
    includes a data model validation mask.
    - fixes known PT type errors in source dataset with module metmetpy
    - selects data reports according to filtering requests
    - rejects data reports not validiting against its data model
    - maps to the C3S CDM header and observations tables if there is data left
    after cleaning (table[i].psv CDM table-like files)

The processing unit is the source-deck monthly file.

Outputs data to /<data_path>/<release>/<dataset>/level1a/<sid-dck>/table[i]-fileID.psv
Outputs invalid data to /<data_path>/<release>/<dataset>/level1a/invalid/<sid-dck>/fileID-data|mask.psv
Outputs exluded data to /<data_path>/<release>/<dataset>/level1a/excluded/<sid-dck>/fileID-<element>.psv
Outputs quicklook info to:  /<data_path>/<release>/<dataset>/level1a/quicklooks/<sid-dck>/fileID.json

where fileID is year-month-release-update

Before processing starts:
    - checks the existence of all output subdirectories in level1a -> exits if fails
    - checks the existence of the source file to be converted -> exits if fails
    - removes all level1a products on input file resulting from previous runs

On input data:
-------------
Records of input data assumed to be in sid-dck monthly partitions which imply:
    - data for same month-year period
    - data from a unique data model
    

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


configfile:
----------
To specify processing options that may be shared in different processing
settings:
    - main data model
    - supplemental data model
    - processing options: supplemental replacements,
    record selection/filtering by field (i.e. PT....)
        
.....

@author: iregon
"""
import sys
import os
import json
from io import StringIO
import simplejson
import datetime
import mdf_reader
import cdm
import metmetpy
from pandas_operations import select,inspect
from pandas_operations.common import TextParser_hdlr
import glob
import logging
import pandas as pd
import numpy as np
import copy
from imp import reload
reload(logging)  # This is to override potential previous config of logging


FFS = '-'
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
            self.sid_dck = config.get('sid_dck')
            self.year = config.get('yyyy')
            self.month = config.get('mm') 
            self.filename = config.get('filename')
        
        print(config)            
        self.dck = self.sid_dck.split("-")[1]
        
        process_options = ['data_model', 'read_sections','filter_reports_by',
                           'cdm_map']
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

def clean_L1a(L1a_id):
    L1a_prods = glob.glob(os.path.join(L1a_path,'*' + FFS + L1a_id + '.psv'))
    L1a_ql = glob.glob(os.path.join(L1a_ql_path, L1a_id + '.json'))
    L1a_excluded = glob.glob(os.path.join(L1a_excluded_path, L1a_id + FFS + '*.psv'))
    L1a_invalid = glob.glob(os.path.join(L1a_invalid_path, L1a_id + FFS + '*.psv'))
    for filename in L1a_prods + L1a_ql + L1a_excluded + L1a_invalid:
        try:
            logging.info('Removing previous file: {}'.format(filename))
            os.remove(filename)
        except:
            pass

def write_out_junk(dataObj,filename):
    v = [dataObj] if not read_kwargs.get('chunksize') else dataObj
    c = 0
    for df in v:
        wmode = 'a' if c > 0 else 'w'
        header = False if c > 0 else True
        df.to_csv(filename, sep = '|', mode = wmode, header = header)
        c += 1  
# MAIN ------------------------------------------------------------------------

# PROCESS INPUT AND MAKE SOME CHECKS ------------------------------------------
logging.basicConfig(format='%(levelname)s\t[%(asctime)s](%(filename)s)\t%(message)s',
                    level=logging.INFO,datefmt='%Y%m%d %H:%M:%S',filename=None)
if len(sys.argv)>1:
    logging.info('Reading command line arguments')
    args = sys.argv
else:
    logging.error('Need arguments to run!')
    sys.exit(1)

params = script_setup(args)

if not params.flag:
    logging.error('Error parsing initial configuration')
    sys.exit(1)
    
release_path = os.path.join(params.data_path,params.release,params.dataset)

FFS = '-'    
L0_path = os.path.join(params.data_path,'datasets',params.dataset,'level0',params.sid_dck)   
L1a_path = os.path.join(release_path,'level1a',params.sid_dck)
L1a_ql_path = os.path.join(release_path,'level1a','quicklooks',params.sid_dck)
L1a_excluded_path = os.path.join(release_path,'level1a','excluded',params.sid_dck)
L1a_invalid_path = os.path.join(release_path,'level1a','invalid',params.sid_dck)

data_paths = [L0_path, L1a_path, L1a_ql_path, L1a_excluded_path, L1a_invalid_path]
if any([ not os.path.isdir(x) for x in data_paths ]):
    logging.error('Could not find data paths: '.format(','.join([ x for x in data_paths if not os.path.isdir(x)])))
    sys.exit(1)

#L0_filename = os.path.join(L0_path,FFS.join([params.year,params.month]) + '.imma')
L0_filename = params.filename


if not os.path.isfile(L0_filename):
    logging.error('L0 file not found: {}'.format(L0_filename))
    sys.exit(1)
    
release_id = FFS.join([params.release,params.update ])   
L1a_id = FFS.join([str(params.year),str(params.month).zfill(2),release_id ])

# CLEAN PREVIOUS L1A PRODUCTS AND SIDE FILES ----------------------------------
clean_L1a(L1a_id)

# DO THE DATA PROCESSING ------------------------------------------------------
data_model = params.data_model
dataset = params.dataset
io_dict = {}

#1. Read input file to dataframe
logging.info('Reading dataset data')

read_kwargs = {'data_model':params.data_model,
                  'sections':params.read_sections,
                  'chunksize':200000}

data_in = mdf_reader.read(L0_filename, **read_kwargs)

print(data_in)

io_dict['read'] = {'total':inspect.get_length(data_in.data)}

# 2. PT fixing, filtering and invalid rejection
# 2.1. Fix platform type

# dataset = ICOADS_R3.0.0T is not "registered" in metmetpy, but icoads_r3000
# Modify metmetpy so that it maps ICOADS_R3.0.0T to its own alliaeses
# we now do the dirty trick here: dataset_metmetpy = icoads_r3000

logging.info('Applying platform type fixtures')
dataset_metmetpy = 'icoads_r3000'
data_model_metmetpy = 'imma1'
data_in.data = metmetpy.correct_pt.correct(data_in.data,dataset_metmetpy,data_model_metmetpy,params.dck)

# 2.2. Apply record selection (filter by) criteria: PT types.....
if hasattr(params, 'filter_reports_by'):
    logging.info('Applying selection filters')
    io_dict['not_selected'] = {}
    data_excluded = {}
    data_excluded['atts'] = data_in.atts.copy()
    data_excluded['data'] = {}
    # 3.1. Select by report_filters options
    for k,v in params.filter_reports_by.items():
        io_dict['not_selected'][k] = {}
        logging.info('Selecting {0} values: {1}'.format(k,','.join(v)))
        filter_location = tuple(k.split('.'))
        col = filter_location[0] if len(filter_location) == 1 else filter_location
        values = v
        selection={col:values}
        data_in.data,data_excluded['data'][k],index = select.select_from_list(data_in.data,selection,out_rejected = True,in_index = True)
        data_in.mask= select.select_from_index(data_in.mask,index)
        io_dict['not_selected'][k]['total'] = inspect.get_length(data_excluded['data'][k])
        if io_dict['not_selected'][k]['total'] > 0:
            if data_in.atts[col]['column_type'] in ['str','object','key']:
                io_dict['not_selected'][k].update(inspect.count_by_cat(data_excluded['data'][k],col))
    io_dict['not_selected']['total'] = sum([ v.get('total') for k,v in io_dict['not_selected'].items()])

io_dict['pre_selected'] = {'total':inspect.get_length(data_in.data)}    


# 2.3. Keep track of invalid data 
# First create a global mask and count failure occurrences
newmask_buffer = StringIO()
logging.info('Removing invalid data')
for data,mask in zip(data_in.data,data_in.mask):
    # 2.3.1. Global mask
    mask['global_mask'] = mask.all(axis=1)
    mask.to_csv(newmask_buffer,header = False, mode = 'a', encoding = 'utf-8',index = False)
    
    # 2.3.2. Invalid reports counts and values
    # Initialize counters if first chunk
    masked_columns = [ x for x in mask if not all(mask[x].isna()) and x!=('global_mask','') ]
    if not io_dict.get('invalid'):
        io_dict['invalid'] = {".".join(k):{'total':0,'values':[]} for k in masked_columns}
    for col in masked_columns:
        k = ".".join(col)
        io_dict['invalid'][k]['total'] += len(mask[col].loc[~mask[col]])
        if col in data: # cause some masks are not in data (datetime....)
            io_dict['invalid'][k]['values'].extend(data[col].loc[~mask[col]].values)

newmask_buffer.seek(0)   
chunksize = None if isinstance(data_in.mask,pd.DataFrame) else data_in.mask.orig_options['chunksize']
data_in.mask = pd.read_csv(newmask_buffer,names = [ x for x in mask ], chunksize = chunksize)    
data_in.data = TextParser_hdlr.restore(data_in.data)
# Now see what fails
for col in masked_columns:
    k = '.'.join(col)
    if io_dict['invalid'][k]['total'] > 0:
        if data_in.atts.get(col,{}).get('column_type') in mdf_reader.properties.object_types:
            ivalues = list(set(io_dict['invalid'][k]['values']))
            # This is because sorting fails on strings if nan
            if np.nan in ivalues:
                ivalues.remove(np.nan)
                ivalues.sort()
                ivalues.append(np.nan)
            else:
                ivalues.sort()
            io_dict['invalid'][k].update({i:io_dict['invalid'][k]['values'].count(i) for i in ivalues})
            sush = io_dict['invalid'][k].pop('values',None)
        elif data_in.atts.get(col,{}).get('column_type') in mdf_reader.properties.numeric_types:
            values = io_dict['invalid'][k]['values']
            values = np.array(values)[~np.isnan(np.array(values))]
            if len(values>0):
                [counts,edges] = np.histogram(values)
                # Following binning approach only if at most 1 sign digit!
                bins = [ '-'.join(["{:.1f}".format(edges[i]),"{:.1f}".format(edges[i+1])]) for i in range(0,len(edges)-1)]
                io_dict['invalid'][k].update({b:counts for b,counts in zip(bins,counts)})
            else:
                io_dict['invalid'][k].update({'nan?':len(io_dict['invalid'][k]['values'])})
            sush = io_dict['invalid'][k].pop('values',None)
    else:
        sush = io_dict['invalid'].pop(k,None)

# 2.4. Discard invalid data. 
data_invalid = {}
data_invalid['atts'] = data_in.atts.copy()
col = 'global_mask'            
data_in.data,data_invalid['data'] = select.select_true(data_in.data,data_in.mask,col,out_rejected = True)
data_in.mask,data_invalid['valid_mask'] = select.select_true(data_in.mask,data_in.mask,col,out_rejected = True)
            
io_dict['invalid']['total'] = inspect.get_length(data_invalid['data'])         
io_dict['processed'] = {'total':inspect.get_length(data_in.data)}

process = True
if io_dict['processed']['total'] == 0:
    process = False
    logging.warning('No data to map to CDM after selection and cleaning')


# 2.9. Let's save reports with no observations...
#OBS_VALUES = [ ('core',x) for x in ['AT','SST','SLP','D','W','WBT','DPT'] ]
#no_obs_file = os.path.join(L1a_path,'no_obs',str(params.year) + FFS + str(params.month) + '.psv')
#c = 0
#for data_obs in data_in.data:
#    if len(data_obs[data_obs[OBS_VALUES].isna().all(axis=1)]) > 0:
#        if not os.path.isdir(os.path.join(L1a_path,'no_obs')):
#            os.mkdir(os.path.join(L1a_path,'no_obs'))
#        wmode = 'a' if c > 0 else 'w'
#        header = False if c > 0 else True
#        data_obs[data_obs[OBS_VALUES].isna().all(axis=1)].to_csv(no_obs_file, sep = '|', mode = wmode, header = header)
#        c += 1  
            
#data_in.data = TextParser_hdlr.restore(data_in.data)
# 3. Map to common data model and output files
if process:
    logging.info('Mapping to CDM')
    tables = ['header','observations-at','observations-sst','observations-dpt',
                  'observations-wbt','observations-wd','observations-ws','observations-slp']
    obs_tables = tables[1:]
    io_dict.update({table:{} for table in tables})
    mapping = params.cdm_map
    cdm_tables = cdm.map_model(mapping, data_in.data, data_in.atts,
                               log_level = 'INFO')
    
    logging.info('Printing tables to psv files')
    cdm.cdm_to_ascii(cdm_tables,log_level ='DEBUG',
                     out_dir = L1a_path, suffix = L1a_id, prefix = None)
        
    for table in tables:
        io_dict[table]['total'] = inspect.get_length(cdm_tables[table]['data'])

io_dict['date processed'] = datetime.datetime.now()
logging.info('Saving json quicklook')
L1a_io_filename = os.path.join(L1a_ql_path,L1a_id + '.json')
with open(L1a_io_filename,'w') as fileObj:
    simplejson.dump({'-'.join([params.year,params.month]):io_dict},fileObj,
                     default = date_handler,indent=4,ignore_nan=True)
    
# Output exluded and invalid ---------------------------------------------
if hasattr(params, 'filter_reports_by'):
    for k,v in data_excluded['data'].items():
        if inspect.get_length(data_excluded['data'][k]) > 0:
            excluded_filename = os.path.join(L1a_excluded_path,L1a_id + FFS + '_'.join(k.split('.')) + '.psv')  
            logging.info('Writing {0} excluded data to file {1}'.format(k,excluded_filename))
            write_out_junk(v,excluded_filename)

if inspect.get_length(data_invalid['data']) > 0:
    invalid_data_filename = os.path.join(L1a_invalid_path,L1a_id + FFS + 'data.psv')
    invalid_mask_filename = os.path.join(L1a_invalid_path,L1a_id + FFS + 'mask.psv')
    logging.info('Writing invalid data to file {}'.format(invalid_data_filename))
    write_out_junk(data_invalid['data'],invalid_data_filename)
    logging.info('Writing invalid data mask to file {}'.format(invalid_mask_filename))
    write_out_junk(data_invalid['valid_mask'],invalid_mask_filename)
