#!/bin/bash

set -e # exit on error

# Define variables
mouse='M24019' #mouse id
save_date='20240719' #date of recording
dates='20240719/20240719_0,20240719/20240719_2' #acquisition date and session e.g. dates='20240624/20240624_0,20240624/20240624_1'
base_folder='/home/lab/spikeinterface_sorting/temp_data/'  # Adjust this path if necessary
server_folder='/mnt/rds01/ibn-vision/DATA/SUBJECTS/' # path to SUBJECTS dir on server
pathToCatGTRunit='/home/lab/CatGT-linux/runit.sh'
pathToTPrimeRunit='/home/lab/TPrime-linux/runit.sh'

no_probe=1 #number of probes you have in this session
use_ks4=true #use kilosort4
use_ks3=false #use kilosort3

# Copy files from server to local drive
python copyFilesLocally.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder

# Consider method to get output directory, try outputString=$(python myPythonScript arg1 arg2 arg3)

python runCatGTandTPrime.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder $pathToCatGTRunit $pathToTPrimeRunit

#pre-processing as separate script
python preprocessProbes.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

python runSpikeSorting.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

#matlab -nosplash -nodisplay -nodesktop -r "mouse='${mouse}'; date='${save_date}'; base_folder='${base_folder}';no_probe='${no_probe}';dates='${dates}'; run('unit_match_merge_ks4_eddit2.m'); exit;"

python mergeAndCalculateQualityMetrics.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

python uploadToServer.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3


