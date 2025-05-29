from pathlib import Path

print("Calculating quality metrics")

import os
import shutil
import subprocess
subprocess.run('ulimit -n 10000',shell=True)

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
from datetime import datetime
import itertools
from spikeinterface.exporters import export_report
import scipy.io as sio
import sys


startTime = datetime.now()
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))
''' this section defines the animal and dates and fetch the recordings from the server to Beast'''

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
save_folder = local_folder + mouse + '/' + save_date + '/SpikeSorting/'
parent_folder = local_folder + mouse + '/' + save_date + '/'


extensions = ['templates', 'template_metrics', 'noise_levels', 'template_similarity', 'correlograms', 'isi_histograms']
job_kwargs = dict(n_jobs=32, chunk_duration='1s', progress_bar=True)

for probe in range(int(no_probe)):
    probe_preprocessed = si.load_extractor(parent_folder+'/probe'+str(probe)+'_preprocessed')
    if use_ks4:
        
        # merge units based on UnitMatch 
        probe_sorting_ks4 = si.read_sorter_folder(save_folder + 'probe'+str(probe)+'/sorters/kilosort4')
        merge_suggestions = sio.loadmat(save_folder + 'probe'+str(probe)+'/sorters/kilosort4/sorter_output/UnitMatch/' +'um_merge_suggestion_ks4.mat')
        match_ids = merge_suggestions['match_ids']
        merge_ids = match_ids[:,1] - 1
        cs_probe = si.CurationSorting(probe_sorting_ks4)
        unique_ids = np.unique(merge_ids)
        original_ids = probe_sorting_ks4.get_unit_ids()
        for id in unique_ids:
            id_count = np.count_nonzero(merge_ids == id)
            if id_count > 1:
                unit_index = merge_ids == id
                cs_probe.merge(original_ids[unit_index])
                
        # Create a sorting object and compute quality metrics
        probe_sorting_ks4_merged = cs_probe.sorting
        probe_sorting_ks4_merged.save(folder = save_folder + 'probe'+str(probe)+'/sorters/kilosort4_merged/',overwrite=True)
        probe_we_ks4_merged = si.create_sorting_analyzer(probe_sorting_ks4_merged, probe_preprocessed, 
                            format = 'binary_folder',folder=save_folder +'probe'+str(probe)+'/waveform/kilosort4_merged',
                            sparse = True,overwrite = True,
                            **job_kwargs)
        probe_we_ks4_merged.compute('random_spikes')
        probe_we_ks4_merged.compute('waveforms',ms_before=1.0, ms_after=2.0,**job_kwargs)
        probe_we_ks4_merged.compute(extensions,**job_kwargs)
        probe_we_ks4_merged.compute('principal_components',**job_kwargs)
        probe_we_ks4_merged.compute('spike_amplitudes',**job_kwargs)
        qm_list = si.get_default_qm_params()
        print('The following quality metrics are being computed:')
        print(qm_list)
        probe_we_ks4_merged.compute('quality_metrics', qm_params=qm_list,**job_kwargs)
        export_report(sorting_analyzer=probe_we_ks4_merged, output_folder=save_folder +'probe'+str(probe)+'/report/kilosort4_merged')
        
        
    if use_ks3:
        probe_sorting_ks3 = si.read_sorter_folder(save_folder + 'probe'+str(probe)+'/sorters/kilosort3')
        merge_suggestions = sio.loadmat(save_folder + 'probe'+str(probe)+'um_merge_suggestion_ks3.mat')
        match_ids = merge_suggestions['match_ids']
        merge_ids = match_ids[:,1] - 1
        cs_probe = si.CurationSorting(probe_sorting_ks3)
        unique_ids = np.unique(merge_ids)
        original_ids = probe_sorting_ks3.get_unit_ids()
        for id in unique_ids:
            id_count = np.count_nonzero(merge_ids == id)
            if id_count > 1:
                unit_index = merge_ids == id
                cs_probe.merge(original_ids[unit_index])
                
        probe_sorting_ks3_merged = cs_probe.sorting
        probe_sorting_ks3_merged.save(folder = save_folder + 'probe'+str(probe)+'/sorters/kilosort3_merged/',overwrite=True)
        ''' Compute quality metrics on the extracted waveforms'''

        probe_we_ks3_merged = si.create_sorting_analyzer(probe_sorting_ks3_merged, probe_preprocessed, 
                                format = 'binary_folder',folder=save_folder +'probe'+str(probe)+'/waveform/kilosort3_merged',
                                sparse = True,overwrite = True,
                                **job_kwargs)
        probe_we_ks3_merged.compute('random_spikes')
        probe_we_ks3_merged.compute('waveforms',ms_before=1.0, ms_after=2.0,**job_kwargs)
        probe_we_ks3_merged.compute(extensions,**job_kwargs)
        probe_we_ks3_merged.compute('principal_components',**job_kwargs)  
        probe_we_ks3_merged.compute('spike_amplitudes',**job_kwargs)
        qm_list = si.get_default_qm_params()
        print('The following quality metrics are computed:')
        print(qm_list)
        probe_we_ks3_merged.compute('quality_metrics', qm_params=qm_list,**job_kwargs)
        export_report(sorting_analyzer=probe_we_ks3_merged, output_folder=save_folder +'probe'+str(probe)+'/report/kilosort3_merged')

sys.exit(0)