from datetime import datetime

startTime = datetime.now()
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))
''' this section defines the animal and dates and fetch the recordings from the server to Beast'''

from pathlib import Path

import os
import shutil

import numpy as np

import spikeinterface.sorters
import spikeinterface.full as si
import scipy.signal
import spikeinterface.extractors as se
import spikeinterface.comparison
import spikeinterface.exporters
import spikeinterface.curation
import spikeinterface.widgets
import docker
import itertools
from spikeinterface.exporters import export_report


import scipy.io as sio

import sys

import os
import subprocess
print('import time:')
print(datetime.now()-startTime)
subprocess.run('ulimit -n 4096', shell=True)

import pandas as pd
def save_spikes_to_csv(spikes, save_folder):
    unit_index = spikes['unit_index']
    segment_index = spikes['segment_index']
    sample_index = spikes['sample_index']
    spikes_df = pd.DataFrame({'unit_index': unit_index, 'segment_index': segment_index, 'sample_index': sample_index})
    spikes_df.to_csv(save_folder + 'spikes.csv', index=False)


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
print(mouse)
print('acquisition folder: ', dates)
use_ks4 = sys.argv[6].lower() in ['true', '1', 't', 'y', 'yes']
use_ks3 = sys.argv[7].lower() in ['true', '1', 't', 'y', 'yes']

temp_save_folder = local_folder + mouse + "/"

# get the output folder of CatGT for SI to read
parent_dir = temp_save_folder + save_date + '/'
save_folder = temp_save_folder + save_date +'/SpikeSorting/'

extensions = ['templates', 'template_metrics', 'noise_levels', 'template_similarity', 'correlograms', 'isi_histograms']
job_kwargs = dict(n_jobs=32, chunk_duration='1s', progress_bar=True)

for probe in range(int(no_probe)):

    # load the pre-processed probe
    probe_processed = si.load_extractor(parent_dir+'probe'+str(probe)+'_preprocessed')
    print(probe_processed)

    # do the spike sorting

    if use_ks4:
        # set params
        ks4params = si.get_default_sorter_params(sorter_name_or_class='kilosort4')
        ks4params['do_CAR'] = False

        print("ks4 params: \n", ks4params)

        print('Running kilosort 4 on probe ', probe)
        probe_sorting_ks4 = si.run_sorter(sorter_name='kilosort4', recording=probe_processed,
                                           folder=save_folder + 'probe' + str(probe) + '/sorters/kilosort4/')

        probe_sorting_ks4 = si.remove_duplicated_spikes(sorting=probe_sorting_ks4, censored_period_ms=0.3,
                                                         method='keep_first')

        # quality metrics and waveforms
        probe_we_ks4 = si.create_sorting_analyzer(probe_sorting_ks4, probe_processed,
                                                   format='binary_folder',
                                                   folder=save_folder + 'probe' + str(probe) + '/sorters/kilosort4/metrics/',
                                                   sparse=True, overwrite=True,
                                                   **job_kwargs)
        probe_we_ks4.compute('random_spikes')
        probe_we_ks4.compute('waveforms', ms_before=1.0, ms_after=2.0, **job_kwargs)
        probe_we_ks4.compute(extensions, **job_kwargs)
        probe_we_ks4.compute('principal_components', **job_kwargs)
        probe_we_ks4.compute('spike_amplitudes', **job_kwargs)
        qm_list = si.get_default_qm_params()
        print('The following quality metrics are being computed:')
        print(qm_list)
        probe_we_ks4.compute('quality_metrics', qm_params=qm_list,**job_kwargs)
        export_report(sorting_analyzer=probe_we_ks4, output_folder=save_folder +'probe'+str(probe)+'/sorters/kilosort4/report/')

        probe_ks4_spikes = np.load(
            save_folder + 'probe' + str(probe) + '/sorters/kilosort4/metrics/sorting/spikes.npy')
        save_spikes_to_csv(probe_ks4_spikes,
            save_folder + 'probe' + str(probe) + '/sorters/kilosort4/')

    if use_ks3:
        ks3params = si.get_default_sorter_params(sorter_name_or_class='kilosort3')
        ks3params['do_CAR'] = False

        print('Running kilosort 3 on probe ', probe)
        probe_sorting_ks3 = si.run_sorter(sorter_name= 'kilosort3',recording=probe_processed,
                                           folder=save_folder+'probe'+str(probe)+'/sorters/kilosort3/',
                                           docker_image='spikeinterface/kilosort3-compiled-base:latest')

        probe_sorting_ks3 = si.remove_duplicated_spikes(sorting=probe_sorting_ks3, censored_period_ms=0.3,
                                                         method='keep_first')

        probe_we_ks3 = si.create_sorting_analyzer(probe_sorting_ks3, probe_processed,
                                                   format='binary_folder',
                                                   folder=save_folder + 'probe' + str(probe) + '/sorters/kilosort3/metrics/',
                                                   sparse=True, overwrite=True,
                                                   **job_kwargs)
        probe_we_ks3.compute('random_spikes')
        probe_we_ks3.compute('waveforms', ms_before=1.0, ms_after=2.0, **job_kwargs)
        probe_we_ks3.compute(extensions, **job_kwargs)
        probe_we_ks3.compute('principal_components', **job_kwargs)
        probe_we_ks3.compute('spike_amplitudes', **job_kwargs)
        qm_list = si.get_default_qm_params()
        print('The following quality metrics are being computed:')
        print(qm_list)
        probe_we_ks3.compute('quality_metrics', qm_params=qm_list, **job_kwargs)
        export_report(sorting_analyzer=probe_we_ks3,
                      output_folder=save_folder + 'probe' + str(probe) + '/sorters/kilosort3/report/')

        probe_ks3_spikes = np.load(
            save_folder + 'probe' + str(probe) + '/sorters/kilosort3/metrics/sorting/spikes.npy')
        save_spikes_to_csv(probe_ks3_spikes,
                           save_folder + 'probe' + str(probe) + '/sorters/kilosort3/')

sys.exit(0)
