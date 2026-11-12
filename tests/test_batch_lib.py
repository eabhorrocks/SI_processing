"""Tests for batch_lib.sh: entry parsing, deleting only the sorted session's local copy, and
carrying on past a failed session.

On Windows the bash on PATH may be WSL's, so these skip there unless SI_TEST_BASH points to
Git Bash, e.g.  set SI_TEST_BASH=C:\\Program Files\\Git\\bin\\bash.exe
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WINDOWS = sys.platform == "win32"
LIB = Path(__file__).resolve().parents[1] / "batch_lib.sh"
BASH = os.environ.get("SI_TEST_BASH") or (None if WINDOWS else shutil.which("bash"))
pytestmark = pytest.mark.skipif(BASH is None, reason="needs a POSIX bash (on Windows, set SI_TEST_BASH)")


def _sh_path(value) -> str:
    return str(value).replace("\\", "/") if WINDOWS else str(value)


def run(script: str, **env) -> subprocess.CompletedProcess:
    prelude = f"set -e\nsource '{_sh_path(LIB)}'\n" + "".join(f"{k}='{_sh_path(v)}'\n" for k, v in env.items())
    return subprocess.run([BASH, "-c", prelude + script], capture_output=True, text=True)


def parsed(entry: str, **env) -> dict:
    out = run(f'parse_entry "{entry}"\necho "$mouse|$dates|$save_date|$session_probes|$session_bad_channel_mode"', **env)
    assert out.returncode == 0, out.stderr
    mouse, dates, save_date, probes, mode = out.stdout.strip().split("|")
    return dict(mouse=mouse, dates=dates, save_date=save_date, probes=probes, mode=mode)


def test_parse_defaults_and_options():
    assert parsed("M25104 20250922/20250922_0", no_probe=1, bad_channel_mode="auto") == dict(
        mouse="M25104", dates="20250922/20250922_0", save_date="20250922", probes="1", mode="auto")
    p = parsed("M25066  20250617/20250617_0,20250617/20250617_1 probes=2 bad_channels=none")
    assert (p["dates"], p["probes"], p["mode"]) == ("20250617/20250617_0,20250617/20250617_1", "2", "none")


@pytest.mark.parametrize("entry", [
    "20250922/20250922_0",                      # no mouse
    "M25104 20250922",                          # no acquisition
    "../x 20250922/20250922_0",                 # path in the mouse name
    "M25104 20250922/20250922_0 probes=0",
    "M25104 20250922/20250922_0 bad_channels=nope",
    "M25104 20250922/20250922_0 bad_channel=auto",  # unknown option
])
def test_bad_entries_rejected(entry):
    assert run(f'parse_entry "{entry}"').returncode == 1


def test_check_entries_reports_all_then_fails():
    out = run('check_entries "M1 20250101/20250101_0" "M2 20250101" "M3 20250101/20250101_0 x=1"')
    assert out.returncode == 1
    assert "M2 20250101" in out.stderr and "x=1" in out.stderr


def test_delete_only_this_session(tmp_path):
    base = tmp_path / "temp_data"
    for d in ["M1/20250101/20250101_0", "M1/20250102/20250102_0", "M2/20250101/20250101_0"]:
        (base / d).mkdir(parents=True)
        (base / d / "f.bin").write_text("x")
    out = run('parse_entry "M1 20250101/20250101_0"\ndelete_local_session', base_folder=f"{base}/")
    assert out.returncode == 0, out.stderr
    assert not (base / "M1" / "20250101").exists()
    assert (base / "M1" / "20250102" / "20250102_0" / "f.bin").exists()  # same mouse, other day
    assert (base / "M2" / "20250101" / "20250101_0" / "f.bin").exists()  # other mouse, same day

    out = run('parse_entry "M1 20250102/20250102_0"\ndelete_local_session', base_folder=str(base))
    assert out.returncode == 0, out.stderr
    assert not (base / "M1").exists()  # empty mouse folder removed
    assert (base / "M2").exists()


def test_delete_covers_every_acquisition_day(tmp_path):
    base = tmp_path / "temp_data"
    for d in ["M1/20250101/20250101_0", "M1/20250102/20250102_0"]:
        (base / d).mkdir(parents=True)
    out = run('parse_entry "M1 20250101/20250101_0,20250102/20250102_0"\ndelete_local_session', base_folder=str(base))
    assert out.returncode == 0, out.stderr
    assert not (base / "M1").exists()


def test_delete_refuses_root():
    out = run('parse_entry "M1 20250101/20250101_0"\ndelete_local_session', base_folder="/")
    assert out.returncode == 1 and "Refusing" in out.stderr


# --- carrying on past a failed session ---

def test_run_session_stops_at_first_failing_step_and_returns():
    out = run(
        'steps() { echo one; false; echo two; }\n'
        'run_session steps\n'
        'echo "status=$session_status error=$session_error"\n'
        'ok() { echo fine; }\n'
        'run_session ok\n'
        'echo "status=$session_status error=$session_error"\n'
    )
    assert out.returncode == 0, out.stderr
    assert "one" in out.stdout and "two" not in out.stdout
    assert "status=1 error=no error output" in out.stdout
    assert "fine\nstatus=0 error=\n" in out.stdout


@pytest.mark.parametrize("stderr_text, expected", [
    # runCatGTandTPrime.py's check, after progress-bar text ending in a carriage return
    ("loading 10%\rloading 90%\rERROR: the raw data for M1 is incomplete, so CatGT was not run:\n"
     "  - M1_20250101_0_g0: no probe folder M1_20250101_0_g0_imec0\n  - other\n",
     "ERROR: the raw data for M1 is incomplete, so CatGT was not run: M1_20250101_0_g0: no probe folder M1_20250101_0_g0_imec0"),
    ('Traceback (most recent call last):\n  File "x.py", line 1, in <module>\n'
     "FileNotFoundError: [Errno 2] No such file or directory: 'y'\n",
     "FileNotFoundError: [Errno 2] No such file or directory: 'y'"),
    ("bash: python: command not found\n\n", "bash: python: command not found"),
])
def test_session_error_line(tmp_path, stderr_text, expected):
    err = tmp_path / "stderr.txt"
    err.write_bytes(stderr_text.encode())
    out = run('steps() { cat "$err_file" >&2; return 3; }\nrun_session steps\necho "[$session_status] $session_error"',
              err_file=err)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == f"[3] {expected}"
    assert "not run" in out.stderr or "Error" in out.stderr or "not found" in out.stderr  # still shown


def test_failed_session_set_aside_and_batch_continues(tmp_path):
    """A failed session's files move to _failed/, so a later session from the same day starts
    clean; the batch runs every session and fails at the end, listing the failure."""
    base = tmp_path / "temp_data"
    script = r'''
SESSIONS=("M1 20250101/20250101_0" "M1 20250101/20250101_1" "M2 20250102/20250102_0")
steps() {
    local day_dir="${base_folder%/}/$mouse/$save_date"
    mkdir -p "$day_dir/${dates#*/}" "$day_dir/CatGToutput"
    if [[ -e $day_dir/CatGToutput/from_failed_session.bin ]]; then echo LEAK; return 9; fi
    if [[ $dates == */20250101_0 ]]; then
        touch "$day_dir/CatGToutput/from_failed_session.bin"
        echo "ERROR: CatGT did not make the expected output:" >&2
        echo "  - no *_tcat.imec0.ap.bin" >&2
        false
    fi
    echo "uploaded $dates"
}
failed_sessions=()
for entry in "${SESSIONS[@]}"; do
    parse_entry "$entry"
    session_start=$SECONDS
    run_session steps
    finish_session
done
report_failures ${#SESSIONS[@]}
'''
    out = run(script, base_folder=f"{base}/")
    assert out.returncode == 1, out.stderr
    assert "LEAK" not in out.stdout
    assert "uploaded 20250101/20250101_0" not in out.stdout
    assert "uploaded 20250101/20250101_1" in out.stdout and "uploaded 20250102/20250102_0" in out.stdout
    assert "--- 1 of 3 sessions failed: ---" in out.stdout
    assert "M1 20250101/20250101_0: ERROR: CatGT did not make the expected output: no *_tcat.imec0.ap.bin [exit 1" in out.stdout
    aside = list((base / "_failed").iterdir())
    assert [p.name.startswith("M1_20250101_") for p in aside] == [True]
    assert (aside[0] / "CatGToutput" / "from_failed_session.bin").exists()
    assert sorted(p.name for p in base.iterdir()) == ["_failed"]  # successful sessions deleted


def test_set_aside_never_overwrites(tmp_path):
    base = tmp_path / "temp_data"
    out = run('parse_entry "M1 20250101/20250101_0,20250102/20250102_0"\n'
              'for i in 1 2; do\n'
              '  mkdir -p "$base_folder/M1/20250101/20250101_0" "$base_folder/M1/20250102/20250102_0"\n'
              '  set_aside_failed_session\n'
              'done\n', base_folder=base)
    assert out.returncode == 0, out.stderr
    assert len(out.stdout.split()) == 4
    assert len(list((base / "_failed").iterdir())) == 4
    assert not (base / "M1").exists()


def test_all_sessions_ok_report():
    out = run('failed_sessions=()\nreport_failures 2')
    assert out.returncode == 0 and "All 2 sessions processed successfully" in out.stdout


# --- machine paths and CatGT/TPrime links ---

CONFIG = LIB.parent / "machine_config.sh"


def _copy_config(root: Path) -> Path:
    repo = root / "si_edd" / "SI_processing"
    repo.mkdir(parents=True)
    shutil.copy(CONFIG, repo / "machine_config.sh")
    return repo


def _config(repo: Path) -> dict:
    out = run(f"source '{_sh_path(repo / 'machine_config.sh')}'\n"
              'echo "$base_folder|$server_folder|$pathToCatGTRunit|$pathToTPrimeRunit"')
    assert out.returncode == 0, out.stderr
    keys = ["base_folder", "server_folder", "catgt", "tprime"]
    return dict(zip(keys, out.stdout.strip().split("|")))


def _real(p: Path) -> str:
    # what `pwd -P` prints for p (Git Bash gives /c/... on Windows)
    out = subprocess.run([BASH, "-c", f"cd '{_sh_path(p)}' && pwd -P"], capture_output=True, text=True)
    return out.stdout.strip()


def test_machine_paths_follow_the_repo(tmp_path):
    repo = _copy_config(tmp_path)
    c = _config(repo)
    root = _real(tmp_path / "si_edd")
    assert c["base_folder"] == f"{root}/temp_data/"
    assert c["server_folder"] == "/mnt/rds01/ibn-vision/DATA/SUBJECTS/"
    assert c["catgt"] == f"{root}/SI_processing/CatGT-linux/runit.sh"
    assert c["tprime"] == f"{root}/SI_processing/TPrime-linux/runit.sh"


def test_machine_local_overrides(tmp_path):
    repo = _copy_config(tmp_path)
    (repo / "machine.local.sh").write_text("base_folder='/data/temp_data/'\n")
    c = _config(repo)
    assert c["base_folder"] == "/data/temp_data/"
    assert c["catgt"].endswith("/SI_processing/CatGT-linux/runit.sh")


def _fake_tool(dir: Path) -> Path:
    """A tool folder whose install.sh links the loader like the real one and counts its runs."""
    (dir / "libs").mkdir(parents=True)
    (dir / "libs" / "ld-2.23.so").write_text("loader")
    (dir / "install.sh").write_text(
        "rm -rf links\nmkdir -p links\nln -s $PWD/libs/ld-2.23.so links/ld-linux-x86-64.so.2\n"
        "echo x >> installs.txt\n", newline="\n")
    return dir


def _installs(dir: Path) -> int:
    f = dir / "installs.txt"
    return len(f.read_text().split()) if f.exists() else 0


def _symlinks_work(tmp_path) -> bool:
    probe = tmp_path / "symlink_probe"
    probe.mkdir()
    out = subprocess.run([BASH, "-c", f"cd '{_sh_path(probe)}' && touch a && ln -s \"$PWD/a\" b && test -L b"],
                         capture_output=True)
    return out.returncode == 0


def test_missing_links_are_built(tmp_path):
    tool = _fake_tool(tmp_path / "CatGT-linux")
    out = run(f"ensure_tool_links '{_sh_path(tool)}'")
    assert out.returncode == 0, out.stderr
    assert _installs(tool) == 1 and (tool / "links" / "ld-linux-x86-64.so.2").exists()


def test_links_from_another_machine_are_rebuilt(tmp_path):
    """The clone carries links into the first machine's folder: dangling here, or (with both
    folders on one machine) pointing at the other copy. Either way, install.sh runs once."""
    if not _symlinks_work(tmp_path):
        pytest.skip("this bash cannot make symlinks (Git Bash on Windows without developer mode)")
    old = _fake_tool(tmp_path / "old" / "CatGT-linux")
    new = _fake_tool(tmp_path / "new" / "CatGT-linux")
    sh = lambda script: subprocess.run([BASH, "-c", script], capture_output=True, text=True)
    # links into the other copy
    assert sh(f"mkdir -p '{_sh_path(new)}/links' && ln -s '{_sh_path(old)}/libs/ld-2.23.so' "
              f"'{_sh_path(new)}/links/ld-linux-x86-64.so.2'").returncode == 0
    out = run(f"ensure_tool_links '{_sh_path(new)}'")
    assert out.returncode == 0, out.stderr
    assert _installs(new) == 1 and "Rebuilding CatGT-linux links" in out.stdout
    # now correct: left alone
    out = run(f"ensure_tool_links '{_sh_path(new)}'")
    assert out.returncode == 0 and _installs(new) == 1 and out.stdout == ""
    # dangling, as on a machine without the first machine's home folder
    assert sh(f"rm -rf '{_sh_path(new)}/links' && mkdir '{_sh_path(new)}/links' && "
              f"ln -s /home/nobody_here/CatGT-linux/libs/ld-2.23.so '{_sh_path(new)}/links/ld-linux-x86-64.so.2'").returncode == 0
    out = run(f"ensure_tool_links '{_sh_path(new)}'")
    assert out.returncode == 0, out.stderr
    assert _installs(new) == 2


def test_check_machine_reports_missing_server_and_tool(tmp_path):
    tool = _fake_tool(tmp_path / "TPrime-linux")
    (tool / "runit.sh").write_text("")
    out = run("check_machine",
              base_folder=tmp_path / "temp_data", server_folder=tmp_path / "not_mounted",
              pathToCatGTRunit=tmp_path / "CatGT-linux" / "runit.sh", pathToTPrimeRunit=tool / "runit.sh")
    assert out.returncode == 1
    assert "is the server mounted?" in out.stderr and "CatGT-linux/runit.sh" in out.stderr
    assert (tmp_path / "temp_data").is_dir() and _installs(tool) == 1


def test_check_machine_ok(tmp_path):
    tools = [_fake_tool(tmp_path / n) for n in ("CatGT-linux", "TPrime-linux")]
    for t in tools:
        (t / "runit.sh").write_text("")
    (tmp_path / "server").mkdir()
    out = run("check_machine", base_folder=tmp_path / "temp_data", server_folder=tmp_path / "server",
              pathToCatGTRunit=tools[0] / "runit.sh", pathToTPrimeRunit=tools[1] / "runit.sh")
    assert out.returncode == 0, out.stderr
    assert "Local folder" in out.stdout
