#!/bin/bash
# Sort a batch of sessions, from any number of mice, one after another: copy from the server,
# CatGT/TPrime, preprocess, Kilosort, metrics, upload, then delete that session's local copy.
# A session that fails stops at its first failing step; its local files are moved to
# <base_folder>/_failed/ and the batch carries on. Failed sessions are listed at the end.

set -e # exit on error
# Print Python output as it happens, also when piped through tee
export PYTHONUNBUFFERED=1
source "$(dirname "$0")/batch_lib.sh"

# --- Main Configuration (defaults for every session) ---
no_probe=1 # number of probes; override per session with probes=<n>
use_ks4=true
use_ks3=false
get_qm=true
# Bad channel removal: auto (default), si_default, dead_out or none (see bad_channels.py).
# Override per session with bad_channels=<mode>.
bad_channel_mode='auto'
# true also computes principal_components and the PCA-based quality metrics
# (isolation_distance, l_ratio, d_prime, nn_*, silhouette): about an hour per session.
pca_metrics=false

# --- Machine paths ---
# base_folder, server_folder and the CatGT/TPrime paths come from machine_config.sh, which
# works them out from where this repo is (temp_data/ sits next to SI_processing/). To change
# one on this machine only, set it in machine.local.sh (see machine_config.sh).
source "$(dirname "$0")/machine_config.sh"

# --- Sessions to Process ---
# One entry per sort: "<mouse> <acquisitions> [probes=<n>] [bad_channels=<mode>]".
# Acquisitions are folders under <mouse>/ephys/ on the server, e.g. 20250922/20250922_0.
# Join several from one day with commas to concatenate them into one sort (CatGT supercat).
# Mice can be mixed, e.g.
#   "M25104 20250922/20250922_0"
#   "M26018 20260622/20260622_0 bad_channels=dead_out"
SESSIONS=(
    "M26018 20260621/20260621_0"
    "M26018 20260621/20260621_1"
    "M26018 20260621/20260621_2"
    "M26018 20260621/20260621_3"
    "M26018 20260621/20260621_4"
    "M26018 20260621/20260621_5"
)

# Check every entry, the paths and the CatGT/TPrime links before starting
check_entries "${SESSIONS[@]}"
check_machine
echo "${#SESSIONS[@]} sessions to process:"
printf '    %s\n' "${SESSIONS[@]}"

# --- One session's steps (run_session stops at the first one that fails) ---
sort_session() {
    # Copy files from server to local drive
    python copyFilesLocally.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $server_folder

    # Run CatGT and TPrime
    python runCatGTandTPrime.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $server_folder $pathToCatGTRunit $pathToTPrimeRunit

    # Pre-processing
    python preprocessProbes.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $session_bad_channel_mode

    # Run Spike Sorting
    python runSpikeSorting.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $get_qm $pca_metrics

    # Run MATLAB script for unit matching
    #matlab -nosplash -nodisplay -nodesktop -r "mouse='${mouse}'; date='${save_date}'; base_folder='${base_folder}';no_probe='${session_probes}';dates='${dates}'; run('unit_match_merge_ks4_eddit2.m'); exit;"

    # Merge and calculate quality metrics
    #python mergeAndCalculateQualityMetrics.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3

    # Upload results to server
    python uploadToServer.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $server_folder
}

# --- Processing Loop ---
failed_sessions=()
for entry in "${SESSIONS[@]}"; do

    parse_entry "$entry"
    session_start=$SECONDS

    echo "----------------------------------------------------"
    echo "Mouse         : $mouse"
    echo "Session       : $dates"
    echo "Save date     : $save_date"
    echo "Probes        : $session_probes"
    echo "Bad channels  : $session_bad_channel_mode"
    echo "----------------------------------------------------"

    run_session sort_session
    # Delete this session's local copy only (not the rest of the mouse's folder), or move it
    # aside if the session failed
    finish_session
done

report_failures ${#SESSIONS[@]}
