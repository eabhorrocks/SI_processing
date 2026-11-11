"""Tests for catgt_checks.py and its use in runCatGTandTPrime.py, on fake SpikeGLX folders.

The script tests run runCatGTandTPrime.py with small Python stand-ins for CatGT and TPrime, so
they need no CatGT install. Run from the repo root:  python -m pytest tests -p no:cacheprovider
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from catgt_checks import check_catgt_output, check_raw_acquisition  # noqa: E402

MOUSE, DAY, ACQ = "M1", "20250613", "20250613_0"
RUN = f"{MOUSE}_{ACQ}"


def write_pair(bin_path: Path, n_bytes: int = 64, meta_bytes=None, meta=True, data=True):
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    if data:
        bin_path.write_bytes(b"\0" * n_bytes)
    if meta:
        size = n_bytes if meta_bytes is None else meta_bytes
        bin_path.with_suffix(".meta").write_text(f"nSavedChans=385\nfileSizeBytes={size}\n~snsGeomMap=(x)\n")


def make_acquisition(acq: Path, gates=(0,), probes=(0,), lf=False, nidq=True):
    for g in gates:
        gate = acq / f"{RUN}_g{g}"
        gate.mkdir(parents=True, exist_ok=True)
        if nidq:
            write_pair(gate / f"{RUN}_g{g}_t0.nidq.bin")
        for i in probes:
            probe = gate / f"{RUN}_g{g}_imec{i}"
            write_pair(probe / f"{RUN}_g{g}_t0.imec{i}.ap.bin")
            if lf:
                write_pair(probe / f"{RUN}_g{g}_t0.imec{i}.lf.bin", n_bytes=16)
    return acq


def test_complete_acquisition_passes(tmp_path):
    acq = make_acquisition(tmp_path / ACQ, gates=(0, 1, 2), probes=(0, 1), lf=True)
    assert check_raw_acquisition(str(acq), RUN, n_probes=2) == []


def test_missing_probe_folder_reported_with_contents(tmp_path):
    # M25065 20250613_0 on 2026-11-11: the gate folder had no imec0 folder
    acq = make_acquisition(tmp_path / ACQ, probes=())
    problems = check_raw_acquisition(str(acq), RUN, n_probes=1)
    assert any(f"no probe folder {RUN}_g0_imec0" in p for p in problems)
    assert any("contains:" in p and f"{RUN}_g0_t0.nidq.bin" in p for p in problems)


def test_second_probe_missing(tmp_path):
    acq = make_acquisition(tmp_path / ACQ, probes=(0,))
    problems = check_raw_acquisition(str(acq), RUN, n_probes=2)
    assert any("imec1" in p for p in problems) and not any("imec0:" in p for p in problems)


@pytest.mark.parametrize("damage, expected", [
    (lambda ap: ap.unlink(), "missing"),
    (lambda ap: ap.with_suffix(".meta").unlink(), "missing"),
    (lambda ap: ap.write_bytes(b"\0" * 10), "incomplete copy"),
])
def test_damaged_ap_file(tmp_path, damage, expected):
    acq = make_acquisition(tmp_path / ACQ, gates=(0, 1))
    damage(acq / f"{RUN}_g1" / f"{RUN}_g1_imec0" / f"{RUN}_g1_t0.imec0.ap.bin")
    problems = check_raw_acquisition(str(acq), RUN, n_probes=1)
    assert any(p.startswith(f"{RUN}_g1: imec0: ") and expected in p for p in problems), problems
    assert not any(p.startswith(f"{RUN}_g0:") for p in problems)


def test_missing_nidq_and_truncated_lf(tmp_path):
    acq = make_acquisition(tmp_path / ACQ, lf=True, nidq=False)
    (acq / f"{RUN}_g0" / f"{RUN}_g0_imec0" / f"{RUN}_g0_t0.imec0.lf.bin").write_bytes(b"\0")
    problems = check_raw_acquisition(str(acq), RUN, n_probes=1)
    assert any(f"missing {RUN}_g0_t0.nidq.bin and its .meta" in p for p in problems)
    assert any("lf.bin" in p and "incomplete copy" in p for p in problems)


def test_no_gate_folders(tmp_path):
    acq = tmp_path / ACQ
    acq.mkdir()
    (acq / "notes.txt").write_text("x")
    problems = check_raw_acquisition(str(acq), RUN, n_probes=1)
    assert len(problems) == 1 and "no gate folders" in problems[0] and "notes.txt" in problems[0]
    assert "does not exist" in check_raw_acquisition(str(tmp_path / "nope"), RUN, 1)[0]


def test_gate_gap_warns_only(tmp_path, capsys):
    acq = make_acquisition(tmp_path / ACQ, gates=(0, 2))
    assert check_raw_acquisition(str(acq), RUN, n_probes=1) == []
    assert "gate(s) [1]" in capsys.readouterr().out


def test_catgt_output(tmp_path):
    out = tmp_path / f"catgt_{RUN}_g0"
    assert "no output folder" in check_catgt_output(str(out), 1)[0]
    out.mkdir()
    assert "no *_tcat.imec0.ap.bin" in check_catgt_output(str(out), 1)[0]
    write_pair(out / f"{RUN}_g0_imec0" / f"{RUN}_g0_tcat.imec0.ap.bin")
    assert check_catgt_output(str(out), 1) == []
    write_pair(out / f"{RUN}_g0_imec1" / f"{RUN}_g0_tcat.imec1.ap.bin", n_bytes=0)
    assert "is empty" in check_catgt_output(str(out), 2)[0]


# --- runCatGTandTPrime.py with stand-ins for CatGT and TPrime ---

FAKE_CATGT = r'''
import sys
from pathlib import Path
args = dict(a.split("=", 1) for a in sys.argv[1].split() if "=" in a)
Path("catgt_called").write_text(sys.argv[1])
if "{mode}" == "nothing":
    sys.exit(0)
out = Path(args["-dest"]) / ("catgt_" + args["-run"] + "_g0")
probe = out / (args["-run"] + "_g0_imec0")
probe.mkdir(parents=True)
(probe / (args["-run"] + "_g0_tcat.imec0.ap.bin")).write_bytes(b"\0" * 8)
(probe / (args["-run"] + "_g0_tcat.imec0.ap.xd_384_6_500.txt")).write_text("0.1\n")
(out / (args["-run"] + "_g0_tcat.nidq.xd_8_3_500.txt")).write_text("0.1\n")
'''

FAKE_TPRIME = r'''
import sys
from pathlib import Path
args = sys.argv[1].split()
Path("tprime_called").write_text(sys.argv[1])
if "{mode}" == "write":
    events = [a for a in args if a.startswith("-events=")][0]
    Path(events.split(",")[-1]).write_text("0.1\n")
'''


def run_script(tmp_path: Path, catgt_mode="ok", tprime_mode="write", probes=(0,)):
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "catgt.py").write_text(FAKE_CATGT.replace("{mode}", catgt_mode))
    (tools / "tprime.py").write_text(FAKE_TPRIME.replace("{mode}", tprime_mode))
    base = tmp_path / "temp_data"
    make_acquisition(base / MOUSE / DAY / ACQ, probes=probes)
    py = Path(sys.executable).as_posix()
    cmd = [sys.executable, str(REPO / "runCatGTandTPrime.py"), MOUSE, f"{DAY}/{ACQ}", DAY,
           base.as_posix() + "/", "1", "true", "false", "/server/SUBJECTS/",
           f"{py} {(tools / 'catgt.py').as_posix()}", f"{py} {(tools / 'tprime.py').as_posix()}"]
    work = tmp_path / "work"
    work.mkdir()
    proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    return proc, work, base


def test_script_stops_before_catgt_when_probe_data_missing(tmp_path):
    proc, work, _ = run_script(tmp_path, probes=())
    assert proc.returncode == 1
    assert "incomplete, so CatGT was not run" in proc.stderr
    assert f"no probe folder {RUN}_g0_imec0" in proc.stderr
    assert "/server/SUBJECTS/M1/ephys/20250613/20250613_0/" in proc.stderr
    assert not (work / "catgt_called").exists()


def test_script_stops_when_catgt_makes_nothing(tmp_path):
    proc, work, _ = run_script(tmp_path, catgt_mode="nothing")
    assert proc.returncode == 1
    assert (work / "catgt_called").exists()
    assert "CatGT did not make the expected output" in proc.stderr
    assert "CatGT.log" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_script_stops_when_tprime_writes_nothing(tmp_path):
    proc, work, base = run_script(tmp_path, tprime_mode="nothing")
    assert proc.returncode == 1, proc.stderr
    assert (work / "tprime_called").exists()
    assert "TPrime did not write the NI sync file" in proc.stderr
    assert (base / MOUSE / DAY / "CatGToutput" / f"{RUN}_g0_tcat.imec0.ap.bin").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="the script's final file moves split paths on '/'")
def test_script_completes(tmp_path):
    proc, _, base = run_script(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (base / MOUSE / DAY / "nidq_processed" / "nidq_sync_tprime.txt").exists()
