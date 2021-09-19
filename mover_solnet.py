#!/usr/bin/env python3

import argparse
import collections
import csv

import psycopg2
import psycopg2.extras

from write_backends import ExportWriteBackend, SaveWriteBackend, make_level_dicts

Point = collections.namedtuple('Point', ['x', 'y'])

sn_cur: psycopg2.extensions.cursor
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


def load_solution(solution, replace_base_sol):
    sol_id, db_level_name, player_name, comment, c, s, r = solution
    write_level_id = write_backend.write_solution(db_level_name, player_name, c, s, r,
                                                  comment, replace_base_sol)

    # get the reactors from db
    sn_cur.execute(r"""  select component_id, type, x, y
                           from components
                          where solution_id = %s
                       order by component_id;""", (sol_id,))
    reactors = sn_cur.fetchall()

    for reactor in reactors:
        comp_id = reactor['component_id']
        write_comp_id = write_backend.write_component(write_level_id, reactor)

        # get all its members
        sn_cur.execute(r"""SELECT type, arrow_dir, choice, layer, x, y, element_type, element
                           FROM members
                           WHERE component_id = %s;""", (comp_id,))
        write_backend.write_members(write_comp_id, sn_cur)

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

    write_backend.commit(db_level_name if args.group_exports_by_level else sol_id, args.schem)

def main():
    global sn_cur
    global write_backend
    global seeds

    # connections
    sn_conn = psycopg2.connect(dbname='solutionnet')
    sn_cur = sn_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if args.file_save:
        write_backend = SaveWriteBackend(args.file_save)
    elif args.export_folder:
        id2name, _ = make_level_dicts()
        write_backend = ExportWriteBackend(id2name, args.export_folder)

    # populate seeds map
    with open('config/seeds.csv') as levelscsv:
        reader = csv.DictReader(levelscsv, skipinitialspace=True)
        for row in reader:
            seeds[(row['type'], int(row['output']))] = Point(int(row['x']), int(row['y']))

    query = r'''SELECT solution_id, internal_name, username, description,
                       cycle_count, symbol_count, reactor_count
                FROM solutions NATURAL JOIN levels NATURAL JOIN users'''
    if args.all:
        sn_cur.execute(query + ' ORDER BY 1')
    else:
        sn_cur.execute(query + ' WHERE solution_id in (%s)', (args.sol_ids,))

    solutions = sn_cur.fetchall()

    for solution in solutions:
        sol_id = solution['solution_id']
        print(f'Loading solution {sol_id}')
        load_solution(solution, args.replace_sols)

    write_backend.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    gr_out = parser.add_mutually_exclusive_group(required=True)
    gr_out.add_argument("-f", "--file-save", nargs="?", const=r'data/solnet.user')
    gr_out.add_argument("-e", "--export-folder", nargs="?", const=r'exports')
    gr_in = parser.add_mutually_exclusive_group()
    gr_in.add_argument("--all", action="store_true")
    gr_in.add_argument("sol_ids", nargs='*', type=int, default=[47424])
    parser.add_argument("--replace-sols", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--group-exports-by-level", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("-s", "--schem", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    main()