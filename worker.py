#!/usr/bin/env python3

import csv
import sqlite3

from natsort import natsorted

import level_dicts

scoresfile = r"score_dump.csv"
savefiles = [r'save/000.user', r'save/001.user']
playername = '12345ieee'
playerOS = 'Linux' # 'Windows'

"""
{'Username': 'LittleBigDej', 'Level Category': '63corvi', 'Level Number': '1', 'Level Name': 'QT-1',
 'Cycle Count': '20', 'Reactor Count': '1', 'Symbol Count': '5', 'Upload Time': '2013-08-15 10:23:14.329898', 'Youtube Link': ''}
"""

"""
{'id': 'fusion-1', 'passed': 1, 'mastered': 0, 'cycles': 52, 'symbols': 38, 'reactors': 1, 'best_cycles': 52, 'best_symbols': 11, 'best_reactors': 1}
"""

def tiebreak(this_score, best_score, stat1, stat2, stat3, stat4):
    return this_score[stat1] < best_score[stat1] or \
           (this_score[stat1] == best_score[stat1] and \
            (this_score[stat2] < best_score[stat2] or \
             (this_score[stat2] == best_score[stat2] and \
              (this_score[stat3] < best_score[stat3] or \
               (this_score[stat3] == best_score[stat3] and \
                this_score[stat4] < best_score[stat4]
               )
              )
             )
            )
           )

def insert_score(this_score, scores, category, stats):
    if category not in scores or tiebreak(this_score, scores[category], *stats):
        scores[category] = this_score

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

def printscore(score, bold=0):
    fmt_score = fmt_scores_with_bold[bold].format(score['Cycle Count'], score['Reactor Count'], score['Symbol Count'],
                                                  score['Username'])
    if score['Youtube Link']:
        fmt_score = '[{}]({})'.format(fmt_score, score['Youtube Link'])
    print('| {:20}'.format(fmt_score),end=' ')

def printblock(scores, header, cat1, cat2, bold1, bold2):
    if cat1 in scores and cat2 in scores: 
        print(header, end='')
        printscore(scores[cat1], bold=bold1)
        printscore(scores[cat2], bold=bold2)
        print()

level_order = {'main':0, 'tf2':1, '63corvi':2, 'researchnet':3}

def reorder_levels(val):
    return (level_order[val[0]], val[1])


if __name__ == '__main__':
    
    levels = {k: dict() for k in level_dicts.id2level}
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
            
            if should_reject(this_score):
                continue
            
            props = level_dicts.id2level[level_id]
            
            if props['isDeterministic']:
                insert_score(this_score, levels[level_id], 'Least Cycles', ['Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'])
                insert_score(this_score, levels[level_id], 'Least Symbols', ['Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'])
                if not props['isResearch']:
                    insert_score(this_score, levels[level_id], 'Least Cycles - N Reactors', ['Reactor Count', 'Cycle Count', 'Symbol Count', 'Upload Time'])
                    insert_score(this_score, levels[level_id], 'Least Symbols - N Reactors', ['Reactor Count', 'Symbol Count', 'Cycle Count', 'Upload Time'])
            else:
                if this_score['Username'] in user2OS:
                    userOS = user2OS[this_score['Username']]
                else:
                    userOS = 'Unknown OS'
                insert_score(this_score, levels[level_id], 'Least Cycles - {}'.format(userOS), ['Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'])
                insert_score(this_score, levels[level_id], 'Least Symbols - {}'.format(userOS), ['Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'])
                if not props['isResearch']:
                    insert_score(this_score, levels[level_id], 'Least Cycles - {} - N Reactors'.format(userOS), ['Reactor Count', 'Cycle Count', 'Symbol Count', 'Upload Time'])
                    insert_score(this_score, levels[level_id], 'Least Symbols - {} - N Reactors'.format(userOS), ['Reactor Count', 'Symbol Count', 'Cycle Count', 'Upload Time'])


    for savefile in savefiles:
        conn = sqlite3.connect(savefile)
        conn.row_factory = sqlite3.Row
        dbcursor = conn.execute("SELECT * FROM {}".format('Level'))

        for row in dbcursor:
            if row['passed'] == 0:
                continue
            if row['id'] in level_dicts.save2id:
                level_id = level_dicts.save2id[row['id']]
            else:
                continue
            this_score = {'Username': playername,
                          'Cycle Count': row['cycles'],
                          'Reactor Count': row['reactors'],
                          'Symbol Count': row['symbols'],
                          'Upload Time': '2017-03-05 09:12:35.408504',
                          'Youtube Link': ''}
            
            if should_reject(this_score):
                continue
            
            props = level_dicts.id2level[level_id]
            
            if props['isDeterministic']:
                insert_score(this_score, levels[level_id], 'Least Cycles', ['Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'])
                insert_score(this_score, levels[level_id], 'Least Symbols', ['Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'])
                if not props['isResearch']:
                    insert_score(this_score, levels[level_id], 'Least Cycles - N Reactors', ['Reactor Count', 'Cycle Count', 'Symbol Count', 'Upload Time'])
                    insert_score(this_score, levels[level_id], 'Least Symbols - N Reactors', ['Reactor Count', 'Symbol Count', 'Cycle Count', 'Upload Time'])
            else:
                insert_score(this_score, levels[level_id], 'Least Cycles - {}'.format(playerOS), ['Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'])
                insert_score(this_score, levels[level_id], 'Least Symbols - {}'.format(playerOS), ['Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'])
                if not props['isResearch']:
                    insert_score(this_score, levels[level_id], 'Least Cycles - {} - N Reactors'.format(playerOS), ['Reactor Count', 'Cycle Count', 'Symbol Count', 'Upload Time'])
                    insert_score(this_score, levels[level_id], 'Least Symbols - {} - N Reactors'.format(playerOS), ['Reactor Count', 'Symbol Count', 'Cycle Count', 'Upload Time'])
        
        conn.close()

    for level_id in natsorted(levels, key=reorder_levels):
        scores = levels[level_id]
        if not scores:
            continue
        
        print('|{} - {} | Min Cycles | Min Symbols'.format(*level_id))

        level = level_dicts.id2level[level_id]
        
        for OSstring in ['', ' - Windows', ' - Linux', ' - Unknown OS']:
            printblock(scores, '|{name}{OS} '.format(**level, OS=OSstring),
                       'Least Cycles{}'.format(OSstring), 'Least Symbols{}'.format(OSstring),
                       0b100, 0b001)
            printblock(scores, '|{name}{OS} - N Reactors '.format(**level, OS=OSstring),
                       'Least Cycles{} - N Reactors'.format(OSstring), 'Least Symbols{} - N Reactors'.format(OSstring),
                       0b110, 0b011)
        print()
