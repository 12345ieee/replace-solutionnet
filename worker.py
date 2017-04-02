#!/usr/bin/env python3

import csv
import sqlite3
import pickle
import re
import datetime
from collections import OrderedDict

### Configuration block

scoresfile = r"score_dump.csv"
saves = [ {'saveFile': r'save/000.user', 'playerName': '12345ieee', 'playerOS': 'Linux'},
          {'saveFile': r'save/001.user', 'playerName': '12345ieee', 'playerOS': 'Linux'},
          {'saveFile': r'save/002.user', 'playerName': '12345ieee', 'playerOS': 'Linux'},
          {'saveFile': r'saves/Criado.user', 'playerName': 'Criado', 'playerOS': 'Linux'},
        ]
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

def add_score(level_id, this_score, playerOS):

    props = id2level[level_id]

    if should_reject(this_score):
        return

    if props['isDeterministic']:
        insert_score(this_score, levels[level_id], 'Least Cycles', ['Cycle Count', 'Reactor Count', 'Symbol Count'])
        insert_score(this_score, levels[level_id], 'Least Symbols', ['Symbol Count', 'Reactor Count', 'Cycle Count'])
        if props['type'] in {'production', 'boss'}:
            insert_score(this_score, levels[level_id], 'Least Cycles - N Reactors', ['Reactor Count', 'Cycle Count', 'Symbol Count'])
            insert_score(this_score, levels[level_id], 'Least Symbols - N Reactors', ['Reactor Count', 'Symbol Count', 'Cycle Count'])
    else:
        insert_score(this_score, levels[level_id], 'Least Cycles - {}'.format(playerOS), ['Cycle Count', 'Reactor Count', 'Symbol Count'])
        insert_score(this_score, levels[level_id], 'Least Symbols - {}'.format(playerOS), ['Symbol Count', 'Reactor Count', 'Cycle Count'])
        if props['type'] in {'production', 'boss'}:
            insert_score(this_score, levels[level_id], 'Least Cycles - {} - N Reactors'.format(playerOS), ['Reactor Count', 'Cycle Count', 'Symbol Count'])
            insert_score(this_score, levels[level_id], 'Least Symbols - {} - N Reactors'.format(playerOS), ['Reactor Count', 'Symbol Count', 'Cycle Count'])

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

def printscore(score, bold=0, suffix=''):
    fmt_score = fmt_scores_with_bold[bold].format(score['Cycle Count'], score['Reactor Count'], score['Symbol Count'],
                                                  score['Username'])
    if score['Youtube Link']:
        fmt_score = '[{}]({})'.format(fmt_score, score['Youtube Link'])
    print('| {:20}{suffix}'.format(fmt_score, suffix=suffix), end=' ')

def printblock(scores, header, cat1, cat2, bold1, bold2, suffix=''):
    if cat1 in scores and cat2 in scores:
        print(header.ljust(20), end='')
        printscore(scores[cat1], bold=bold1, suffix=suffix)
        printscore(scores[cat2], bold=bold2, suffix=suffix)
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
            
            add_score(level_id, this_score, userOS)


def parse_saves():

    for save in saves:
        conn = sqlite3.connect(save['saveFile'])
        conn.row_factory = sqlite3.Row
        dbcursor = conn.execute("SELECT * FROM {}".format('Level'))

        for row in dbcursor:
            if row['passed'] == 0:
                continue
            if row['id'] in save2id:
                level_id = save2id[row['id']]
            else:
                continue
            this_score = {'Username': save['playerName'],
                          'Cycle Count': row['cycles'],
                          'Reactor Count': row['reactors'],
                          'Symbol Count': row['symbols'],
                          'Upload Time': nowstring,
                          'Youtube Link': ''}
            
            add_score(level_id, this_score, save['playerOS'])
        
        conn.close()

def dump_scores():
    with open(dumpfile, 'wb') as dumpdest:
        pickle.dump(levels, dumpdest)

def load_scores():
    global levels
    with open(dumpfile, 'rb') as dumpdest:
        levels = pickle.load(dumpdest)

def print_scores():

    for level_id in levels:
        scores = levels[level_id]
        if not scores:
            continue
        
        print('|{} - {}'.format(*level_id).ljust(20) + '| Min Cycles | Min Cycles - No Bugs | Min Symbols | Min Symbols - No Bugs')

        level = id2level[level_id]
        
        for OSstring in ['', ' - Windows', ' - Linux', ' - Unknown OS']:
            printblock(scores, '|{name}{OS} '.format(**level, OS=OSstring),
                       'Least Cycles{}'.format(OSstring), 'Least Symbols{}'.format(OSstring),
                       0b100, 0b001, ' | N/A | N/A' if OSstring else ' | N/A')
            printblock(scores, '|{name}{OS} - N Reactors '.format(**level, OS=OSstring),
                       'Least Cycles{} - N Reactors'.format(OSstring), 'Least Symbols{} - N Reactors'.format(OSstring),
                       0b110, 0b011, ' | N/A | N/A' if OSstring else ' | N/A')
        print()

def parse_wiki():
    
    lines = []
    for f in wikifiles:
        with open(wikifolder + f) as infile:
            lines.extend(infile.readlines())
    
    reg = re.compile(r'^\|{0}\|{0}\|{0}\|{0}\|{0}\|?{0}?\|?{0}?$'.format(r'([^|]+)'))
    lreg = re.compile(r'^(?P<level>.+?)(?: - (?P<OS>Windows|Linux|Unknown OS))?(?: - (?P<reactors>\d) Reactors?)?\s*$')
    sreg = re.compile(r'^\s*\[?\(\**(?P<cycles>\d+)\**(?P<OSmark>\\\*)?/\**(?P<reactors>\d+)\**/\**(?P<symbols>\d+)\**\)\s+(?P<user>[^\]]+?)(?:\]\((?P<link>[^\)]+)\))?\s*$')
    it = iter(levels)
    
    for line in lines:
        match = reg.match(line)
        if match:
            if match.group(1).strip() not in {'Name', ':-'}:
                lmatch = lreg.match(match.group(1))
                best_reactors = lmatch.group('reactors')
                playerOS = lmatch.group('OS')
                if not best_reactors and playerOS not in {'Linux', 'Unknown OS'}:
                    level_id = next(it)
                    while id2level[level_id]['type'] == 'boss':
                        level_id = next(it)
                for m in filter(None, match.groups()[1:]):
                    smatch = sreg.match(m)
                    if smatch:
                        if smatch.group('OSmark'):
                            username = smatch.group('OSmark') + smatch.group('user')
                        else:
                            username = smatch.group('user')
                        this_score = {'Username': username,
                                      'Cycle Count': int(smatch.group('cycles')),
                                      'Reactor Count': int(smatch.group('reactors')),
                                      'Symbol Count': int(smatch.group('symbols')),
                                      'Upload Time': nowstring,
                                      'Youtube Link': smatch.group('link') if smatch.group('link') else ''}
                        
                        add_score(level_id, this_score, playerOS)


if __name__ == '__main__':
    init()
    #~ load_scores()
    parse_wiki()
    parse_solnet()
    parse_saves()
    #~ dump_scores()
    print_scores()
