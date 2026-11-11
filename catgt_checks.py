"""Checks around CatGT and TPrime for runCatGTandTPrime.py.

CatGT runs with -prb_miss_ok and -t_miss_ok, so it skips a probe whose folder is missing and
zero-fills a missing file instead of stopping, and it reports problems only in CatGT.log (the
console shows nothing). On 2026-11-11 the server copy of M25065 20250613_0 was missing its
probe data: CatGT ran for 3 s, made no probe output, and the script then crashed with a bare
FileNotFoundError on the output folder that was never created.

These checks stop the session with a message that says what is missing:
- check_raw_acquisition, before CatGT: every gate folder has, for each probe, the AP .bin and
  .meta CatGT will read, plus the NI .bin and .meta TPrime needs, and every .bin is the size
  its .meta records (a truncated copy fails here).
- check_catgt_output, after CatGT (and supercat): each probe has a non-empty tcat AP .bin.
- check_tprime_output, after TPrime: the sync file was written.

Only the gate folders that exist are checked. runCatGTandTPrime.py asks CatGT for gates 0-1
even when only g0 was recorded, and CatGT logs the missing g1 files, which is expected.
"""

from __future__ import annotations

import glob
import os
import re
import sys

GB = 1e9


def read_meta(path: str) -> dict[str, str]:
    """Read a SpikeGLX .meta file into a dict of strings."""
    meta = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            key, sep, value = line.strip().partition("=")
            if sep:
                meta[key.lstrip("~")] = value
    return meta


def gate_folders(ephys_folder: str, run_name: str) -> dict[int, str]:
    """Gate folders <run>_g<N> in an acquisition folder, keyed by gate index."""
    pattern = re.compile(re.escape(run_name) + r"_g(\d+)$")
    gates = {}
    for name in os.listdir(ephys_folder):
        m = pattern.match(name)
        if m and os.path.isdir(os.path.join(ephys_folder, name)):
            gates[int(m.group(1))] = os.path.join(ephys_folder, name)
    return dict(sorted(gates.items()))


def _contents(folder: str, limit: int = 12) -> str:
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    if not names:
        return "(empty)"
    shown = ", ".join(names[:limit])
    return shown + (f", ... ({len(names) - limit} more)" if len(names) > limit else "")


def _check_bin_pair(bin_path: str) -> list[str]:
    """Problems with one .bin and its .meta: either missing, or the .bin not the size the .meta records."""
    meta_path = bin_path[: -len(".bin")] + ".meta"
    name = os.path.basename(bin_path)
    has_bin, has_meta = os.path.isfile(bin_path), os.path.isfile(meta_path)
    if not has_bin and not has_meta:
        return [f"missing {name} and its .meta"]
    if not has_bin:
        return [f"missing {name} (its .meta is there)"]
    if not has_meta:
        return [f"missing {os.path.basename(meta_path)}"]
    expected = read_meta(meta_path).get("fileSizeBytes")
    actual = os.path.getsize(bin_path)
    if expected is not None and expected.isdigit() and int(expected) != actual:
        return [f"{name} is {actual / GB:.2f} GB but its .meta says {int(expected) / GB:.2f} GB (incomplete copy?)"]
    return []


def check_raw_acquisition(ephys_folder: str, run_name: str, n_probes: int) -> list[str]:
    """Problems with the raw SpikeGLX data of one acquisition; an empty list means it looks complete.

    Expects the folder-per-probe layout CatGT is run with (-prb_fld) and trigger t0 (-t=0):
    <ephys_folder>/<run>_g<N>/<run>_g<N>_t0.nidq.bin and
    <ephys_folder>/<run>_g<N>/<run>_g<N>_imec<i>/<run>_g<N>_t0.imec<i>.ap.bin.
    LF files (NP1 only) are not required, but any .bin present must match its .meta.
    """
    if not os.path.isdir(ephys_folder):
        return [f"{ephys_folder} does not exist"]
    gates = gate_folders(ephys_folder, run_name)
    if not gates:
        return [f"no gate folders {run_name}_g<N> in {ephys_folder}; it contains: {_contents(ephys_folder)}"]

    problems = []
    for g, gate_dir in gates.items():
        gate_problems = []
        stem = f"{run_name}_g{g}"
        checked = set()
        nidq_bin = os.path.join(gate_dir, f"{stem}_t0.nidq.bin")
        gate_problems += _check_bin_pair(nidq_bin)
        checked.add(nidq_bin)
        for i in range(n_probes):
            probe_dir = os.path.join(gate_dir, f"{stem}_imec{i}")
            if not os.path.isdir(probe_dir):
                gate_problems.append(f"no probe folder {stem}_imec{i}")
                continue
            ap_bin = os.path.join(probe_dir, f"{stem}_t0.imec{i}.ap.bin")
            gate_problems += [f"imec{i}: {p}" for p in _check_bin_pair(ap_bin)]
            checked.add(ap_bin)
        # any other .bin (LF, extra triggers) must still match its .meta
        for bin_path in glob.glob(os.path.join(gate_dir, "**", "*.bin"), recursive=True):
            if bin_path not in checked:
                gate_problems += _check_bin_pair(bin_path)
        if gate_problems:
            problems += [f"{stem}: {p}" for p in gate_problems]
            problems.append(f"{stem} contains: {_contents(gate_dir)}")

    missing_gates = sorted(set(range(min(gates), max(gates) + 1)) - set(gates))
    if missing_gates:
        # not an error by itself (a bad gate may have been deleted on purpose), but say so
        print(f"WARNING: {run_name} has no folder for gate(s) {missing_gates}; CatGT will join the "
              f"other gates with a short gap where they were.")
    return problems


def check_catgt_output(folder: str, n_probes: int) -> list[str]:
    """Problems with a CatGT (or supercat) output folder: each probe needs a non-empty tcat AP .bin."""
    if not os.path.isdir(folder):
        return [f"CatGT made no output folder {folder}"]
    problems = []
    for i in range(n_probes):
        bins = glob.glob(os.path.join(folder, "**", f"*_tcat.imec{i}.ap.bin"), recursive=True)
        if not bins:
            problems.append(f"no *_tcat.imec{i}.ap.bin in {folder}; it contains: {_contents(folder)}")
        problems += [f"{b} is empty" for b in bins if os.path.getsize(b) == 0]
    return problems


def check_tprime_output(sync_file: str) -> list[str]:
    if not os.path.isfile(sync_file):
        return [f"TPrime wrote no {sync_file}"]
    return []


def wait_all(procs, tool: str) -> None:
    """Wait for subprocesses and print a warning for any non-zero exit code.

    The exit code is only reported: whether CatGT and TPrime exit non-zero on every error is not
    documented, so the output checks above are what stop the session.
    """
    for p in procs:
        code = p.wait()
        if code != 0:
            print(f"WARNING: {tool} exited with code {code}: {' '.join(map(str, p.args))}")


def stop_if_problems(problems: list[str], what: str, log_hint: str = "") -> None:
    """Print the problems to stderr and exit with status 1, so the batch script stops."""
    if not problems:
        return
    lines = [f"ERROR: {what}"] + [f"  - {p}" for p in problems]
    if log_hint:
        lines.append(log_hint)
    print("\n".join(lines), file=sys.stderr, flush=True)
    sys.exit(1)
