"""Bad-channel selection used by preprocessProbes.py.

SpikeInterface's default detector ('coherence+psd', from IBL) calls a channel 'noise' when
its mean power above 0.8 x Nyquist (12 kHz for AP data) is over a fixed 0.02 uV^2/Hz, then
takes a majority vote over random chunks. When the whole probe gets noisier, every channel
crosses that line and the vote removes nearly the whole probe. This happened in M26018
20260622_0: high-frequency power went from ~0.011 (g0-g2) to 0.025-0.035 uV^2/Hz (g3
onwards) on all channels at once, and only 31 of 384 channels were kept.

Mode 'auto' keeps SI's dead / outside-brain / low-coherence labels but makes the power test
relative: a channel is noisy only where its high-frequency power is more than `factor` times
the probe median in the same chunk. The threshold never drops below SI's 0.02, so on a clean
recording this flags no more channels than SI does; it only becomes more lenient when the
whole probe is noisy. As a backstop, if more than `max_noise_fraction` of the channels would
still be removed as noise, none are removed for noise and the report says so.

Modes
-----
auto        relative power test + guard (default)
si_default  SpikeInterface defaults, no guard (the behaviour before this module)
dead_out    remove only dead and outside-brain channels
none        remove nothing and skip detection
"""

from __future__ import annotations

import numpy as np
import spikeinterface
import spikeinterface.full as si
from scipy.signal import welch

MODES = ("auto", "si_default", "dead_out", "none")
SI_PSD_HF_THRESHOLD = 0.02  # uV^2/Hz, SpikeInterface's default psd_hf_threshold


def check_mode(mode: str) -> str:
    if mode not in MODES:
        raise ValueError(f"bad channel mode must be one of {MODES}, got {mode!r}")
    return mode


def _traces_uv(recording, start: int, end: int, segment_index: int) -> np.ndarray:
    kwargs = dict(start_frame=start, end_frame=end, segment_index=segment_index)
    try:
        traces = recording.get_traces(return_in_uV=True, **kwargs)  # SI >= 0.103
    except TypeError:
        traces = recording.get_traces(return_scaled=True, **kwargs)
    return traces.astype(np.float64)


def _random_chunk_starts(recording, num_chunks: int, chunk_size: int, seed: int):
    """(segment_index, start_frame) pairs, spread over segments by their length."""
    rng = np.random.default_rng(seed)
    lengths = np.array([recording.get_num_samples(s) for s in range(recording.get_num_segments())])
    usable = np.clip(lengths - chunk_size, 0, None)
    if usable.sum() == 0:
        raise ValueError(f"recording is shorter than one {chunk_size}-sample chunk")
    segments = rng.choice(len(lengths), size=num_chunks, p=usable / usable.sum())
    return [(int(s), int(rng.integers(0, usable[s] + 1))) for s in segments]


def high_freq_power(
    recording,
    num_chunks: int = 100,
    chunk_duration_s: float = 0.3,
    nyquist_threshold: float = 0.8,
    welch_window_ms: float = 10.0,
    seed: int = 0,
) -> np.ndarray:
    """Mean PSD above `nyquist_threshold` x Nyquist for each random chunk and channel, in
    uV^2/Hz, computed as SpikeInterface's IBL detector does. Shape (num_chunks, num_channels).
    `recording` should already be high-pass filtered."""
    fs = recording.sampling_frequency
    chunk_size = int(chunk_duration_s * fs)
    nperseg = int(welch_window_ms * fs / 1000)
    out = []
    for segment_index, start in _random_chunk_starts(recording, num_chunks, chunk_size, seed):
        x = _traces_uv(recording, start, start + chunk_size, segment_index)
        x -= x.mean(axis=0, keepdims=True)
        f, psd = welch(x, fs=fs, axis=0, window="hann", nperseg=nperseg)
        out.append(psd[f > fs / 2 * nyquist_threshold].mean(axis=0))
    return np.array(out)


