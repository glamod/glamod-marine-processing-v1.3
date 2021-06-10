#!/bin/bash

export home_directory=/gws/nopw/j04/glamod_marine
export home_directory_smf=/gws/smf/j04/c3s311a_lot2
export code_directory=$home_directory_smf/dyb/release_4.0/glamod-marine-processing/obs-suite
export config_directory=$home_directory_smf/code/marine_code/glamod-marine-config/obs-suite

export pyTools_directory=$code_directory/modules/python
export scripts_directory=$code_directory/scripts
export lotus_scripts_directory=$code_directory/lotus_scripts
export data_directory=$home_directory/data

echo 'Data directory is '$data_directory
echo 'Code directory is '$code_directory
echo 'Config directory is '$config_directory
# Create the scratch directory for the user
export scratch_directory=/work/scratch-nopw/$(whoami)
if [ ! -d $scratch_directory ]
then
  echo "Creating user $(whoami) scratch directory $scratch_directory"
  mkdir $scratch_directory
else
  echo "Scratch directory is $scratch_directory"
fi
