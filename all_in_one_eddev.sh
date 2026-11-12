#!/bin/bash

set -e # exit on error
# Print Python output as it happens, also when piped through tee
export PYTHONUNBUFFERED=1

# Define variables
mouse='M26018' #mouse id
save_date='20260622' #date of recording
dates='20260622/20260622_0' #'20260421/M26015_20260421_1','20260421/M26015_20260421_2' #acquisition date and session e.g. dates='20240624/20240624_0,20240624/20240624_1'
# base_folder, server_folder and the CatGT/TPrime paths come from machine_config.sh, which
# works them out from where this repo is (temp_data/ sits next to SI_processing/). To change
# one on this machine only, set it in machine.local.sh (see machine_config.sh).
source "$(dirname "$0")/batch_lib.sh"
source "$(dirname "$0")/machine_config.sh"
check_machine

no_probe=1 #number of probes you have in this session
use_ks4=true #use kilosort4
use_ks3=false #use kilosort3
get_qm=true
bad_channel_mode='auto' # auto, si_default, dead_out or none (see bad_channels.py)
pca_metrics=false # true adds principal_components + PCA quality metrics (~1 h per session)

# Copy files from server to local draive
python copyFilesLocally.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder

# Consider method to get output directory, try outputString=$(python myPythonScript arg1 arg2 arg3)

python runCatGTandTPrime.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder $pathToCatGTRunit $pathToTPrimeRunit

#pre-processing as separate script
python preprocessProbes.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $bad_channel_mode

python runSpikeSorting.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $get_qm $pca_metrics

#matlab -nosplash -nodisplay -nodesktop -r "mouse='${mouse}'; date='${save_date}'; base_folder='${base_folder}';no_probe='${no_probe}';dates='${dates}'; run('unit_match_merge_ks4_eddit2.m'); exit;"

#python mergeAndCalculateQualityMetrics.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

python uploadToServer.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder


