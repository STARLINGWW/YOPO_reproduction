"""CLI wrapper for the aggregation dataset builder."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from yopo_dagger.build_dataset import main


if __name__=='__main__':main()
