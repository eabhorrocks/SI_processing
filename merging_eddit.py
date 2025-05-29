from pathlib import Path

print("Calculating quality metrics")

import os
import shutil

import numpy as np

import spikeinterface.sorters
import spikeinterface.full as si
import  scipy.signal
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
startTime = datetime.now()
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))
''' this section defines the animal and dates and fetch the recordings from the server to Beast'''

import sys
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
nAcq = (len(dates))

if nAcq == 1:
    date=dates[0]
    runName = date.split('/')
    tempDates = dates[0].split('/')
    outDir = save_folder +  save_date + '/' + tempDates[1] + '/' + 'catgt_' + mouse + '_' + runName[1] + '_g0/'
    save_folder = outDir

if nAcq > 1:
    date = dates[0]
    runName = date.split('/')
    baseDate = runName[0]
    tempDates = dates[0].split('/')
    outDir = save_folder + baseDate + '/' + 'supercat_' + mouse + '_' + tempDates[1] + '_g0/'
    print('Final concatenated file: ')
    print(outDir)
    save_folder = outDir

import os
import subprocess
subprocess.run('ulimit -n 10000',shell=True)

#grab recordings from the server to local machine (Beast)

extensions = ['templates', 'template_metrics', 'noise_levels', 'template_similarity', 'correlograms', 'isi_histograms']
job_kwargs = dict(n_jobs=32, chunk_duration='1s', progress_bar=True)
for probe in range(int(no_probe)):
    probe0_preprocessed_corrected = si.load_extractor(save_folder+'/probe'+str(probe)+'_preprocessed')
    if use_ks4:
        probe0_sorting_ks4 = si.read_sorter_folder(save_folder + 'probe'+str(probe)+'/sorters/kilosort4')
        merge_suggestions = sio.loadmat(save_folder + 'probe'+str(probe)+'/sorters/kilosort4/sorter_output/UnitMatch/' +'um_merge_suggestion_ks4.mat')
        match_ids = merge_suggestions['match_ids']
        merge_ids = match_ids[:,1] - 1
        cs_probe0 = si.CurationSorting(probe0_sorting_ks4)
        unique_ids = np.unique(merge_ids)
        original_ids = probe0_sorting_ks4.get_unit_ids()
        for id in unique_ids:
            id_count = np.count_nonzero(merge_ids == id)
            if id_count > 1:
                unit_index = merge_ids == id
                cs_probe0.merge(original_ids[unit_index])
                
        probe0_sorting_ks4_merged = cs_probe0.sorting
        probe0_sorting_ks4_merged.save(folder = save_folder + 'probe'+str(probe)+'/sorters/kilosort4_merged/')
        probe0_we_ks4_merged = si.create_sorting_analyzer(probe0_sorting_ks4_merged, probe0_preprocessed_corrected, 
                            format = 'binary_folder',folder=save_folder +'probe'+str(probe)+'/waveform/kilosort4_merged',
                            sparse = True,overwrite = True,
                            **job_kwargs)
        probe0_we_ks4_merged.compute('random_spikes')
        probe0_we_ks4_merged.compute('waveforms',ms_before=1.0, ms_after=2.0,**job_kwargs)
        probe0_we_ks4_merged.compute(extensions,**job_kwargs)
        probe0_we_ks4_merged.compute('principal_components',**job_kwargs)
        probe0_we_ks4_merged.compute('spike_amplitudes',**job_kwargs)
        qm_list = si.get_default_qm_params()
        print(qm_list)
        probe0_we_ks4_merged.compute('quality_metrics', qm_params=qm_list,**job_kwargs)
        export_report(sorting_analyzer=probe0_we_ks4_merged, output_folder=save_folder +'probe'+str(probe)+'/report/kilosort4_merged')
        
        
    if use_ks3:
        probe0_sorting_ks3 = si.read_sorter_folder(save_folder + 'probe'+str(probe)+'/sorters/kilosort3')
        merge_suggestions = sio.loadmat(save_folder + 'probe'+str(probe)+'um_merge_suggestion_ks3.mat')
        match_ids = merge_suggestions['match_ids']
        merge_ids = match_ids[:,1] - 1
        cs_probe0 = si.CurationSorting(probe0_sorting_ks3)
        unique_ids = np.unique(merge_ids)
        original_ids = probe0_sorting_ks3.get_unit_ids()
        for id in unique_ids:
            id_count = np.count_nonzero(merge_ids == id)
            if id_count > 1:
                unit_index = merge_ids == id
                cs_probe0.merge(original_ids[unit_index])
                
        probe0_sorting_ks3_merged = cs_probe0.sorting
        probe0_sorting_ks3_merged.save(folder = save_folder + 'probe'+str(probe)+'/sorters/kilosort3_merged/')
        ''' Compute quality metrics on the extracted waveforms'''

        probe0_we_ks3_merged = si.create_sorting_analyzer(probe0_sorting_ks3_merged, probe0_preprocessed_corrected, 
                                format = 'binary_folder',folder=save_folder +'probe'+str(probe)+'/waveform/kilosort3_merged',
                                sparse = True,overwrite = True,
                                **job_kwargs)
        probe0_we_ks3_merged.compute('random_spikes')
        probe0_we_ks3_merged.compute('waveforms',ms_before=1.0, ms_after=2.0,**job_kwargs)
        probe0_we_ks3_merged.compute(extensions,**job_kwargs)
        probe0_we_ks3_merged.compute('principal_components',**job_kwargs)  
        probe0_we_ks3_merged.compute('spike_amplitudes',**job_kwargs)
        qm_list = si.get_default_qm_params()
        print('The following quality metrics are computed:')
        print(qm_list)
        probe0_we_ks3_merged.compute('quality_metrics', qm_params=qm_list,**job_kwargs)
        export_report(sorting_analyzer=probe0_we_ks3_merged, output_folder=save_folder +'probe'+str(probe)+'/report/kilosort3_merged')


    '''minor corrections to the folder path of files before moving the files to server'''
    #process to change all the folder paths in text and .json files on Beast to the server before uploading it to the server
    #import os
    #import glob

    # Define the folder list
    #folder_list = [save_folder + 'probe'+str(probe)+'_preprocessed', 
    #            save_folder + 'probe'+str(probe)+'/waveform/',
    #            save_folder + 'probe'+str(probe)+'/sorters/']

    # Initialize an empty list to store the paths of JSON files
    #json_file_list = []
   # temp_wh_files = []
    # Go through each folder in the folder list
 #   for folder in folder_list:
 #       # Recursively find all JSON files in the folder and its subfolders
 #       for json_file in glob.glob(os.path.join(folder, '**', '*.json'), recursive=True):
 #           # Append the found JSON file path to the list
 #           json_file_list.append(json_file)
 ###   for folder in folder_list:
  #      # Recursively find all JSON files in the folder and its subfolders
  #      for temp_wh_file in glob.glob(os.path.join(folder, '**', 'temp_wh.dat'), recursive=True):
  #          # Append the found JSON file path to the list
  #          temp_wh_files.append(temp_wh_file)
  #  def replace_text(obj, to_replace, replace_with):
  #      if isinstance(obj, dict):
  #          return {k: replace_text(v, to_replace, replace_with) for k, v in obj.items()}
  #      elif isinstance(obj, list):
  #          return [replace_text(elem, to_replace, replace_with) for elem in obj]
  #      elif isinstance(obj, str):
  #          return obj.replace(to_replace, replace_with)
  #      else:
  #          return obj
  #  import json

 #   for files in json_file_list:
        
        # open the JSON file and load the data
 #       with open(files, 'r') as f:
 #           data = json.load(f)
        
        # replace the text
 #       data = replace_text(data, save_folder[:-1], base_folder + mouse + '/ephys/' +save_date)
        
        # write the updated data back to the JSON file
 #       with open(files, 'w') as f:
 #           json.dump(data, f, indent=4)
            

 #   for files in temp_wh_files:
 #       os.remove(files)
    #move spikeinterface folder on Beast to the server

  ##  import shutil
   # import os

    #folders_to_move = ['probe'+str(probe),

     #               'probe'+str(probe)+'_preprocessed']
    ##
    #
    #for folder in folders_to_move:
        # construct the destination path
        #destination = os.path.join(base_folder + mouse + '/ephys/' +save_date, folder)
        # copy the folder to the destination
        #shutil.copytree(save_folder+folder, destination)
#
#remove all temmp files
#shutil.rmtree(save_folder)

print('All Done! Overall it took:')

print(datetime.now() - startTime)
print('to finish! Please move the files to the server as soon as you have time!')

sys.exit(0)