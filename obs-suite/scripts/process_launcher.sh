#!/bin/bash
# Sends a bsub array of jobs for every sid-deck listed in a the input file
# to run the corresponding script
#
# Within the sid-deck array, a subjob is only submitted if the corresponding
# source monthly file is available.
#
# bsub input, error and output files are initially located in
# <scratch_dir>/level1a/sid_dck
#
#
# process_list is: sid-dck
#
# Usage: ./process_launcher.sh release update dataset process_config_file list_file -f 0|1 -s yyyy -e yyyy
# Optional kwargs:
# -f: process only failed (0) | process all (1 or none)
# -s: start processing year (defaults to sid-dck initial year)
# -e: end processing year (defaults to sid-dck last year)

#. FUNCTIONS -------------------------------------------------------------------
# Write entry to json input file
function to_json {
    printf "\"%s\":\"%s\",\n" $2 $3 >> $1
}

# Get JOB
function nk_jobid {
    output=$($*)
    echo $output | head -n1 | cut -d'<' -f2 | cut -d'>' -f1
}
# Check var exists
function check_config {
    if [ -z $2 ]
    then
      echo "ERROR: CONFIGURATION VARIABLE $1 is empty"
      return 1
    else
      echo "CONFIGURATION VARIABLE $1 set to $2"
      return 0
    fi
}
# Check var exists, otherwise default
function check_soft {
    if [ -z $2 ]
    then
      echo "WARNING: CONFIGURATION VARIABLE $1 is empty, will use default"
      return 1
    else
      echo "CONFIGURATION VARIABLE $1 set to $2"
      return 0
    fi
}
# Check dir exists
function check_dir {
    if [ -d $2 ]
    then
      echo "DIRECTORY $1 set to $2"
      return 0
    else
      echo "ERROR: DIRECTORY $1 NOT FOUND: $2"
      return 1
    fi
}
# Check file exists
function check_file {
    if [ -s $2 ]
    then
      echo "FILE $1 is $2"
      return 0
    else
      echo "ERROR: can't find or zero size $1 FILE: $2"
      return 1
    fi
}
#. END FUNCTIONS ---------------------------------------------------------------

#. PARAMS ----------------------------------------------------------------------
FFS="-"
#. END PARAMS ------------------------------------------------------------------

#. INARGS ----------------------------------------------------------------------
release=$1
update=$2
dataset=$3
# Here make sure we are using fully expanded paths, as some may be passed to a config file
process_config_file=$(readlink --canonicalize  $4)
process_list=$(readlink --canonicalize $5)

shift 5
while getopts ":f:" opt; do
  case $opt in
    f) failed="$OPTARG"
    ;;
    s) process_start="$OPTARG"
    ;;
    e) process_end="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    ;;
  esac
done
if [ "$failed" == '0' ];then failed_only=true;else failed_only=false;fi
if [ -z "$process_start" ];then process_start=-99999;fi
if [ -z "$process_end" ];then process_end=99999;fi
#. CONFIG FILES & ENVIRONMENT --------------------------------------------------
source ../setpaths.sh

sid_dck_periods=$code_directory/configuration_files/$release'_'$update/$dataset/source_deck_periods.json

check_file sid_dck_periods $sid_dck_periods || exit 1
check_file process_config_file $process_config_file || exit 1

process=$(basename $process_config_file ".json")
env=$(jq -r '.["job"].environment | select (.!=null)' $process_config_file)
source ../setenv$env.sh
echo
#. END INARGS, CONFIG FILES AND ENVIRONMENT ------------------------------------

#. GET MAIN CONFIG -------------------------------------------------------------
data_level=$(jq -r '.["job"].data_level | select (.!=null)' $process_config_file)
job_time_hr=$(jq -r '.["job"].job_time_hr | select (.!=null)' $process_config_file)
job_time_min=$(jq -r '.["job"].job_time_min | select (.!=null)' $process_config_file)
job_memo_mb=$(jq -r '.["job"].job_memo_mb | select (.!=null)' $process_config_file)
script_name=$(jq -r '.["job"].script_name | select (.!=null)' $process_config_file)

for confi in data_level job_time_hr job_time_min job_memo_mb
do
  check_config $confi "${!confi}"  || exit 1
done
#. END GET MAIN CONFIG ---------------------------------------------------------

# MAIN DIRS, LOG AND CONFIRM ---------------------------------------------------
data_dir=$data_directory/$release/$dataset/$data_level
log_dir=$data_dir/log

