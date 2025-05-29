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
import subprocess
import pandas as pd
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
base_folder = '/mnt/rds01/ibn-vision/DATA/SUBJECTS/'

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

    # detect and remove bad channels
    bad_channel_ids, channel_labels = si.detect_bad_channels(probe_processed)
    probe_processed = probe_processed.remove_channels(bad_channel_ids)
    print('probe_bad_channel_ids', bad_channel_ids)

    # phase shift correction - equivalent to T-SHIFT in catGT
    #probe_phase_shift = si.phase_shift(probe_bad_channels)
    probe_processed = si.common_reference(probe_processed, operator='median', reference='global')

    #probe0_preprocessed_corrected = probe_common_reference
    # print(probe0_preprocessed_corrected)

    # save pre-processed catenated file
    probe_processed = probe_processed.save(folder=outputDir+'probe'+str(probe)+'_preprocessed', format='binary', **job_kwargs)
    #probe0_preprocessed_corrected = si.load_extractor(save_folder+'probe'+str(probe)+'_preprocessed')


