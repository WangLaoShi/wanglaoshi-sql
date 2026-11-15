import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_demo_script_prints_counts_and_roles():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "demo.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0] == "30"
    assert lines[1] == "6"
    assert any("度量" in line for line in lines)
    assert any("维度" in line for line in lines)
