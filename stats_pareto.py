#!/usr/bin/env python3.10

import itertools
from pathlib import Path
from write_backends import make_level_dicts

ARCHIVE_DIR = Path('../spacechem-archive')

def main():
    id2name, _ = make_level_dicts()

    levels = list(id2name.keys())
    solutions_files = [(p, p.parts[-2].replace('_', '-')) for p in ARCHIVE_DIR.glob('*/*/solutions.psv')]
    solutions_files.sort(key=lambda s: levels.index(s[1]))

    print('level, solutions, filling fraction')
    for (solutions_file, db_id) in solutions_files:
        with open(solutions_file) as sf:
            raw_scores: list = [line.split('|', 1)[0].replace(',', '').split('/') for line in sf]
            scores = [tuple(map(int, score)) for score in raw_scores if len(score) == 3]

        realistic_paretos = 1
        for (this, next) in itertools.pairwise(scores):
            if this[1] >= next[1]:
                # find the number of holes in symbols and cycles, keep the smallest
                realistic_paretos += min(abs(this[i] - next[i]) for i in [0, 2])
            else:
                realistic_paretos += 1

        print(f'"{id2name[db_id]}", {len(raw_scores)}, {len(raw_scores)/realistic_paretos:.2f}')

if __name__ == '__main__':
    main()
