# Shared by all_in_one_batched.sh and all_in_one_batched_lfpOnly.sh (sourced, not run).
#
# A session entry is "<mouse> <acquisitions> [probes=<n>] [bad_channels=<mode>]", e.g.
#   "M25104 20250922/20250922_0"
#   "M26018 20260622/20260622_0 bad_channels=dead_out"
#   "M25066 20250617/20250617_0,20250617/20250617_1 probes=2"
# Acquisitions are folders under <mouse>/ephys/ on the server; several, comma-separated, are
# concatenated into one sort (CatGT supercat). Options default to the script's no_probe and
# bad_channel_mode.

BAD_CHANNEL_MODES="auto si_default dead_out none"

# parse_entry "<entry>": set mouse, dates, save_date, session_probes and
# session_bad_channel_mode, or print why the entry is malformed and return 1.
parse_entry() {
    local entry=$1 opt key value
    local -a words
    read -r -a words <<< "$entry"
    if (( ${#words[@]} < 2 )); then
        echo "Bad entry '$entry': expected '<mouse> <date>/<date>_<acq>[,...] [option=value ...]'" >&2
        return 1
    fi
    mouse=${words[0]}
    dates=${words[1]}
    save_date=${dates%%/*}
    session_probes=${no_probe:-1}
    session_bad_channel_mode=${bad_channel_mode:-auto}
    # The mouse and days become paths that are deleted after upload: allow plain names only.
    if ! [[ $mouse =~ ^[A-Za-z0-9_-]+$ ]]; then
        echo "Bad entry '$entry': mouse must be a plain name such as M25104" >&2
        return 1
    fi
    if ! [[ $dates =~ ^[0-9]{8}/[A-Za-z0-9_-]+(,[0-9]{8}/[A-Za-z0-9_-]+)*$ ]]; then
        echo "Bad entry '$entry': acquisitions must look like 20250922/20250922_0 (comma-separated for several)" >&2
        return 1
    fi
    for opt in "${words[@]:2}"; do
        key=${opt%%=*}
        value=${opt#*=}
        case $key in
            probes)
                if ! [[ $opt == *=* && $value =~ ^[1-9][0-9]*$ ]]; then
                    echo "Bad entry '$entry': probes must be a positive integer" >&2
                    return 1
                fi
                session_probes=$value
                ;;
            bad_channels)
                if [[ " $BAD_CHANNEL_MODES " != *" $value "* ]]; then
                    echo "Bad entry '$entry': bad_channels must be one of: $BAD_CHANNEL_MODES" >&2
                    return 1
                fi
                session_bad_channel_mode=$value
                ;;
            *)
                echo "Bad entry '$entry': unknown option '$opt' (known: probes=, bad_channels=)" >&2
                return 1
                ;;
        esac
    done
}

# check_entries "${SESSIONS[@]}": parse every entry before anything runs, so a typo in the
# last entry does not stop a batch hours in. Returns 1 if any entry is malformed.
check_entries() {
    local entry bad=0
    if (( $# == 0 )); then
        echo "No sessions to process" >&2
        return 1
    fi
    for entry in "$@"; do
        parse_entry "$entry" || bad=1
    done
    return $bad
}

# _session_days: print each acquisition day of the current entry once.
_session_days() {
    local acq day seen=" "
    local -a acqs
    IFS=',' read -r -a acqs <<< "$dates"
    for acq in "${acqs[@]}"; do
        day=${acq%%/*}
        if [[ -n $day && $seen != *" $day "* ]]; then
            seen+="$day "
            echo "$day"
        fi
    done
}

# _local_root: print base_folder without its trailing slash, or return 1 if it or mouse is
# empty or base_folder is /, so a delete or move cannot hit the wrong folder.
_local_root() {
    local root=${base_folder%/}
    if [[ -z $root || $root == / || -z $mouse ]]; then
        echo "Refusing to delete or move local files: base_folder='$base_folder', mouse='$mouse'" >&2
        return 1
    fi
    echo "$root"
}

# delete_local_session: after a successful upload, delete this session's local copy, i.e.
# <base_folder>/<mouse>/<day> for each acquisition day in the current entry (raw copy, CatGT
# output, preprocessed binary and sorting all live there), then <base_folder>/<mouse> if
# nothing else is left in it. Other sessions and mice are untouched.
delete_local_session() {
    local root day dir
    root=$(_local_root) || return 1
    for day in $(_session_days); do
        dir="$root/$mouse/$day"
        if [[ -d $dir ]]; then
            echo "Deleting local copy: $dir"
            rm -rf -- "$dir"
        else
            echo "Warning: local copy $dir not found"
        fi
    done
    if rmdir -- "$root/$mouse" 2>/dev/null; then
        echo "Removed empty folder: $root/$mouse"
    fi
    return 0
}

# set_aside_failed_session: move a failed session's local copy, each <base_folder>/<mouse>/<day>,
# to <base_folder>/_failed/<mouse>_<day>_<time>, and print the new paths. Nothing is deleted, so
# the files can be inspected, but the next session starts clean: sessions from the same day
# share the day folder (CatGToutput, nidq_processed and lfp are per day, not per acquisition).
set_aside_failed_session() {
    local root day src dest stamp n
    root=$(_local_root) || return 1
    stamp=$(date +%Y%m%d-%H%M%S)
    for day in $(_session_days); do
        src="$root/$mouse/$day"
        [[ -d $src ]] || continue
        mkdir -p -- "$root/_failed"
        dest="$root/_failed/${mouse}_${day}_$stamp"
        n=1
        while [[ -e $dest ]]; do
            dest="$root/_failed/${mouse}_${day}_${stamp}_$n"
            n=$((n + 1))
        done
        mv -- "$src" "$dest"
        echo "$dest"
    done
    rmdir -- "$root/$mouse" 2>/dev/null || true
}

# _error_line <log>: one line saying why a session failed, from its stderr: the first "ERROR:"
# line (runCatGTandTPrime.py's checks) with its first listed problem, else the last Python
# exception line, else the last line. Progress-bar text before a carriage return is dropped.
_error_line() {
    local line
    line=$(awk '{ sub(/.*\r/, "") }
        /^ERROR:/ {
            if ($0 ~ /:$/ && (getline next_line) > 0) {
                sub(/.*\r/, "", next_line); sub(/^[[:space:]]*-[[:space:]]*/, "", next_line)
                $0 = $0 " " next_line
            }
            print; exit
        }' "$1")
    [[ -n $line ]] || line=$(grep -a -o -E '[A-Za-z_][A-Za-z0-9_.]*(Error|Exception): .*' "$1" | tail -n 1)
    [[ -n $line ]] || line=$(grep -a -v -E '^[[:space:]]*$' "$1" | tail -n 1)
    line=${line//$'\r'/}
    echo "${line:-no error output}"
}

# run_session <command...>: run one session's steps in a subshell that stops at the first
# failing step. Sets session_status (0 = success) and session_error (one line saying why) and
# returns 0, so the batch carries on with the next session either way.
# Call it as a plain command, never inside `if`, `&&`, `||` or `!`: bash ignores set -e in
# anything run from those, so a failing step would not stop the session.
run_session() {
    local restore_e=0 err_log
    [[ $- == *e* ]] && restore_e=1
    set +e
    err_log=$(mktemp)
    exec 3>&1
    # stdout goes straight out; stderr goes through tee, which keeps a copy for session_error
    ( set -e; "$@" ) 2>&1 1>&3 3>&- | tee "$err_log" >&2
    session_status=${PIPESTATUS[0]}
    exec 3>&-
    session_error=""
    if (( session_status != 0 )); then
        session_error=$(_error_line "$err_log")
    fi
    rm -f -- "$err_log"
    (( restore_e )) && set -e
    return 0
}

# finish_session: after run_session, delete the session's local copy if it succeeded; if not,
# move the copy to <base_folder>/_failed/ and add the session to failed_sessions.
finish_session() {
    local minutes=$(( (SECONDS - session_start) / 60 )) aside
    if (( session_status == 0 )); then
        delete_local_session
        echo "Finished $mouse $dates in $minutes min"
        return 0
    fi
    aside=$(set_aside_failed_session)
    aside=${aside//$'\n'/, }
    failed_sessions+=("$mouse $dates: $session_error [exit $session_status after $minutes min; local files: ${aside:-none}]")
    echo "FAILED $mouse $dates after $minutes min: $session_error"
    echo "Local files moved to: ${aside:-none}. Carrying on with the next session."
}

# report_failures <n sessions>: list the failed sessions and return 1 if there were any.
report_failures() {
    if (( ${#failed_sessions[@]} == 0 )); then
        echo "--- All $1 sessions processed successfully! ---"
        return 0
    fi
    echo "--- ${#failed_sessions[@]} of $1 sessions failed: ---"
    printf '    %s\n' "${failed_sessions[@]}"
    echo "Failed sessions' local files are under ${base_folder%/}/_failed/; delete them when done."
    return 1
}
