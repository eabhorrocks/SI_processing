"""Tests for bad_channels.py on synthetic probes (CPU only, a few seconds each).

Run from the repo root:  python -m pytest tests -p no:cacheprovider

White noise of variance v has a one-sided PSD of v / (fs / 2), so per-channel noise of
10 uV plus 8 uV of common-mode signal gives ~0.011 uV^2/Hz above 12 kHz, as in a clean
M26018 recording, and 21.5 uV gives ~0.035, as in its noisy g4 file.
"""

import json
import sys
from pathlib import Path

import numpy as np
import probeinterface as pi
import pytest
import spikeinterface.full as si

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bad_channels import relative_noise_channels, select_bad_channels  # noqa: E402

FS = 30000.0
N_CH = 128
CLEAN_UV, NOISY_UV = 10.0, 21.5
CHUNKS = 30


def make_recording(sigma, dead=(5,), overrides=None, duration_s=4.0, common_uv=8.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(FS * duration_s)
    sig = np.full(N_CH, sigma, dtype=np.float32)
    for ch, s in (overrides or {}).items():
        sig[ch] = s
    common = rng.normal(0, common_uv, n).astype(np.float32)[:, None]
    x = rng.normal(size=(n, N_CH)).astype(np.float32) * sig + common
    for ch in dead:  # no shared signal and almost no noise
        x[:, ch] = rng.normal(0, 0.5, n)
    rec = si.NumpyRecording([x], sampling_frequency=FS)
    probe = pi.generate_multi_columns_probe(num_columns=2, num_contact_per_column=N_CH // 2, xpitch=32, ypitch=20)
    probe.set_device_channel_indices(np.arange(N_CH))
    with_probe = rec.set_probe(probe)  # returns a new recording in older SI, None (in place) in 0.105
    rec = with_probe if with_probe is not None else rec
    rec.set_channel_gains(1.0)
    rec.set_channel_offsets(0.0)
    return si.highpass_filter(rec, freq_min=300)


def removed(bad, rec):
    """Removed channels as indices, whatever type the channel ids are."""
    ids = list(rec.channel_ids)
    return {ids.index(c) for c in bad}


def test_clean_probe_removes_only_dead_channel():
    rec = make_recording(CLEAN_UV)
    bad, report = select_bad_channels(rec, mode="auto", num_random_chunks=CHUNKS)
    assert removed(bad, rec) == {5}
    assert report["label_counts"].get("noise", 0) == 0
    assert 0.008 < report["median_psd_hf_uv2_per_hz"] < 0.014


def test_uniformly_noisy_probe_si_default_removes_almost_everything():
    """The failure seen in M26018 20260622: the whole probe crosses SI's fixed threshold."""
    rec = make_recording(NOISY_UV)
    bad, _ = select_bad_channels(rec, mode="si_default", num_random_chunks=CHUNKS)
    assert len(bad) > 0.9 * N_CH


def test_uniformly_noisy_probe_auto_keeps_the_probe():
    rec = make_recording(NOISY_UV)
    bad, report = select_bad_channels(rec, mode="auto", num_random_chunks=CHUNKS)
    assert removed(bad, rec) == {5}
    assert report["channels_over_si_threshold"] > 0.9 * N_CH
    assert not report["noise_guard_applied"]


def test_auto_still_finds_individual_noisy_channels_on_a_noisy_probe():
    rec = make_recording(NOISY_UV, overrides={20: 4 * NOISY_UV, 70: 4 * NOISY_UV})
    bad, report = select_bad_channels(rec, mode="auto", num_random_chunks=CHUNKS)
    assert removed(bad, rec) == {5, 20, 70}
    assert report["labels"][str(rec.channel_ids[20])] == "noise"


def test_guard_keeps_noise_channels_when_too_many_are_flagged():
    many = {ch: 4 * CLEAN_UV for ch in range(40, 70)}  # 30 of 128 channels, over 10%
    rec = make_recording(CLEAN_UV, overrides=many)
    bad, report = select_bad_channels(rec, mode="auto", num_random_chunks=CHUNKS)
    assert removed(bad, rec) == {5}
    assert report["noise_guard_applied"]
    assert report["label_counts"]["noise"] == 30
    assert report["warnings"]


def test_dead_out_ignores_noise():
    rec = make_recording(NOISY_UV, overrides={20: 4 * NOISY_UV})
    bad, _ = select_bad_channels(rec, mode="dead_out", num_random_chunks=CHUNKS)
    assert removed(bad, rec) == {5}


def test_none_removes_nothing():
    rec = make_recording(NOISY_UV)
    bad, report = select_bad_channels(rec, mode="none")
    assert len(bad) == 0
    assert report["num_kept"] == N_CH
    assert set(report["labels"].values()) == {"not_checked"}


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        select_bad_channels(make_recording(CLEAN_UV), mode="off")


def test_report_is_json_serialisable():
    rec = make_recording(CLEAN_UV)
    _, report = select_bad_channels(rec, mode="auto", num_random_chunks=CHUNKS)
    json.dumps(report)


def test_relative_threshold_never_below_si_floor():
    # Quiet probe (median 0.004): a channel at 0.015 is 3.75x the median but under SI's 0.02,
    # so it is not flagged; one at 0.05 is.
    psd = np.full((10, 6), 0.004)
    psd[:, 1] = 0.015
    psd[:, 2] = 0.05
    assert list(np.flatnonzero(relative_noise_channels(psd, factor=2.0))) == [2]
