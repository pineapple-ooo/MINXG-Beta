"""pytest configuration: ensure project root is on sys.path so
`import minxg` works without `pip install -e .`.
""""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
