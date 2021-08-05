home_directory=/gws/nopw/j04/glamod_marine/
home_directory_smf=/gws/smf/j04/c3s311a_lot2
code_directory=$home_directory_smf/dyb/release_4.0/glamod-marine-processing/qc-suite
scripts_directory=$code_directory/scripts
pyEnvironment_directory=$code_directory/pyenvs/env0
modules_directory=$code_directory/modules

echo 'Code directory is '$code_directory

# Activate python environment and add jaspy3.7 path to LD_LIBRARY_PATH so that cartopy and other can find the geos library
source $pyEnvironment_directory/bin/activate
export PYTHONPATH="$modules_directory:${PYTHONPATH}"
export LD_LIBRARY_PATH=/apps/contrib/jaspy/miniconda_envs/jaspy3.7/m3-4.5.11/envs/jaspy3.7-m3-4.5.11-r20181219/lib/:$LD_LIBRARY_PATH
echo "Python environment loaded from gws: $pyEnvironment_directory"

# Create the scratch directory for the user
#scratch_directory=/work/scratch-nompiio/$(whoami)
#if [ ! -d $scratch_directory ]
#then
#  echo "Creating user $(whoami) scratch directory $scratch_directory"
#  mkdir $scratch_directory
#else
#  echo "Scratch directory is $scratch_directory"
#fi
