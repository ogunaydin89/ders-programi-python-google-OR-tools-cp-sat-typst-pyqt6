"""The package must start the way users start it: `python -m dersprogrami`, without test path tricks."""
import os
import subprocess
import sys
import tempfile


def test_package_is_installed_and_importable_from_anywhere():
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run([sys.executable, "-c", "import dersprogrami.ui.app, dersprogrami.curriculum as c; "
                          "print(len(c.load_all()))"], cwd=tempfile.gettempdir(), env=env,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "5"


def test_command_line_help_runs():
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run([sys.executable, "-m", "dersprogrami", "check", "--help"], cwd=tempfile.gettempdir(),
                         env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
