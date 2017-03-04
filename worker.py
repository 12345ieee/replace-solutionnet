#!/usr/bin/env python3

import csv

from natsort import natsorted

filename=r"score_dump.csv"

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


if __name__ == '__main__':
    
    levels = dict()
    
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            level_name = (row['Level Category'], row['Level Number'], row['Level Name'])
            this_score = {'Username': row['Username'],
                          'Cycle Count': int(row['Cycle Count']),
                          'Reactor Count': int(row['Reactor Count']),
                          'Symbol Count': int(row['Symbol Count']),
                          'Upload Time': row['Upload Time'],
                          'Youtube Link': row['Youtube Link']}
            if level_name not in levels:
                levels[level_name] = {}
                levels[level_name]['Least Cycles'] = this_score
                levels[level_name]['Least Symbols'] = this_score
                levels[level_name]['Least Cycles - Min reactors'] = this_score
                levels[level_name]['Least Symbols - Min reactors'] = this_score
            else:
                if tiebreak(this_score, levels[level_name]['Least Cycles'], 'Cycle Count', 'Reactor Count', 'Symbol Count', 'Upload Time'):
                    levels[level_name]['Least Cycles'] = this_score
                    
                if tiebreak(this_score, levels[level_name]['Least Symbols'], 'Symbol Count', 'Reactor Count', 'Cycle Count', 'Upload Time'):
                    levels[level_name]['Least Symbols'] = this_score

    for name, scores in natsorted(levels.items()):
        print(name)
        for category, score in sorted(scores.items()):
            print('',category, ' U:', score['Username'], 
                  ' C:', score['Cycle Count'], ' R:', score['Reactor Count'], ' S:', score['Symbol Count'], 
                  ' T:', score['Upload Time'], ' Y:', score['Youtube Link'] if score['Youtube Link'] else '\'\'')
