#!/usr/bin/env python3

import os
import csv
import sqlite3
import pickle
import re
import datetime
import argparse

from collections import OrderedDict
from collections import Counter

### Configuration block

scoresfile = r"score_dump.csv"
saves_folder = r'saves'

dumpfile = r'dump.pickle'
wikifolder = r'../wiki/'
wikifiles = [r'index.md', r'researchnet.md', r'researchnet2.md']

"""
{'Username': '<user>', 'Level Category': '63corvi', 'Level Number': '1', 'Level Name': 'QT-1',
 'Cycle Count': '20', 'Reactor Count': '1', 'Symbol Count': '5', 'Upload Time': '2013-08-15 10:23:14.329898', 'Youtube Link': ''}
"""

"""
{'id': 'fusion-1', 'passed': 1, 'mastered': 0, 'cycles': 52, 'symbols': 38, 'reactors': 1, 'best_cycles': 52, 'best_symbols': 11, 'best_reactors': 1}
"""

nowstring = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')

save2id = {}
id2level = {}
levels = OrderedDict()

def init():

    global save2id, id2level, levels

    with open('levels.csv') as levelscsv:
        reader = csv.DictReader(levelscsv, skipinitialspace=True)
        for row in reader:
            id_tuple = (row['category'], row['number'])
            save2id[row['saveId']] = id_tuple
            id2level[id_tuple] = {'name': row['name'],
                                  'type': row['type'],
                                  'isDeterministic': int(row['isDeterministic'])}
            levels[id_tuple] = {}


def tiebreak(this_score, best_score, stat1, stat2, stat3):
    return (this_score[stat1] < best_score[stat1] or
            (this_score[stat1] == best_score[stat1] and
             (this_score[stat2] < best_score[stat2] or
              (this_score[stat2] == best_score[stat2] and
               (this_score[stat3] < best_score[stat3] or
                (this_score[stat3] == best_score[stat3] and
                 (bool(this_score['Youtube Link']) > bool(best_score['Youtube Link']) or
                  (bool(this_score['Youtube Link']) == bool(best_score['Youtube Link']) and
                   this_score['Upload Time'] < best_score['Upload Time']
                  )
                 )
                )
               )
              )
             )
            )
           )

def insert_score(this_score, scores, category, stats):
    if category not in scores or tiebreak(this_score, scores[category], *stats):
        scores[category] = this_score

def add_score(level_id, this_score, test_reject=True):

    props = id2level[level_id]

    if test_reject and should_reject(this_score):
        return

    insert_score(this_score, levels[level_id], 'Least Cycles', ['Cycle Count', 'Reactor Count', 'Symbol Count'])
    insert_score(this_score, levels[level_id], 'Least Symbols', ['Symbol Count', 'Reactor Count', 'Cycle Count'])
    if props['type'] in {'production', 'boss'}:
        insert_score(this_score, levels[level_id], 'Least Cycles - N Reactors', ['Reactor Count', 'Cycle Count', 'Symbol Count'])
        insert_score(this_score, levels[level_id], 'Least Symbols - N Reactors', ['Reactor Count', 'Symbol Count', 'Cycle Count'])

def should_reject(this_score):
    # In, Out, 2 arrows, Swap = 5 min
    # Max of 2*2*80=320 symbols/reactor
    # In, Swap, Out /2 = 1.5
    return this_score['Symbol Count'] < 5*this_score['Reactor Count'] or \
           this_score['Symbol Count'] > 320*this_score['Reactor Count'] or \
           this_score['Cycle Count'] < 1.5*this_score['Reactor Count']


fmt_scores_with_bold = ['({}/{}/{}) {}', '({}/{}/**{}**) {}', '({}/**{}**/{}) {}', '({}/**{}**/**{}**) {}',
                        '(**{}**/{}/{}) {}', '(**{}**/{}/**{}**) {}', '(**{}**/**{}**/{}) {}',
                        '(**{}**/**{}**/**{}**) {}']

def printscore(score, bold=0b000, suffix='', printvideo=True):
    fmt_score = fmt_scores_with_bold[bold].format(score['Cycle Count'], score['Reactor Count'], score['Symbol Count'],
                                                  score['Username'])
    if printvideo and score['Youtube Link']:
        fmt_score = '[{}]({})'.format(fmt_score, score['Youtube Link'])
    print('| {:20}{suffix}'.format(fmt_score, suffix=suffix), end=' ')

