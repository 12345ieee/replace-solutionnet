#!/usr/bin/env python3

import csv
import re

from natsort import natsorted

import level_dicts

scoresfile = r"score_dump.csv"
savefile = r'Level.csv'

"""
{'Username': 'LittleBigDej', 'Level Category': '63corvi', 'Level Number': '1', 'Level Name': 'QT-1',
 'Cycle Count': '20', 'Reactor Count': '1', 'Symbol Count': '5', 'Upload Time': '2013-08-15 10:23:14.329898', 'Youtube Link': ''}
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

def should_reject(this_score):
    # In, Out, 2 arrows, Swap = 5 min
    # Max of 2*2*80=320 symbols/reactor
    # In, Swap, Out /2 = 1.5
    return this_score['Symbol Count'] < 5*this_score['Reactor Count'] or \
           this_score['Symbol Count'] > 320*this_score['Reactor Count'] or \
           this_score['Cycle Count'] < 1.5*this_score['Reactor Count']

def printscore_vis(scores, category):
    score = scores[category]
    print('  {:29} U:{:14}  C:{:5} R:{:1} S:{:3}  T:{:26}  {}'.
          format(category, score['Username'],
                 score['Cycle Count'], score['Reactor Count'], score['Symbol Count'],
                 score['Upload Time'], 'Y:'+score['Youtube Link'] if score['Youtube Link'] else '')
         )


fmt_scores_with_bold = ['({}/{}/{}) {}', '(**{}**/{}/{}) {}', '({}/**{}**/{}) {}', '({}/{}/**{}**) {}']

def printscore(score, bold=0):
    fmt_score = fmt_scores_with_bold[bold].format(score['Cycle Count'], score['Reactor Count'], score['Symbol Count'],
                                                  score['Username'])
    if score['Youtube Link']:
        fmt_score = '[{}]({})'.format(fmt_score, score['Youtube Link'])
    print('| {:20}'.format(fmt_score),end=' ')


level_order = {'main':0, 'tf2':1, '63corvi':2, 'researchnet':3}

def reorder_levels(val):
    return (level_order[val[0][0]], val[0][1])


if __name__ == '__main__':
    
    levels = dict()
    
    with open(scoresfile) as csvfile:
        reader = csv.DictReader(csvfile)
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
            
            if level_id not in levels:
                levels[level_id] = {}
                levels[level_id]['Least Cycles'] = this_score
                levels[level_id]['Least Symbols'] = this_score
                levels[level_id]['Least Cycles - Min Reactors'] = this_score
                levels[level_id]['Least Symbols - Min Reactors'] = this_score
            else:
                if tiebreak(this_score, levels[level_id]['Least Cycles'], 'Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'):
                    levels[level_id]['Least Cycles'] = this_score
                    
                if tiebreak(this_score, levels[level_id]['Least Symbols'], 'Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'):
                    levels[level_id]['Least Symbols'] = this_score
                
                if tiebreak(this_score, levels[level_id]['Least Cycles - Min Reactors'], 'Reactor Count', 'Cycle Count', 'Symbol Count', 'Upload Time'):
                    levels[level_id]['Least Cycles - Min Reactors'] = this_score
                    
                if tiebreak(this_score, levels[level_id]['Least Symbols - Min Reactors'], 'Reactor Count', 'Symbol Count', 'Cycle Count', 'Upload Time'):
                    levels[level_id]['Least Symbols - Min Reactors'] = this_score

    with open(savefile) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['passed'] != '1':
                continue
            if row['id'] in level_dicts.save2id:
                level_id = level_dicts.save2id[row['id']]
            else:
                continue
            this_score = {'Username': '12345ieee',
                          'Cycle Count': int(row['cycles']),
                          'Reactor Count': int(row['reactors']),
                          'Symbol Count': int(row['symbols']),
                          'Upload Time': '2017-03-05 09:12:35.408504',
                          'Youtube Link': ''}
            
            if should_reject(this_score):
                continue
            
            if level_id not in levels:
                continue
                #~ levels[level_id] = {}
                #~ levels[level_id]['Least Cycles'] = this_score
                #~ levels[level_id]['Least Symbols'] = this_score
                #~ levels[level_id]['Least Cycles - Min Reactors'] = this_score
                #~ levels[level_id]['Least Symbols - Min Reactors'] = this_score
            else:
                if tiebreak(this_score, levels[level_id]['Least Cycles'], 'Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'):
                    levels[level_id]['Least Cycles'] = this_score
                    
                if tiebreak(this_score, levels[level_id]['Least Symbols'], 'Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'):
                    levels[level_id]['Least Symbols'] = this_score
                
                if tiebreak(this_score, levels[level_id]['Least Cycles - Min Reactors'], 'Reactor Count', 'Cycle Count', 'Symbol Count', 'Upload Time'):
                    levels[level_id]['Least Cycles - Min Reactors'] = this_score
                    
                if tiebreak(this_score, levels[level_id]['Least Symbols - Min Reactors'], 'Reactor Count', 'Symbol Count', 'Cycle Count', 'Upload Time'):
                    levels[level_id]['Least Symbols - Min Reactors'] = this_score

    for name, scores in natsorted(levels.items(), key=reorder_levels):
        print('|{} - {} | Min Cycles | Min Symbols'.format(name[0], name[1]))
        print('|{:13} '.format(level_dicts.id2name[name]), end='')
        printscore(scores['Least Cycles'], bold=1)
        printscore(scores['Least Symbols'], bold=3)
        print()
        if scores['Least Cycles - Min Reactors'] != scores['Least Cycles'] or \
           scores['Least Symbols - Min Reactors'] != scores['Least Symbols']:
            print('|{} - N Reactors '.format(level_dicts.id2name[name]), end='')
            printscore(scores['Least Cycles - Min Reactors'], bold=1)
            printscore(scores['Least Symbols - Min Reactors'], bold=3)
            print()
        print()
