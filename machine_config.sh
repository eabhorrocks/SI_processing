# Paths that differ between sorting machines, worked out from where this repo is so the same
# scripts run anywhere (sourced by the all_in_one_*.sh scripts, not run).
#
# With the repo at <root>/SI_processing (e.g. /home/lab/si_edd/SI_processing):
#   base_folder       <root>/temp_data/          local working copy of each session
#   server_folder     /mnt/rds01/ibn-vision/DATA/SUBJECTS/
#   pathToCatGTRunit  <repo>/CatGT-linux/runit.sh
#   pathToTPrimeRunit <repo>/TPrime-linux/runit.sh
#
# To use something else on one machine, set it in machine.local.sh next to this file. git does
# not track that file, so it stays with the machine. For example:
#   base_folder='/media/lab/Data/temp_data/'

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

base_folder="$(dirname -- "$repo_dir")/temp_data/"
server_folder='/mnt/rds01/ibn-vision/DATA/SUBJECTS/'
pathToCatGTRunit="$repo_dir/CatGT-linux/runit.sh"
pathToTPrimeRunit="$repo_dir/TPrime-linux/runit.sh"

if [[ -f $repo_dir/machine.local.sh ]]; then
    source "$repo_dir/machine.local.sh"
fi
