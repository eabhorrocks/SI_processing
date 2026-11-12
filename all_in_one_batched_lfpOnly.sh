#!/bin/bash
# LFP-only batch: copy from the server, CatGT/TPrime, upload the LFP and NIDQ outputs, then
# delete that session's local copy. Sessions from any number of mice; see all_in_one_batched.sh
# and batch_lib.sh for the entry format. A session that fails stops at its first failing step;
# its local files are moved to <base_folder>/_failed/ and the batch carries on. Failed sessions
# are listed at the end.

set -e # exit on error
# Print Python output as it happens, also when piped through tee
export PYTHONUNBUFFERED=1
source "$(dirname "$0")/batch_lib.sh"

# --- Main Configuration (defaults for every session) ---
no_probe=1 # number of probes; override per session with probes=<n>
use_ks4=true
use_ks3=false
get_qm=true

# --- Machine paths ---
# base_folder, server_folder and the CatGT/TPrime paths come from machine_config.sh, which
# works them out from where this repo is (temp_data/ sits next to SI_processing/). To change
# one on this machine only, set it in machine.local.sh (see machine_config.sh).
source "$(dirname "$0")/machine_config.sh"

# --- Sessions to Process ---
# One entry per session: "<mouse> <acquisitions> [probes=<n>]", e.g. "M25120 20260624/20260624_0".
SESSIONS=(
    "M25120 20260624/20260624_0"
    "M25120 20260624/20260624_1"
    "M25120 20260624/20260624_2"
    "M25120 20260624/20260624_3"
)

# Check every entry, the paths and the CatGT/TPrime links before starting
check_entries "${SESSIONS[@]}"
check_machine
echo "${#SESSIONS[@]} sessions to process:"
printf '    %s\n' "${SESSIONS[@]}"

# --- One session's steps (run_session stops at the first one that fails) ---
lfp_session() {
    # Copy files from server to local drive
    python copyFilesLocally.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $server_folder

    # Run CatGT and TPrime
    python runCatGTandTPrime.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $server_folder $pathToCatGTRunit $pathToTPrimeRunit

    # Pre-processing
    #python preprocessProbes.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3

    # Run Spike Sorting
    #python runSpikeSorting.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $get_qm

    # Upload results to server
    python uploadToServer_lfp.py $mouse $dates $save_date $base_folder $session_probes $use_ks4 $use_ks3 $server_folder
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
    echo "----------------------------------------------------"

    run_session lfp_session
    # Delete this session's local copy only (not the rest of the mouse's folder), or move it
    # aside if the session failed
    finish_session
done

report_failures ${#SESSIONS[@]}
