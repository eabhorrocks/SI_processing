from spikeinterface_gui import run_mainwindow
import spikeinterface.full as si
import spikeinterface.widgets as sw

# reload the SortingAnalyzer
 
sorting_analyzer = si.load_sorting_analyzer("/home/saleem_lab/si_edd/temp_data/M25065/20250606/SpikeSorting/probe0/sorters/kilosort4/metrics")
run_mainwindow(sorting_analyzer, curation=False)
