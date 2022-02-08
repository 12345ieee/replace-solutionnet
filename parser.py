#!/usr/bin/env python3.10

import argparse
import bisect
import csv
import sqlite3
import typing
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Dict, List

from read_backends import SaveReadBackend

### Configuration block

saves_path = Path(r'saves')
archive_path = Path(r'../archive/')

"""
{'Username': '<user>', 'Level Category': '63corvi', 'Level Number': '1', 'Level Name': 'QT-1',
 'Cycle Count': '20', 'Reactor Count': '1', 'Symbol Count': '5', 'Upload Time': '2013-08-15 10:23:14.329898', 'Youtube Link': ''}
"""

"""
{'id': 'fusion-1', 'passed': 1, 'mastered': 0, 'cycles': 52, 'symbols': 38, 'reactors': 1, 'best_cycles': 52, 'best_symbols': 11, 'best_reactors': 1}
"""

Level = typing.NamedTuple('Level', [('name', str), ('type', str), ('is_deterministic', bool)])

class Solution(typing.NamedTuple):
    cycles: int
    reactors: int
    symbols: int
    is_bugged: bool
    is_precognitive: bool
    author: str
    display_link: str = ''
    categories: str = '' # we won't actually find them, but we keep the ones from archive

    def score(self) -> tuple:
        return (self.cycles, self.reactors, self.symbols, self.is_bugged, self.is_precognitive)

    def slash_flags(self):
        if self.is_bugged or self.is_precognitive:
            result = '/'
            if self.is_bugged: result += 'B'
            if self.is_precognitive: result += 'P'
            return result
        else:
            return ''

    def marshal(self) -> str:
        return f'{self.cycles}/{self.reactors}/{self.symbols}{self.slash_flags()}|' + \
               f'{self.author}|{self.display_link}||{self.categories}'

    @classmethod
    def unmarshal(cls, line: str):
        score, author, display_link, video_only, categories = line.rstrip().split('|')
        cycles_str, reactors_str, symbols_str, *flags = score.split('/')
        cycles = int(cycles_str.replace(',', ''))
        is_bugged = bool(flags and 'B' in flags[0])
        is_precognitive = bool(flags and 'P' in flags[0])
        return Solution(cycles, int(reactors_str), int(symbols_str), is_bugged, is_precognitive,
                        author, display_link, categories)

solnet2id: Dict[tuple, str] = {}
id2level: Dict[str, Level] = {}
level_solutions: Dict[str, List[Solution]] = OrderedDict()

def init():

    with open('config/levels.csv') as levelscsv:
        reader = csv.DictReader(levelscsv, skipinitialspace=True)
        for row in reader:
            save_id = row['saveId']
            solnet_id = (row['category'], row['number']) # ("main", "1-1")
            solnet2id[solnet_id] = save_id
            id2level[save_id] = Level(row['name'], row['type'], bool(int(row['isDeterministic'])))
            level_solutions[save_id] = []


def dominance_compare(s1: Solution, s2: Solution):
    r1 = s1.cycles - s2.cycles
    r2 = s1.reactors - s2.reactors
    r3 = s1.symbols - s2.symbols
    r4 = s1.is_bugged - s2.is_bugged
    r5 = s1.is_precognitive - s2.is_precognitive

    if r1 <= 0 and r2 <= 0 and r3 <= 0 and r4 <= 0 and r5 <= 0:
        if r1 == 0 and r2 == 0 and r3 == 0 and r4 == 0 and r5 == 0:
            return 1 # preexisting sol wins
        else:
            return -1
    elif r1 >= 0 and r2 >= 0 and r3 >= 0 and r4 >= 0 and r5 >= 0:
        # sol2 dominates
        return 1
    else:
        # equal is already captured by the 1st check, this is for "not comparable"
        return 0

def add_solution(save_id: str, candidate: Solution, test_reject=True, test_frontier=True):

    if test_reject and should_reject(candidate):
        return

    solutions = level_solutions[save_id]
    if test_frontier:
        for i in range(len(solutions)-1, -1, -1): # iterate backwards so we can delete things
            solution = solutions[i]
            r = dominance_compare(candidate, solution)
            if r > 0:
                return
            elif r < 0:
                # candidate.categories += solution.categories
                del solutions[i]

    bisect.insort(solutions, candidate, key=lambda s: s.score())


