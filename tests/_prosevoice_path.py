"""Put the source prosevoice skill's scripts directory on sys.path for the tests."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/prosevoice/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
