"""Analyzer extensions computed after sorting (used by runSpikeSorting.py).

PCA-based quality metrics are off by default. On the sorting machine (SI 0.103, M26018
20260617, 794 units) quality metrics took 59 min and the principal_components extension 12
min, against 9 min for Kilosort 4. In SI 0.105 the PCA metrics were 85% of the quality
metric time (nearest_neighbor alone 51%), and none of them changes bombcell labels:
isolation_distance > 20 failed for 21 of 23,346 somatic units in the spikepost survey.
Set `pca_metrics=True` to compute principal_components and the PCA metrics
(isolation_distance, l_ratio, d_prime, nn_hit_rate, nn_miss_rate, silhouette) again.

spike_locations is computed here because this is the last time the recording is available.
The preprocessed binary (~80 GB per hour of Neuropixels data) and the CatGT output are not
uploaded, so spikepost cannot compute it later, and without it bombcell drops its drift
threshold (drift_ptp). Computing it before quality_metrics also adds the drift metrics here.

The parameters match spikepost's configs/default.yaml (correlogram and ISI windows, location
methods), so spikepost reuses these extensions instead of recomputing them.
"""

from __future__ import annotations

EXTENSIONS = {
    "templates": {},
    "template_metrics": {},
    "noise_levels": {},
    "template_similarity": {},
    "correlograms": {"window_ms": 100.0, "bin_ms": 1.0},
    "isi_histograms": {"window_ms": 100.0, "bin_ms": 1.0},
    "unit_locations": {"method": "monopolar_triangulation"},
}
SPIKE_LOCATIONS = {"method": "center_of_mass"}


def compute_analyzer_extensions(analyzer, job_kwargs: dict, pca_metrics: bool = False):
    analyzer.compute("random_spikes")
    analyzer.compute("waveforms", ms_before=1.0, ms_after=2.0, **job_kwargs)
    analyzer.compute(EXTENSIONS, **job_kwargs)
    if pca_metrics:
        analyzer.compute("principal_components", **job_kwargs)
    analyzer.compute("spike_amplitudes", **job_kwargs)
    analyzer.compute("spike_locations", **SPIKE_LOCATIONS, **job_kwargs)
    # Default parameters for every metric; skip_pc_metrics drops the PCA-based ones.
    analyzer.compute("quality_metrics", skip_pc_metrics=not pca_metrics, **job_kwargs)
    columns = list(analyzer.get_extension("quality_metrics").get_data().columns)
    print(f"Quality metrics computed (pca_metrics={pca_metrics}):", columns)
    return analyzer
