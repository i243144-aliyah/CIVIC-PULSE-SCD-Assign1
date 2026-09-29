"""Run the canonical CivicPulse database seed from the repository root."""

from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
runpy.run_path(str(BACKEND / "scripts" / "seed.py"), run_name="__main__")