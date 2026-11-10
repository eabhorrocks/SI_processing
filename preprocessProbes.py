from datetime import datetime

startTime = datetime.now()
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))

from pathlib import Path

import os
import shutil

import numpy as np

import spikeinterface.full as si
import scipy.signal
import docker
import itertools

import scipy.io as sio

import sys

import os
import json
import subprocess
import pandas as pd

from bad_channels import check_mode, select_bad_channels, summary as bad_channel_summary
print("import time: ", datetime.now()-startTime)


# grab recordings from the server to local machine (Beast)

job_kwargs = dict(n_jobs=32, chunk_duration='1s', progress_bar=True)

# The first command-line argument after the script name is the mouse identifier.
# mouse='M24019' #mouse id
# save_date='20240716' #date of recording
# dates='20240716/20240716_0,20240716/20240716_2' #acquisition date and session e.g. dates='20240624/20240624_0,20240624/20240624_1'
# dates=dates.split(',')
# base_folder='/home/lab/spikeinterface_sorting/temp_data/'  # Adjust this path if necessary
# local_folder = base_folder
# no_probe=1 #number of probes you have in this session

# The first command-line argument after the script name is the mouse identifier.
mouse = sys.argv[1]
# All command-line arguments after `mouse` and before `save_date` are considered dates.
dates = sys.argv[2].split(',')  # This captures all dates as a list.
# The last command-line argument is `save_date`.
save_date = sys.argv[3]
local_folder = sys.argv[4]
no_probe = sys.argv[5]
use_ks4 = sys.argv[6].lower() in ['true', '1', 't', 'y', 'yes']
use_ks3 = sys.argv[7].lower() in ['true', '1', 't', 'y', 'yes']
# Optional 8th argument: bad channel mode (auto, si_default, dead_out, none). See bad_channels.py.
bad_channel_mode = check_mode(sys.argv[8] if len(sys.argv) > 8 else 'auto')
print('bad channel mode: ', bad_channel_mode)

save_folder = local_folder + mouse + "/"

# get the output folder of CatGT for SI to read
catGTDir = save_folder + '/' + save_date + '/CatGToutput/'
outputDir = save_folder + '/' + save_date + '/'

for probe in range(int(no_probe)):

    # load the probe
    print('probe #: ', probe)
    probe_name = 'imec' + str(probe) + '.ap'
    probe_raw = si.read_spikeglx(catGTDir, stream_name=probe_name)
    print(probe_raw)

    # pre-processing steps
    # highpass filter - threhsold at 300Hz
    probe_processed = si.highpass_filter(probe_raw, freq_min=300)

    # detect and remove bad channels (the labels and decision are saved to bad_channels.json)
    bad_channel_ids, bad_channel_report = select_bad_channels(probe_processed, mode=bad_channel_mode)
    probe_processed = probe_processed.remove_channels(bad_channel_ids)
    print(bad_channel_summary(bad_channel_report))
    print('probe_bad_channel_ids', list(bad_channel_ids))

    # phase shift correction - equivalent to T-SHIFT in catGT
    #probe_phase_shift = si.phase_shift(probe_bad_channels)
    probe_processed = si.common_reference(probe_processed, operator='median', reference='global')

    #probe0_preprocessed_corrected = probe_common_reference
    # print(probe0_preprocessed_corrected)

    # save pre-processed catenated file
    preprocessed_folder = outputDir + 'probe' + str(probe) + '_preprocessed'
    probe_processed = probe_processed.save(folder=preprocessed_folder, format='binary', **job_kwargs)
    # inside the preprocessed folder, so uploadToServer.py copies it with the recording's JSON
    with open(os.path.join(preprocessed_folder, 'bad_channels.json'), 'w') as f:
        json.dump(bad_channel_report, f, indent=2)
    #probe0_preprocessed_corrected = si.load_extractor(save_folder+'probe'+str(probe)+'_preprocessed')


