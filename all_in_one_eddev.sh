#!/bin/bash

set -e # exit on error

# Define variables
mouse='M26018' #mouse id
save_date='20260622' #date of recording
dates='20260622/20260622_0' #'20260421/M26015_20260421_1','20260421/M26015_20260421_2' #acquisition date and session e.g. dates='20240624/20240624_0,20240624/20240624_1'
base_folder='/home/saleem_lab/si_edd/temp_data/'  
#beast: '/home/lab/spikeinterface_sorting/temp_data/' GZ: 'home/saleem_lab/spikeinterface_sorting/temp_data/

server_folder='/mnt/rds01/ibn-vision/DATA/SUBJECTS/' #'/home/saleem_lab/rds01/ibn-vision/DATA/SUBJECTS/' # should be same on both: '/mnt/rds01/ibn-vision/DATA/SUBJECTS/' GZ: 
#server_folder='/run/user/1011/gvfs/smb-share:server=rdp.arc.ucl.ac.uk,share=ritd-ag-project-rd01ie-asale69/ibn-vision/DATA/SUBJECTS/'
#server_folder='/home/saleem_lab/rds01/ibn-vision/DATA/SUBJECTS/'

pathToCatGTRunit='/home/saleem_lab/si_edd/SI_processing/CatGT-linux/runit.sh' 
# beast: '/home/lab/CatGT-linux/runit.sh', GZ: /home/saleem_lab/si_edd/SI_processing/CatGT-linux/runit.sh
pathToTPrimeRunit='/home/saleem_lab/si_edd/SI_processing/TPrime-linux/runit.sh' 
# beast: '/home/lab/TPrime-linux/runit.sh',  GZ: /home/saleem_lab/si_edd/SI_processing/TPrime-linux/runit.sh

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


