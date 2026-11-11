"""Tests for sorting_metrics.py on a small synthetic analyzer (CPU only, seconds)."""

import sys
from pathlib import Path

import pytest
import spikeinterface.full as si

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sorting_metrics import compute_analyzer_extensions  # noqa: E402

PCA_COLUMNS = {"isolation_distance", "l_ratio", "d_prime", "nn_hit_rate", "nn_miss_rate", "silhouette"}
JOB_KWARGS = dict(n_jobs=1, chunk_duration="1s", progress_bar=False)


@pytest.fixture(scope="module")
def recording_and_sorting():
    return si.generate_ground_truth_recording(durations=[20.0], num_channels=16, num_units=5, seed=0)


def _analyzer(recording_and_sorting):
    recording, sorting = recording_and_sorting
    return si.create_sorting_analyzer(sorting, recording, format="memory", sparse=True)


def test_default_skips_pca(recording_and_sorting):
    analyzer = compute_analyzer_extensions(_analyzer(recording_and_sorting), JOB_KWARGS)
    assert not analyzer.has_extension("principal_components")
    columns = set(analyzer.get_extension("quality_metrics").get_data().columns)
    assert not PCA_COLUMNS & columns
    # what bombcell and the MATLAB analysis read is still there
    assert {"num_spikes", "presence_ratio", "snr", "amplitude_median", "amplitude_cutoff",
            "rp_contamination", "isi_violations_ratio", "firing_rate"} <= columns
    assert analyzer.has_extension("template_metrics") and analyzer.has_extension("spike_amplitudes")


def test_extensions_spikepost_needs(recording_and_sorting):
    """spike_locations (and so the drift metrics) are computed while the recording exists,
    and the parameters match spikepost's defaults so it does not recompute them."""
    analyzer = compute_analyzer_extensions(_analyzer(recording_and_sorting), JOB_KWARGS)
    assert analyzer.get_extension("spike_locations").params["method"] == "center_of_mass"
    assert len(analyzer.get_extension("spike_locations").get_data()) == analyzer.sorting.count_total_num_spikes()
    assert "drift_ptp" in analyzer.get_extension("quality_metrics").get_data().columns
    for name in ("correlograms", "isi_histograms"):
        params = analyzer.get_extension(name).params
        assert (params["window_ms"], params["bin_ms"]) == (100.0, 1.0)
    assert analyzer.get_extension("unit_locations").params["method"] == "monopolar_triangulation"


def test_pca_metrics_on(recording_and_sorting):
    analyzer = compute_analyzer_extensions(_analyzer(recording_and_sorting), JOB_KWARGS, pca_metrics=True)
    assert analyzer.has_extension("principal_components")
    assert {"isolation_distance", "l_ratio"} <= set(analyzer.get_extension("quality_metrics").get_data().columns)
