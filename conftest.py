"""Test configuration.

This one line lets pytest (and the demo) import our code with clean names like
`from pipeline import Pipeline` by putting the `src/` folder on Python's import
path. Without it, Python wouldn't know where to find our modules.
"""
import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
