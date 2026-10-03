"""Remove only the local Day 9 feedback database; pass --yes to confirm deletion."""
import argparse
from pathlib import Path
from backend.app.config.risk_config import PROJECT_ROOT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--yes',action='store_true',help='Confirm removal of local feedback/audit/review history.')
    args=parser.parse_args()
    target=(PROJECT_ROOT/'data'/'processed'/'day9'/'feedback.sqlite').resolve()
    allowed=(PROJECT_ROOT/'data'/'processed'/'day9').resolve()
    if allowed not in target.parents:raise RuntimeError('Refusing to reset a path outside the demo data directory.')
    if not args.yes:
        print(f'Dry run. Would remove {target.name} and its SQLite sidecar files; rerun with --yes.')
        return
    for path in (target,Path(str(target)+'-wal'),Path(str(target)+'-shm')):
        if path.exists():path.unlink()
    print('Local feedback, audit and review data reset. Restart the API to clear in-memory payment attempts. Models and reports were preserved.')


if __name__=='__main__':main()
