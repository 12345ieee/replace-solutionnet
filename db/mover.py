#!/usr/bin/env python3

import collections
import argparse
import sqlite3

import psycopg2
import psycopg2.extras

replace_old_score = True

Pipe = collections.namedtuple('Pipe', ['output', 'x', 'y'])

sn_cur = None
sv_cur = None
seq_comp = None
seq_memb = None 

def load_solution(sol_id):
    global seq_comp
    global seq_memb
    # get the level and the score
    sn_cur.execute(r'''select internal_name, cycle_count, symbol_count, reactor_count
                         from solutions s, levels l
                        where s.level_id = l.level_id
                          and s.solution_id = %s;''', (sol_id,))
    solution = sn_cur.fetchone()
    int_level_name = solution['internal_name']
    triplet = solution[1:]
    
    # check if the level has a solution already
    sv_cur.execute(r"SELECT count(*) from Level where id = ?", (int_level_name,))
    count = sv_cur.fetchone()[0]
    if count == 0:
        # need to insert the level
        print(f'Adding new solution to {int_level_name}')
        sv_cur.execute(r"""INSERT INTO Level VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?)""", [int_level_name, *triplet, *triplet])
    else:
        # there's already a solution (possibly empty) in the file
        if not replace_old_score:
            print(f'There\'s already a solution to {int_level_name}, doing nothing')
            return
        
        print(f'Replacing previous solution to {int_level_name}')
        sv_cur.execute(r"""UPDATE Level
                           SET passed = 1, mastered = 0, cycles = ?, symbols = ?, reactors = ?
                           WHERE id = ?""", triplet + [int_level_name])
        # delete everything (Component, Member, Annotation, Pipe, UndoPtr, Undo) about the old solution
        sv_cur.execute(r'SELECT rowid FROM Component WHERE level_id = ?', (int_level_name,))
        comp_ids = [row[0] for row in sv_cur.fetchall()]
        qm_list = ','.join('?'*len(comp_ids))
        for table in ['Member', 'Annotation', 'Pipe']:
            sv_cur.execute(fr'DELETE FROM {table} WHERE component_id in ({qm_list})', comp_ids)
        for table in ['Component', 'UndoPtr', 'Undo']:
            sv_cur.execute(fr'DELETE FROM {table} WHERE level_id = ?', (int_level_name,))
    
    # get the reactors from db
    sn_cur.execute(r"""  select component_id, type, x, y
                           from components
                          where solution_id = %s
                       order by component_id;""", (sol_id,))
    reactors = sn_cur.fetchall()

    for reactor in reactors:
        comp_id = reactor['component_id']
        seq_comp += 1
        sv_cur.execute(r"""INSERT INTO Component
                           VALUES (?, ?, ?, ?, ?, NULL, 200, 255, 0)""",
                                  [seq_comp, int_level_name, reactor['type'], reactor['x'], reactor['y']])
        
        # get all its pipes
        #~ sn_cur.execute(r"select * from pipes where component_id = %s;", (comp_id,))
        #~ pipes = []
        #~ for pipe in sn_cur:
            #~ sv_cur.execute(r"INSERT INTO Pipe VALUES (?, ?, ?, ?)", [seq_comp, pipe['output'], pipe['x'], pipe['y']])
        
        # get all its symbols
        sn_cur.execute(r"select * from members where component_id = %s;", (comp_id,))
        for symbol in sn_cur:
            seq_memb += 1
            sv_cur.execute(r"""INSERT INTO Member
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                               [seq_memb, seq_comp] + symbol[2:])

def main(save_path, sol_ids):
    global sn_cur
    global sv_cur
    global seq_comp
    global seq_memb
    
    sn_conn = psycopg2.connect(dbname='solutionnet')
    sn_cur = sn_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    sv_conn = sqlite3.connect(save_path)
    sv_cur = sv_conn.cursor()
    
    # get the sequences
    seqs = sv_cur.execute('select seq from sqlite_sequence order by 1')
    seq_comp, seq_memb = (int(seq[0]) for seq in seqs)
    
    for sol_id in sol_ids:
        print(f'Loading solution {sol_id}')
        load_solution(sol_id)
    
    # write sequences
    sv_cur.execute(fr"""UPDATE sqlite_sequence
                        SET seq = CASE
                                        WHEN name = 'Component' THEN {seq_comp}
                                        WHEN name = 'Member'    THEN {seq_memb}
                                  END""")
    sv_conn.commit()
    sv_conn.close()


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--savefile", action="store", default=r'saves/111.user')
    parser.add_argument("sol_ids", nargs='*', type=int, default=47424)
    args = parser.parse_args()

    main(args.savefile, args.sol_ids)
