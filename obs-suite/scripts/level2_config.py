#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 13 16:18:36 2019

Create initial level2 product list from the initial source-deck periods list

Outputs file to /<data_path>/<release>/<source>/level2/level.json

Inargs:
------
release_periods_file: full path to release periods file
year_init: first year in release period to include in level2
year_end: last year in release period to include in level2


@author: iregon
"""

import os
import sys
import json

# Find command line arguments -------------------------------------------------
if len(sys.argv)>1:
     release_periods_file = sys.argv[1]
     year_init = int(sys.argv[2])
     year_end = int(sys.argv[3])
# -----------------------------------------------------------------------------   
 
level_filename = os.path.join('level2.json')

with open(release_periods_file,'r') as fO:
    level2_dict = json.load(fO)


for k in level2_dict.keys():
    level2_dict[k].update({'exclude':False,'params_exclude':[]})
    # This is because the current version of the periods file has the periods
    # in strings!!!!
    level2_dict[k]['year_init'] = int(level2_dict[k]['year_init'])
    level2_dict[k]['year_end'] = int(level2_dict[k]['year_end'])
    if level2_dict[k]['year_init'] < year_init:
        level2_dict[k]['year_init'] = year_init 
    if level2_dict[k]['year_end'] > year_end:
        level2_dict[k]['year_end'] = year_end 
    
level2_dict['params_exclude'] = []
level2_dict['year_init'] = year_init
level2_dict['year_end'] = year_end

with open(level_filename,'w') as fileObj:
    json.dump(level2_dict,fileObj,indent=4)    

logging.info('End')