def printblock(scores, header, cat1, cat2, bold1, bold2, suffix='', printvideo=True):
    if cat1 in scores and cat2 in scores:
        print(header.ljust(20), end='')
        printscore(scores[cat1], bold=bold1, suffix=suffix, printvideo=printvideo)
        printscore(scores[cat2], bold=bold2, suffix=suffix, printvideo=printvideo)
        print()

def parse_solnet():

    user2OS = {}

    with open('users.csv') as userscsv:
        reader = csv.DictReader(userscsv, skipinitialspace=True)
        user2OS = {row['User']: row['OS'] for row in reader}

    with open(scoresfile) as scorescsv:
        reader = csv.DictReader(scorescsv)
        for row in reader:
            
            if row['Level Category'] == 'researchnet' and \
               row['Level Number'].count('-') == 1:
                    longissue, assign = map(int, row['Level Number'].split('-'))
                    volume, issue = (longissue-1)//12+1, (longissue-1)%12+1
                    level_id = ('researchnet', '{}-{}-{}'.format(volume, issue, assign))
            else:
                level_id = (row['Level Category'], row['Level Number'])
            
            this_score = {'Username': row['Username'],
                          'Cycle Count': int(row['Cycle Count']),
                          'Reactor Count': int(row['Reactor Count']),
                          'Symbol Count': int(row['Symbol Count']),
                          'Upload Time': row['Upload Time'],
                          'Youtube Link': row['Youtube Link']}
            
            if '@' in this_score['Username']:
                this_score['Username'], userOS = this_score['Username'].split('@')
            elif this_score['Username'] in user2OS:
                userOS = user2OS[this_score['Username']]
            else:
                userOS = 'Unknown OS'
            
            if id2level[level_id]['isDeterministic'] or userOS == 'Windows':
                add_score(level_id, this_score)


def parse_saves():

    for player in os.listdir(saves_folder):
        player_folder = os.path.join(saves_folder, player)
        for save in os.listdir(player_folder):
            try:
                conn = sqlite3.connect(os.path.join(player_folder, save))
            except sqlite3.OperationalError:
                continue
            conn.row_factory = sqlite3.Row
            # we use cycles > 0 as a good proxy for finished
            dbcursor = conn.execute("SELECT * FROM Level WHERE cycles != 0")

            for row in dbcursor:
                # CE extra sols are stored as `id!progressive`
                clean_id = row['id'].split('!')[0]
                if clean_id in save2id:
                    level_id = save2id[clean_id]
                else:
                    continue
                this_score = {'Username': player,
                              'Cycle Count': row['cycles'],
                              'Reactor Count': row['reactors'],
                              'Symbol Count': row['symbols'],
                              'Upload Time': nowstring,
                              'Youtube Link': ''}
                
                add_score(level_id, this_score)
            
            conn.close()

def dump_scores():
    with open(dumpfile, 'wb') as dumpdest:
        pickle.dump(levels, dumpdest)

def load_scores():
    global levels
    with open(dumpfile, 'rb') as dumpdest:
        levels = pickle.load(dumpdest)

