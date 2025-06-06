#!/bin/bash

set -e # exit on error

# Define variables
mouse='M25065' #mouse id
save_date='20250605' #date of recording
dates='20250605/20250605_0' #acquisition date and session e.g. dates='20240624/20240624_0,20240624/20240624_1'
base_folder='/home/saleem_lab/si_edd/temp_data/'  
# beast: '/home/lab/spikeinterface_sorting/temp_data/' GZ: 'home/saleem_lab/spikeinterface_sorting/temp_data/
server_folder='/mnt/rds01/ibn-vision/DATA/SUBJECTS/' # should be same on both: '/mnt/rds01/ibn-vision/DATA/SUBJECTS/' GZ: 
pathToCatGTRunit='/home/saleem_lab/si_edd/SI_processing/CatGT-linux/runit.sh' 
# beast: '/home/lab/CatGT-linux/runit.sh', GZ: /home/saleem_lab/si_edd/SI_processing/CatGT-linux/runit.sh
pathToTPrimeRunit='/home/saleem_lab/si_edd/SI_processing/TPrime-linux/runit.sh' 
# beast: '/home/lab/TPrime-linux/runit.sh',  GZ: /home/saleem_lab/si_edd/SI_processing/TPrime-linux/runit.sh

no_probe=1 #number of probes you have in this session
use_ks4=true #use kilosort4
use_ks3=false #use kilosort3

# Copy files from server to local drive
python copyFilesLocally.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder

# Consider method to get output directory, try outputString=$(python myPythonScript arg1 arg2 arg3)

python runCatGTandTPrime.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder $pathToCatGTRunit $pathToTPrimeRunit

pre-processing as separate script
#python preprocessProbes.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

python runSpikeSorting.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

#matlab -nosplash -nodisplay -nodesktop -r "mouse='${mouse}'; date='${save_date}'; base_folder='${base_folder}';no_probe='${no_probe}';dates='${dates}'; run('unit_match_merge_ks4_eddit2.m'); exit;"

#python mergeAndCalculateQualityMetrics.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

python uploadToServer.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder


