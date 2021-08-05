
#pyEnvironment_directory=$home_directory_smf/code/marine_code/glamod-marine-processing/obs-suite/pyenvs/env0
pyEnvironment_directory=$home_directory_smf/dyb/release_4.0/glamod-marine-processing/obs-suite/pyenvs/env0
# Activate python environment and add jaspy3.7 path to LD_LIBRARY_PATH so that cartopy and other can find the geos library
source $pyEnvironment_directory/bin/activate
export PYTHONPATH="$pyTools_directory:${PYTHONPATH}"
export LD_LIBRARY_PATH=/apps/contrib/jaspy/miniconda_envs/jaspy3.7/m3-4.5.11/envs/jaspy3.7-m3-4.5.11-r20181219/lib/:$LD_LIBRARY_PATH
echo "Python environment loaded from gws: $pyEnvironment_directory"
