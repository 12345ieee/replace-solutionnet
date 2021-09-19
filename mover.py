#!/usr/bin/env python3

import argparse
import collections
import csv
import sys

import psycopg2
import psycopg2.extras

from write_backends import SaveWriteBackend

Point = collections.namedtuple('Point', ['x', 'y'])

sn_cur = None
write_backend = None
seeds = {}

def reorder_pipe(pipe, seed):
    """Bounds: -24;30;-18;21"""
    x_size = 56
    y_size = 41
    field = [[0]*y_size for _ in range(x_size)]
    for pt in pipe:
        field[pt.x][pt.y] = 1

    output = [seed]
    if field[seed.x][seed.y] == 0:
        # bad stuff happened
        print(f'Seed {seed} not found')
        return output

    prev = None
    curr = seed
    while True:
        adiacence = [(curr.x+dx, curr.y+dy, field[curr.x+dx][curr.y+dy]) for dx,dy in [(1,0), (-1,0), (0,1), (0,-1)]]
        s = sum(val[2] for val in adiacence)
        if prev is None and s == 1:
            # starting, good case
            prev,curr = curr,Point(*([(x,y) for x,y,o in adiacence if o == 1][0]))
            output.append(curr)
        elif prev is not None and s == 2:
            # continuing, good case
            prev,curr = curr,Point(*([(x,y) for x,y,o in adiacence if o == 1 and not (x == prev.x and y == prev.y)][0]))
            output.append(curr)
        else:
            # see if we've finished all the pipes
            if len(output) != len(pipe):
                print('Incomplete piping')
            return output


def load_solution(sol_id, replace_base_sol):
    # get the level and the score
    sn_cur.execute(r'''select internal_name, description, cycle_count, symbol_count, reactor_count
                         from solutions s, levels l
                        where s.level_id = l.level_id
                          and s.solution_id = %s;''', (sol_id,))
    solution = sn_cur.fetchone()
    if solution is None:
        print(f'ERROR: Invalid solution id: {sol_id}')
        sys.exit()

    db_level_name, comment, *score = solution
    write_level_id = write_backend.write_solution(db_level_name, score, comment, replace_base_sol)

    # get the reactors from db
    sn_cur.execute(r"""  select component_id, type, x, y
                           from components
                          where solution_id = %s
                       order by component_id;""", (sol_id,))
    reactors = sn_cur.fetchall()

    for reactor in reactors:
        comp_id = reactor['component_id']
        write_comp_id = write_backend.write_component(write_level_id, reactor)

        # get all its pipes
        sn_cur.execute(r"select output_id, x, y from pipes where component_id = %s;", (comp_id,))
        pipes = ([], [])
        for pipe_point in sn_cur:
            pipes[pipe_point['output_id']].append(Point(pipe_point['x'], pipe_point['y']))
        for out_id, pipe in enumerate(pipes):
            if not pipe:
                continue
            reordered_pipe = reorder_pipe(pipe, seeds[(reactor['type'], out_id)])
            write_backend.write_pipe(write_comp_id, out_id, reordered_pipe)

        # get all its symbols
        sn_cur.execute(r"""SELECT type, arrow_dir, choice, layer, x, y, element_type, element
                           FROM members
                           WHERE component_id = %s;""", (comp_id,))
        write_backend.write_members(write_comp_id, sn_cur)

def main():
    global sn_cur
    global write_backend
    global seeds

    # connections
    sn_conn = psycopg2.connect(dbname='solutionnet')
    sn_cur = sn_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    write_backend = SaveWriteBackend(args.savefile)

    # populate seeds map
    with open('config/seeds.csv') as levelscsv:
        reader = csv.DictReader(levelscsv, skipinitialspace=True)
        for row in reader:
            seeds[(row['type'], int(row['output']))] = Point(int(row['x']), int(row['y']))

    if args.all:
        sn_cur.execute(r'SELECT solution_id FROM solutions ORDER BY 1')
        sol_ids = [s[0] for s in sn_cur]
    else:
        sol_ids = args.sol_ids

    for sol_id in sol_ids:
        print(f'Loading solution {sol_id}')
        load_solution(sol_id, args.replace_sols)

    write_backend.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--savefile", action="store", default=r'data/solnet.user')
    parser.add_argument("--replace-sols", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("sol_ids", nargs='*', type=int, default=[47424])
    args = parser.parse_args()

    main()