def parse_wiki():
    
    lines = []
    for f in wikifiles:
        with open(wikifolder + f) as infile:
            lines.extend(infile.readlines())
    
    level_reg = re.compile(r'^(?P<level>.+?)(?: - (?P<reactors>\d|N) Reactors?)?$')
    score_reg = re.compile(r'^\[?\(\**(?P<cycles>[\d,]+)\**(?:\\\*)?/\**(?P<reactors>\d+)\**/\**(?P<symbols>\d+)\**\)'
                           r'\s+(?P<user>[^\]]+?)(?:\]\((?P<link>[^\)]+)\).*?)?$')
    single_score_reg = re.compile(r'^\**(?P<score>[\d,]+)\**$')
    extra_stuff_reg = re.compile(r'^(?:←+|X|† \[\()')
    
    it = iter(levels)
    
    for line in lines:
        table_cols = re.split(r'\s*\|\s*', line)[1:]
        if len(table_cols) >= 5:
            name_col = table_cols[0]
            if name_col not in {'Name', ':-'}:
                level_match = level_reg.match(name_col)
                best_reactors = level_match.group('reactors')
                if not best_reactors:
                    level_id = next(it)
                    while id2level[level_id]['type'] == 'boss':
                        level_id = next(it)
                
                scores = table_cols[1:]
                cols = len(scores)
                assert cols in {4,6}, "Level {level_id} has {cols} cols".format_map(locals())
                for idx, tm in enumerate(scores):
                    score_match = score_reg.match(tm)
                    if score_match:
                        this_score = {'Username': score_match.group('user'),
                                      'Cycle Count': int(score_match.group('cycles').replace(',', '')),
                                      'Reactor Count': int(score_match.group('reactors')),
                                      'Symbol Count': int(score_match.group('symbols')),
                                      'Upload Time': '0',
                                      'Youtube Link': score_match.group('link') if score_match.group('link') else ''}
                                      
                        add_score(level_id, this_score)
                    else:
                        single_score_match = single_score_reg.match(tm)
                        if single_score_match:
                            
                            score = int(single_score_match.group('score').replace(',', ''))
                            if 0 <= idx < cols/2:
                                c,s = score, 9999
                            elif cols/2 <= idx < cols:
                                c,s = 99999999, score
                            else:
                                raise IndexError('Score {score} at idx {idx}'.format_map(locals()))
                            
                            if id2level[level_id]['type'] == 'research':
                                r = 1
                            else:
                                r = 7

                            this_score = {'Username': 'Unknown User',
                                          'Cycle Count': c,
                                          'Reactor Count': r,
                                          'Symbol Count': s,
                                          'Upload Time': nowstring,
                                          'Youtube Link': ''}
                                
                            add_score(level_id, this_score, False)
                        else:
                            if not extra_stuff_reg.match(tm):
                                print(tm)

def print_scores(printset, no_separator=False, no_video=False):

    if not printset:
        return
    
    for level_id in levels:
        scores = levels[level_id]
        if not scores:
            continue

        level = id2level[level_id]
        if level['type'] not in printset:
            continue
        score_header = '| Min Cycles | Min Symbols' if no_separator else \
                       '| Min Cycles | Min Cycles - No Bugs | Min Symbols | Min Symbols - No Bugs' if level['isDeterministic'] else \
                       '| Min Cycles | Min Cycles - No Bugs | Min Cycles - No Precognition ' + \
                       '| Min Symbols | Min Symbols - No Bugs | Min Symbols - No Precognition'
        print('|{} - {}'.format(*level_id).ljust(20) + score_header)

        score_separator = '' if no_separator else ' | N/A' if level['isDeterministic'] else ' | N/A | N/A'
        printblock(scores, '|{name} '.format(**level),
                   'Least Cycles', 'Least Symbols',
                   0b100, 0b001, score_separator, not no_video)
        printblock(scores, '|{name} - N Reactors '.format(**level),
                   'Least Cycles - N Reactors', 'Least Symbols - N Reactors',
                   0b110, 0b011, score_separator, not no_video)
        print()

def print_leaderboard():
    leaderboard = Counter()
    for scores in levels.values():
        for score in scores.values():
            name = score['Username']
            leaderboard[name] += 1

    print('{} scores by {} users'.format(sum(leaderboard.values()), len(leaderboard)))
    print('Name                 Scores')
    for name, count in sorted(leaderboard.items(), key=lambda item: (-item[1], item[0].lower())):
        print('{name:24}{count:3}'.format_map(locals()))

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--load", action="store_true")
    parser.add_argument("--no-wiki", action="store_false", dest='wiki')
    parser.add_argument("-w", "--wiki", action="store_true", dest='wiki')
    parser.add_argument("-n", "--solnet", action="store_true")
    parser.add_argument("-s", "--saves", action="store_true")
    parser.add_argument("-d", "--dump", action="store_true")
    parser.add_argument("-p", "--print", choices={'research', 'production', 'boss'}, nargs='+', default=['research', 'production', 'boss'])
    parser.add_argument("--no-print", choices={'research', 'production', 'boss'}, nargs='+', default=[])
    parser.add_argument("--no-print-separator", action="store_true")
    parser.add_argument("--no-print-video", action="store_true")
    parser.add_argument("--leaderboard", action="store_true")
    args = parser.parse_args()

    init()
    if args.load:
        load_scores()
    if args.wiki:
        parse_wiki()
    if args.solnet:
        parse_solnet()
    if args.saves:
        parse_saves()
    if args.dump:
        dump_scores()
    
    print_scores(set(args.print) - set(args.no_print), args.no_print_separator, args.no_print_video)
    
    if args.leaderboard:
        print_leaderboard()