def relative_noise_channels(psd_hf: np.ndarray, factor: float, floor: float = SI_PSD_HF_THRESHOLD):
    """Channels whose power is above max(floor, factor x chunk median) in more than half of
    the chunks (the same majority vote SpikeInterface uses)."""
    thresholds = np.maximum(floor, factor * np.median(psd_hf, axis=1, keepdims=True))
    return (psd_hf > thresholds).mean(axis=0) > 0.5


def select_bad_channels(
    recording,
    mode: str = "auto",
    factor: float = 2.0,
    max_noise_fraction: float = 0.1,
    num_random_chunks: int = 100,
    seed: int = 0,
):
    """Return (bad_channel_ids, report). `recording` should already be high-pass filtered.
    `report` is JSON-serialisable and records every label and decision."""
    check_mode(mode)
    channel_ids = recording.channel_ids
    n = len(channel_ids)
    report = {
        "mode": mode,
        "spikeinterface_version": spikeinterface.__version__,
        "num_channels": n,
        "params": {
            "factor": factor,
            "psd_hf_floor_uv2_per_hz": SI_PSD_HF_THRESHOLD,
            "max_noise_fraction": max_noise_fraction,
            "num_random_chunks": num_random_chunks,
            "seed": seed,
        },
        "noise_guard_applied": False,
        "warnings": [],
    }

    if mode == "none":
        bad = np.array([], dtype=channel_ids.dtype)
        labels = np.array(["not_checked"] * n)
    elif mode == "si_default":
        bad, labels = si.detect_bad_channels(recording, num_random_chunks=num_random_chunks, seed=seed)
    else:
        # SI's detector with its absolute power test switched off: dead, outside-brain and
        # low-coherence ('noise' via xcorr) labels only.
        _, labels = si.detect_bad_channels(
            recording, psd_hf_threshold=np.inf, num_random_chunks=num_random_chunks, seed=seed
        )
        labels = np.asarray(labels).astype("<U16")
        if mode == "auto":
            psd_hf = high_freq_power(recording, num_chunks=num_random_chunks, seed=seed)
            noisy = relative_noise_channels(psd_hf, factor=factor)
            labels[(labels == "good") & noisy] = "noise"
            channel_psd = np.median(psd_hf, axis=0)
            report["median_psd_hf_uv2_per_hz"] = float(np.median(channel_psd))
            report["psd_hf_uv2_per_hz"] = {str(c): float(p) for c, p in zip(channel_ids, channel_psd)}
            report["channels_over_si_threshold"] = int((channel_psd > SI_PSD_HF_THRESHOLD).sum())
        remove = np.isin(labels, ["dead", "out"])
        is_noise = labels == "noise"
        if mode == "auto":
            if is_noise.sum() > max_noise_fraction * n:
                report["noise_guard_applied"] = True
                report["warnings"].append(
                    f"{int(is_noise.sum())} of {n} channels labelled noise (> {max_noise_fraction:.0%}); "
                    "kept them and removed only dead and outside-brain channels"
                )
            else:
                remove |= is_noise
        bad = channel_ids[remove]

    labels = np.asarray(labels).astype(str)
    bad = np.asarray(bad)
    report["labels"] = {str(c): str(lab) for c, lab in zip(channel_ids, labels)}
    names, counts = np.unique(labels, return_counts=True)
    report["label_counts"] = {str(k): int(v) for k, v in zip(names, counts)}
    report["removed_channel_ids"] = [str(c) for c in bad]
    report["num_removed"] = int(len(bad))
    report["num_kept"] = int(n - len(bad))
    if report["num_kept"] < n / 2:
        report["warnings"].append(f"only {report['num_kept']} of {n} channels kept")
    return bad, report


def summary(report: dict) -> str:
    lines = [
        f"bad channels ({report['mode']}): removed {report['num_removed']} of {report['num_channels']}, "
        f"labels {report['label_counts']}"
    ]
    if "median_psd_hf_uv2_per_hz" in report:
        lines.append(
            f"  probe median high-freq power {report['median_psd_hf_uv2_per_hz']:.4f} uV^2/Hz; "
            f"{report['channels_over_si_threshold']} channels over SI's fixed {SI_PSD_HF_THRESHOLD}"
        )
    lines += [f"  WARNING: {w}" for w in report["warnings"]]
    return "\n".join(lines)
