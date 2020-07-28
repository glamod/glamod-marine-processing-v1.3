#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  8 12:29:06 2019

Creates the directory tree for a new C3S data release and source or for a new
source in a pre-existing release

Inargs:
------

data_path: parent directory where tree is to be created
config_path: path to the obs-suite config directory
release: name for release directory
update_tag: tag for the release update
dataset: name for data source in directory tree

@author: iregon
"""

import os
import sys
import json

PERIODS_FILE = 'source_deck_periods.json'
# Find command line arguments -------------------------------------------------
if len(sys.argv)>1:
     data_path = sys.argv[1]
     config_path = sys.argv[2]
     release = sys.argv[3]
     update = sys.argv[4]
     dataset = sys.argv[5]

# Functions -------------------------------------------------------------------
def create_subdir(lpath,subdir_list):
    subdir_list = [subdir_list] if isinstance(subdir_list,str) else subdir_list
    for subdir in subdir_list:
        subdir_dir = os.path.join(lpath,subdir)
        if not os.path.isdir(subdir_dir):
            os.mkdir(subdir_dir,0o774)

# Go --------------------------------------------------------------------------
levels = ['level1a','level1b','level1c','level1d','level1e','level1f', 'level2']
level_subdirs = {}
#level_subdirs['level0'] = []
level_subdirs['level1a'] = ['log','quicklooks','invalid','excluded']
level_subdirs['level1b'] = ['log','quicklooks']
level_subdirs['level1c'] = ['log','quicklooks','invalid']
level_subdirs['level1d'] = ['log','quicklooks']
level_subdirs['level1e'] = ['log','quicklooks','reports']
level_subdirs['level1f'] = ['log','quicklooks','reports']
level_subdirs['level2'] = ['log','quicklooks','excluded','reports']
deep_sublevels = ['log','quicklooks','invalid','excluded','reports']
os.umask(0)
# READ LIST OF SID-DCKS FOR RELEASE
release_tag = '-'.join([release,update])
release_periods_file = os.path.join(config_path,release_tag,dataset,PERIODS_FILE)
with open(release_periods_file,'r') as fileO:
    sid_dck_dict = json.load(fileO)

for level in levels:
    level_subdirs[level].extend(sid_dck_dict.keys())

# CREATE DIR FOR RELEASE
release_tag = release
create_subdir(data_path,release_tag)

# CREATE DIR FOR SOURCE
release_path = os.path.join(data_path,release_tag)
create_subdir(release_path, dataset)

# CREATE LEVELS
source_path = os.path.join(release_path, dataset)
create_subdir(source_path,levels)

# POPULATE LEVELS WITH SID-DCK, LOG AND QL SUBDIRECTORIES
for level in levels:
    level_subdir = os.path.join(source_path,level)
    create_subdir(level_subdir,level_subdirs[level])

    for sublevel in deep_sublevels:
        if sublevel in level_subdirs.get(level):
            create_subdir(os.path.join(level_subdir,sublevel),sid_dck_dict.keys())
