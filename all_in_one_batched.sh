#!/bin/bash

set -e # exit on error
# Print Python output as it happens, also when piped through tee
export PYTHONUNBUFFERED=1

# --- Main Configuration ---
mouse='M26018' # mouse id
base_folder='/home/saleem_lab/si_edd/temp_data/'
server_folder='/mnt/rds01/ibn-vision/DATA/SUBJECTS/'
no_probe=1 # number of probes
use_ks4=true
use_ks3=false
get_qm=true
# Bad channel removal: auto (default), si_default, dead_out or none (see bad_channels.py).
# Override one session by adding ":<mode>" to its entry below, e.g. "20260622/20260622_0:none".
bad_channel_mode='auto'
# true also computes principal_components and the PCA-based quality metrics
# (isolation_distance, l_ratio, d_prime, nn_*, silhouette): about an hour per session.
pca_metrics=false

# --- Paths to Executables ---
pathToCatGTRunit='/home/saleem_lab/si_edd/SI_processing/CatGT-linux/runit.sh'
pathToTPrimeRunit='/home/saleem_lab/si_edd/SI_processing/TPrime-linux/runit.sh'

# --- List of Dates and Sessions to Process ---
# Add all the sessions you want to run to this list
DATES_TO_PROCESS=(
    "20260621/20260621_0"
    "20260621/20260621_1"
    "20260621/20260621_2"
    "20260621/20260621_3"
    "20260621/20260621_4"
    "20260621/20260621_5"
)

# --- Processing Loop ---
# This loop will iterate through each item in the DATES_TO_PROCESS array.
for entry in "${DATES_TO_PROCESS[@]}"; do

    # Split an optional ":<bad channel mode>" off the entry
    dates=${entry%%:*}
    session_bad_channel_mode=$bad_channel_mode
    if [[ "$entry" == *:* ]]; then
        session_bad_channel_mode=${entry#*:}
    fi

    # Dynamically extract the save_date from the current session string
    # This takes the part of the string before the '/'
    save_date=${dates%%/*}

    echo "----------------------------------------------------"
    echo "Processing mouse: $mouse"
    echo "Session       : $dates"
    echo "Save date     : $save_date"
    echo "Bad channels  : $session_bad_channel_mode"
    echo "----------------------------------------------------"

    # Copy files from server to local drive
    python copyFilesLocally.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder

    # Run CatGT and TPrime
    python runCatGTandTPrime.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder $pathToCatGTRunit $pathToTPrimeRunit

    # Pre-processing
    python preprocessProbes.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $session_bad_channel_mode

    # Run Spike Sorting
    python runSpikeSorting.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $get_qm $pca_metrics

    # Run MATLAB script for unit matching
    #matlab -nosplash -nodisplay -nodesktop -r "mouse='${mouse}'; date='${save_date}'; base_folder='${base_folder}';no_probe='${no_probe}';dates='${dates}'; run('unit_match_merge_ks4_eddit2.m'); exit;"

    # Merge and calculate quality metrics
    #python mergeAndCalculateQualityMetrics.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3

    # Upload results to server
    python uploadToServer.py $mouse $dates $save_date $base_folder $no_probe $use_ks4 $use_ks3 $server_folder
    
    DIR_TO_DELETE="/home/saleem_lab/si_edd/temp_data/$mouse"
    if [ -d "$DIR_TO_DELETE" ]; then
  	echo "Found directory: $DIR_TO_DELETE"
  	echo "Deleting..."
  
  	# The deletion command
  	rm -rf "$DIR_TO_DELETE"
  
    	echo "Directory deleted successfully."
    else
  	echo "Warning: Directory $DIR_TO_DELETE was not found."
fi


done

echo "--- All sessions processed successfully! ---"
