import sys
from pathlib import Path

# make root importable in all test modules
sys.path.insert(0, str(Path(__file__).parent.parent))