def should_reject(solution: Solution) -> bool:
    # In, Out, 2 arrows, Swap = 5 min
    # Max of 2*2*80=320 symbols/reactor
    # In, Swap, Out /2 = 1.5
    return solution.symbols < 5*solution.reactors or \
           solution.symbols > 320*solution.reactors or \
           solution.cycles < 1.5*solution.reactors

def parse_solnet():

    with open('config/users.csv') as userscsv:
        reader = csv.DictReader(userscsv, skipinitialspace=True)
        user2OS = {row['User']: row['OS'] for row in reader}

    with open('data/score_dump.csv') as scorescsv:
        reader = csv.DictReader(scorescsv)
        for row in reader:
            if row['Level Category'] == 'researchnet' and \
               row['Level Number'].count('-') == 1:
                    longissue, assign = map(int, row['Level Number'].split('-'))
                    volume, issue = (longissue-1)//12+1, (longissue-1)%12+1
                    solnet_id = ('researchnet', f'{volume}-{issue}-{assign}')
            else:
                solnet_id = (row['Level Category'], row['Level Number'])

            save_id = solnet2id[solnet_id]
            level = id2level[save_id]
            author = row['Username']
            if not level.is_deterministic:
                if '@' in author:
                    author, userOS = author.split('@')
                elif author in user2OS:
                    userOS = user2OS[author]
                else:
                    userOS = 'Unknown OS'

            if level.is_deterministic or userOS == 'Windows':
                this_solution = Solution(cycles=int(row['Cycle Count']),
                                         reactors=int(row['Reactor Count']),
                                         symbols=int(row['Symbol Count']),
                                         is_bugged=True,
                                         is_precognitive=not level.is_deterministic,
                                         author=author,
                                         display_link=row['Youtube Link'])
                add_solution(save_id, this_solution)


def parse_saves():

    for player_path in saves_path.iterdir():
        player: str = player_path.name
        for save in player_path.glob('**/*.user'):
            try:
                read_backend = SaveReadBackend(save)
            except sqlite3.OperationalError:
                continue
            for row in read_backend.read_solutions(ids=None, pareto_only=False):
                # CE extra sols are stored as `id!progressive`
                clean_id = row['id'].split('!')[0]
                level = id2level[clean_id]
                this_solution = Solution(cycles=row['cycles'],
                                         reactors=row['reactors'],
                                         symbols=row['symbols'],
                                         is_bugged=True,
                                         is_precognitive=not level.is_deterministic,
                                         author=player,
                                         display_link='')

                add_solution(clean_id, this_solution)

            read_backend.close()

def parse_archive():

    for puzzle_path in archive_path.glob('[CMRT]*/*'):
        if not puzzle_path.is_dir():
            continue
        level_id = puzzle_path.stem.replace('_', '-')
        with open(puzzle_path / 'solutions.psv', 'r') as metadata_file:
            for line in metadata_file:
                this_solution = Solution.unmarshal(line)
                add_solution(level_id, this_solution, test_reject=False)

def print_solutions(printset):

    if not printset:
        return

    for level_id in level_solutions:
        solutions = level_solutions[level_id]
        if not solutions:
            continue

        level = id2level[level_id]
        if level.type not in printset:
            continue

        print(f'{level.name} - {level_id}')
        for solution in solutions:
            print(solution.marshal())
        print()

def print_leaderboard(include_frontier: bool):
    leaderboard = Counter()
    for solutions in level_solutions.values():
        for solution in solutions:
            if include_frontier or solution.categories:
                leaderboard[solution.author] += 1

    print('{} {} solutions by {} users'.format(sum(leaderboard.values()),
                                               'frontier' if include_frontier else 'record',
                                               len(leaderboard)))
    print('Name              Solutions')
    for name, count in sorted(leaderboard.items(), key=lambda item: (-item[1], item[0].lower())):
        print(f'{name:24}{count:3}')

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--archive", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("-n", "--solnet", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("-s", "--saves", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("-p", "--print", choices={'research', 'production', 'boss'}, nargs='+', default=['research', 'production', 'boss'])
    parser.add_argument("--no-print", choices={'research', 'production', 'boss'}, nargs='+', default=[])
    parser.add_argument("--leaderboard", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--include-frontier", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    init()
    if args.archive:
        parse_archive()
    if args.solnet:
        parse_solnet()
    if args.saves:
        parse_saves()

    if args.leaderboard:
        print_leaderboard(args.include_frontier)
    else:
        print_solutions(set(args.print) - set(args.no_print))
