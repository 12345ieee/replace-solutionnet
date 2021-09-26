#!/usr/bin/env python3

import argparse
import collections
import csv
import itertools
import operator

import psycopg2
import psycopg2.extras

from write_backends import AbstractWriteBackend, ExportWriteBackend, NoopWriteBackend, SaveWriteBackend

Point = collections.namedtuple('Point', ['x', 'y'])

seeds = {}

def reorder_pipe(pipe, seed):
    """Bounds: -24;30;-18;21"""
    x_size = 56
    y_size = 41
    field = [['.']*y_size for _ in range(x_size)]
    for pt in pipe:
        field[pt.x][pt.y] = 'p'

    def find_neighbours(curr):
        return [Point(curr.x+dx, curr.y+dy) for dx,dy in [(1,0), (-1,0), (0,1), (0,-1)]
                                            if field[curr.x+dx][curr.y+dy] == 'p']

    def print_board(header, field):
        print(header + '\n' + '\n'.join(l for l in (''.join(r[-18:] + r[:-18])
                                                    for r in field[-24:] + field[:-24])
                                          if l != '.' * 41))

    curr = seed
    output = [seed]
    field[seed.x][seed.y] = 's'
    backtracking_stack = []
    backtracking_counter = 0
    while True:
        neighbours = find_neighbours(curr)
        if len(neighbours) == 0:
            # see if we've finished all the pipes
            if len(pipe) == len(output):
                return output

            # know when to fold em
            backtracking_counter += 1
            if backtracking_counter == 2000:
                res = output[:-len(backtracking_stack)]
                print_board(f'Incomplete piping ({len(res)}, {len(pipe) - len(res)})', field)
                return res

            # find divergence point
            while not neighbours:
                curr = output.pop()
                field[curr.x][curr.y] = 'p'
                neighbours = backtracking_stack.pop()

        # we try one, if needed backtrack later
        curr = neighbours[0]
        output.append(curr)
        if len(neighbours) > 1 or len(backtracking_stack) > 0:
            backtracking_stack.append(neighbours[1:])
            field[curr.x][curr.y] = 't'
        else:
            field[curr.x][curr.y] = 'a'


def load_solution(sn_cur, write_backend: AbstractWriteBackend, solution, replace_base_sol):
    sol_id, db_level_name, player_name, comment, c, s, r = solution
    write_backend.write_solution(db_level_name, player_name, c, s, r, comment, replace_base_sol)

    # get the reactors from db
    sn_cur.execute(r"""  SELECT component_id, type, x, y
                           FROM components
                          WHERE solution_id = %s
                       ORDER BY component_id""", (sol_id,))
    reactors = sn_cur.fetchall()

    for reactor in reactors:
        comp_id = reactor['component_id']
        write_backend.write_component(reactor)

        # get all its members
        sn_cur.execute(r"""SELECT type, arrow_dir, choice, layer, x, y, element_type, element
                           FROM members
                           WHERE component_id = %s""", (comp_id,))
        write_backend.write_members(sn_cur)

        # get all its pipes
        sn_cur.execute(r"SELECT output_id, x, y FROM pipes WHERE component_id = %s", (comp_id,))
        pipes = ([], [])
        for pipe_point in sn_cur:
            pipes[pipe_point['output_id']].append(Point(pipe_point['x'], pipe_point['y']))
        for out_id, pipe in enumerate(pipes):
            if not pipe:
                continue
            reordered_pipe = reorder_pipe(pipe, seeds[(reactor['type'], out_id)])
            write_backend.write_pipe(out_id, reordered_pipe)

    write_backend.commit(db_level_name if args.group_exports_by_level else sol_id, args.schem, args.check_precog)

def clean_to_pareto(level_sols):
    result = []
    for _, solutions in level_sols:
        pareto = []
        for solution in solutions:
            new_pareto = []
            for stored in pareto:
                if solution[4] >= stored[4] and solution[5] >= stored[5] and solution[6] >= stored[6]:
                    # we are beaten by a solution in the stack
                    break
                elif solution[4] <= stored[4] and solution[5] <= stored[5] and solution[6] <= stored[6]:
                    # we win against the old sol, we'll add once at the end
                    pass
                else:
                    # no one won, we keep the old
                    new_pareto.append(stored)
            else:
                # we didn't get beat, so we replace the paretos
                new_pareto.append(solution)
                pareto = new_pareto
        result += sorted(pareto, key=operator.itemgetter(4,6,5)) #crs
    return result

def main():
    global seeds

    # connections
    sn_conn = psycopg2.connect(dbname='solutionnet')
    sn_cur = sn_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if args.file_save:
        write_backend = SaveWriteBackend(args.file_save)
    elif args.export_folder:
        id2name, _ = ExportWriteBackend.make_level_dicts()
        write_backend = ExportWriteBackend(id2name, args.export_folder)
    else:
        write_backend = NoopWriteBackend()

    # populate seeds map
    with open('config/seeds.csv') as levelscsv:
        reader = csv.DictReader(levelscsv, skipinitialspace=True)
        for row in reader:
            seeds[(row['type'], int(row['output']))] = Point(int(row['x']), int(row['y']))

    query = r'''SELECT solution_id, internal_name, username, description,
                       cycle_count, symbol_count, reactor_count
                FROM solutions NATURAL JOIN levels NATURAL JOIN users'''
    if args.all:
        params = ()
    else:
        query += ' WHERE solution_id in %s'
        params = (tuple(args.sol_ids),)

    if args.pareto_only:
        sn_cur.execute(query + ' ORDER BY internal_name', params)
        level_sols = itertools.groupby(sn_cur, operator.itemgetter('internal_name'))
        solutions = clean_to_pareto(level_sols)
    else:
        sn_cur.execute(query + ' ORDER BY 1', params)
        solutions = sn_cur.fetchall()

    for solution in solutions:
        sol_id = solution['solution_id']
        print(f'Loading solution {sol_id}')
        load_solution(sn_cur, write_backend, solution, args.replace_sols)

    write_backend.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file-save", nargs="?", const=r'data/solnet.user')
    parser.add_argument("-e", "--export-folder", nargs="?", const=r'exports')
    gr_in = parser.add_mutually_exclusive_group()
    gr_in.add_argument("--all", action="store_true")
    gr_in.add_argument("sol_ids", nargs='*', type=int, default=[47424])
    parser.add_argument("--replace-sols", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--group-exports-by-level", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--pareto-only", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("-s", "--schem", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--check-precog", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    main()
