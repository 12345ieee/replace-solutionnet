#!/usr/bin/env python3

from pathlib import Path
from write_backends import make_level_dicts

ARCHIVE_DIR = Path('../spacechem-archive')

def main():
    id2name, _ = make_level_dicts()
    for scores_file in sorted(ARCHIVE_DIR.glob('*/*/scores.txt')):
        with open(scores_file) as sf:
            scores = [line.rstrip() for line in sf]
        for score in scores:
            file = scores_file.parent / (score.replace("/", "-") + '.txt')
            if not file.exists():
                db_id = scores_file.parts[-2].replace('_', '-')
                print(f'{score:13} {id2name[db_id]:30} {file}')

if __name__ == '__main__':
    main()