for diri in data_dir log_dir
do
  check_dir $diri "${!diri}" || exit 1
done

echo
read -p "Do you want to continue (Y/y/N/n)? " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

filebase=$(basename $process_list)
log_file=$log_dir/$process$FFS${filebase%.*}$FFS$(date +'%Y%m%d_%H%M').log

echo "LOGGING TO $log_file"

exec > $log_file 2>&1
# END MAIN DIRS, LOG AND CONFIRM -----------------------------------------------

job_time_hhmm=$job_time_hr":"$job_time_min

# PROCESS ALL SID-DCKS FROM LIST -----------------------------------------------
for sid_dck in $(awk '{print $1}' $process_list)
do
  echo
  echo "---------------------------"
  echo "INFO: processing $sid_dck"
  echo "---------------------------"
  sid_dck_log_dir=$log_dir/$sid_dck
  log_basenamei=$release$FFS$update$FFS$process
  test -e $sid_dck_log_dir/$log_basenamei.failed
  failed=$?
  if [ "$failed" == 0 ];then failed=true;else failed=false;fi
  if $failed_only && ! $failed
  then
    echo "INFO: FAILED ONLY MODE. $sid_dck: already processed successfully. Not listed"
    continue
  fi
  job_memo_mbi=$job_memo_mb
  job_time_hri=$job_time_hr
  job_time_mini=$job_time_min
  # Get processing period
  year_init=$(jq -r --arg sid_dck "$sid_dck" '.[$sid_dck] | .year_init | select (.!=null)' $sid_dck_periods)
  year_end=$(jq -r --arg sid_dck "$sid_dck" '.[$sid_dck] | .year_end | select (.!=null)' $sid_dck_periods)
  if (( process_start > year_init ));then year_init=$process_start;fi
  if (( process_end < year_end ));then year_end=$process_end;fi
  check_config year_init $year_init || exit 1
  check_config year_end $year_end || exit 1
  # Set source-deck specific job settings and directories
	job_memo_mb_=$(jq -r --arg sid_dck "$sid_dck" '.[$sid_dck] | .job_memo_mb | select (.!=null)' $process_config_file)
  job_time_hr_=$(jq -r --arg sid_dck "$sid_dck" '.[$sid_dck] | .job_time_hr | select (.!=null)' $process_config_file)
	job_time_min_=$(jq -r --arg sid_dck "$sid_dck" '.[$sid_dck] | .job_time_min | select (.!=null)' $process_config_file)

  check_soft job_memo_mb_ $job_memo_mb_ && job_memo_mbi=$job_memo_mb_
  check_soft job_time_hr_ $job_time_hr_ && job_time_hri=$job_time_hr_
  check_soft job_time_min_ $job_time_min_ && job_time_mini=$job_time_min_
  job_time_hhmm=$job_time_hri":"$job_time_mini

  sid_dck_scratch_dir=$scratch_directory/$release/$dataset/$process/$sid_dck
  echo "INFO: Setting deck $process scratch directory: $sid_dck_scratch_dir"
  rm -rf $sid_dck_scratch_dir;mkdir -p $sid_dck_scratch_dir


  rm $sid_dck_log_dir/$log_basenamei.*

  jobid=$(nk_jobid bsub -J $sid_dck$process -oo $sid_dck_scratch_dir/$process.o -eo $sid_dck_scratch_dir/$process.o -q short-serial -W $job_time_hhmm -M $job_memo_mbi -R "rusage[mem=$job_memo_mbi]" \
  python $scripts_directory/$script_name $data_directory $release $update $dataset $sid_dck $year_init $year_end $process_config_file)

  bsub -J $sid_dck"OK" -w "done($jobid)" -oo $sid_dck_scratch_dir/$process.ho -eo $sid_dck_scratch_dir/$process.ho -q short-serial -W 00:01 -M 10 -R "rusage[mem=10]" \
  python $scripts_directory/process_output_hdlr.py $scratch_directory $data_directory $release $update $dataset $process $data_level $sid_dck 0

  bsub -J $sid_dck"ERR" -w "exit($jobid)" -oo $sid_dck_scratch_dir/$process.ho -eo $sid_dck_scratch_dir/$process.ho -q short-serial -W 00:01 -M 10 -R "rusage[mem=10]" \
  python $scripts_directory/process_output_hdlr.py $scratch_directory $data_directory $release $update $dataset $process $data_level $sid_dck 1

done
# END PROCESS ALL SID-DCKS FROM LIST -------------------------------------------
