import pandas as pd
import numpy as np

def save_spikes_to_csv(spikes, save_folder):
    unit_index = spikes['unit_index']
    segment_index = spikes['segment_index']
    sample_index = spikes['sample_index']
    spikes_df = pd.DataFrame({'unit_index': unit_index, 'segment_index': segment_index, 'sample_index': sample_index})
    spikes_df.to_csv(save_folder + 'spikes.csv', index=False)

save_folder = 'Z:/ibn-vision/DATA/SUBJECTS/M24077/ephys/20241219/Processed_1/spike_sorting/probe0/sorters/kilosort4_merged/'
spikes_file = save_folder + 'spikes.npy'

spikes_npy = np.load(spikes_file)
save_spikes_to_csv(spikes_npy,save_folder)