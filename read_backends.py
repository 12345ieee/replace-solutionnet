import collections
import csv
import itertools
import operator
import sqlite3
from abc import ABC, abstractmethod
from typing import Iterable

import psycopg2
import psycopg2.extras


class AbstractReadBackend(ABC):

    @staticmethod
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

    @abstractmethod
    def read_solutions(self, ids: list, pareto_only: bool) -> Iterable:
        pass

    @abstractmethod
    def read_components(self, sol_id) -> Iterable:
        pass

    @abstractmethod
    def read_members(self, comp_id):
        pass

    @abstractmethod
    def read_pipes(self, comp_id, component_type=None):
        pass

    @abstractmethod
    def read_annotations(self, comp_id):
        pass

    @abstractmethod
    def close(self):
        pass

class SaveReadBackend(AbstractReadBackend):

    def __init__(self, savefile) -> None:
        self.conn = sqlite3.connect(f'file:{savefile}?mode=ro', uri=True)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

    def read_solutions(self, ids: list, pareto_only: bool) -> Iterable:
        # we use cycles != 0 as a good proxy for finished
        query = """SELECT id, cycles, reactors, symbols, mastered
                   FROM Level
                   WHERE cycles != 0"""
        if not ids:
            params = ()
        else:
            query += f" AND id in ({','.join('?' * len(ids))})"
            params = ids

        query += ' ORDER BY id'
        self.cur.execute(query, params)

        if pareto_only:
            level_sols = itertools.groupby(self.cur, operator.itemgetter('internal_name'))
            return self.clean_to_pareto(level_sols)
        else:
            return self.cur.fetchall()

    def read_components(self, sol_id) -> Iterable:
        return self.cur.execute("SELECT rowid,type,x,y,name "
                                "FROM component "
                                "WHERE level_id=? "
                                "ORDER BY rowid",
                                (sol_id,))

    def read_members(self, comp_id):
        return self.cur.execute("SELECT type, arrow_dir, choice, layer, x, y, element_type, element "
                                "FROM Member "
                                "WHERE component_id=? "
                                "ORDER BY rowid",
                                (comp_id,))

    def read_pipes(self, comp_id, component_type=None):
        return self.cur.execute("SELECT output_id, x, y "
                                "FROM Pipe "
                                "WHERE component_id=? "
                                "ORDER BY rowid",
                                (comp_id,))

    def read_annotations(self, comp_id):
        return self.cur.execute("SELECT output_id, expanded, x, y, annotation "
                                "FROM Annotation "
                                "WHERE component_id=?",
                                (comp_id,))

    def close(self):
        self.conn.close()

class SolnetReadBackend(AbstractReadBackend):
    Point = collections.namedtuple('Point', ['x', 'y'])

    @classmethod
    def make_seed_map(cls):
        with open('config/seeds.csv') as levelscsv:
            reader = csv.DictReader(levelscsv, skipinitialspace=True)
            return {(row['type'], int(row['output'])):
                    cls.Point(int(row['x']), int(row['y']))
                    for row in reader}

    @classmethod
    def find_neighbours(cls, curr, field):
        return [cls.Point(curr.x+dx, curr.y+dy) for dx,dy in [(1,0), (-1,0), (0,1), (0,-1)]
                                                if field[curr.x+dx][curr.y+dy] == 'p']

    def __init__(self) -> None:
        self.conn = psycopg2.connect(dbname='solutionnet')
        self.conn.set_session(readonly=True)
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        self.seeds = self.make_seed_map()

    def read_solutions(self, ids: list, pareto_only: bool) -> Iterable:
        query = r'''SELECT solution_id, internal_name, username, description,
                    cycle_count, symbol_count, reactor_count
            FROM solutions NATURAL JOIN levels NATURAL JOIN users'''

        if not ids:
            params = ()
        else:
            query += ' WHERE solution_id in %s'
            params = (tuple(ids),)

        if pareto_only:
            self.cur.execute(query + ' ORDER BY internal_name', params)
            level_sols = itertools.groupby(self.cur, operator.itemgetter('internal_name'))
            return self.clean_to_pareto(level_sols)
        else:
            self.cur.execute(query + ' ORDER BY 1', params)
            return self.cur.fetchall()

    def read_components(self, sol_id) -> Iterable:
        self.cur.execute(r"""  SELECT component_id, type, x, y
                                 FROM components
                                WHERE solution_id = %s
                             ORDER BY component_id""", (sol_id,))
        return self.cur.fetchall()

    def read_members(self, comp_id):
        self.cur.execute(r"""SELECT type, arrow_dir, choice, layer, x, y, element_type, element
                             FROM members
                             WHERE component_id = %s""", (comp_id,))
        return self.cur.fetchall()

    def read_pipes(self, comp_id, component_type=None):
        self.cur.execute(r"""SELECT output_id, x, y
                           FROM pipes
                           WHERE component_id = %s
                           ORDER BY output_id""", (comp_id,))
        pipes = itertools.groupby(self.cur, operator.itemgetter('output_id'))
        for out_id, raw_pipe in pipes:
            pipe = [self.Point(pipe_point['x'], pipe_point['y']) for pipe_point in raw_pipe]
            reordered_pipe = self._reorder_pipe(pipe, self.seeds[component_type, out_id])
            yield from ((out_id, x, y) for x, y in reordered_pipe)

    @classmethod
    def _reorder_pipe(cls, pipe, seed):

        def print_board(header):
            print(header + '\n' + '\n'.join(l for l in (''.join(r[-18:] + r[:-18])
                                                        for r in field[-24:] + field[:-24])
                                            if l != '.' * 41))

        # Bounds: -24;30;-18;21
        x_size = 56
        y_size = 41
        field = [['.']*y_size for _ in range(x_size)]
        for pt in pipe:
            field[pt.x][pt.y] = 'p'

        # check if the pipe end is alone, so we can meet the pipe in the middle
        other_seed = None
        for pt in pipe:
            if len(cls.find_neighbours(pt, field)) == 1 and pt != seed:
                other_seed = pt
                field[other_seed.x][other_seed.y] = 'e'
                break

        # mark the seed after we've found the other seed
        field[seed.x][seed.y] = 's'

        if not other_seed:
            # do it on one side, 2k tries
            output = cls._build_pipe(field, [seed], len(pipe), None, 2000)
            if len(output) != len(pipe):
                print_board(f'Incomplete piping ({len(output)}, {len(pipe) - len(output)})')
            return output
        else:
            # try meeting in the middle, 5*2*200 tries
            out_forward = [seed]
            out_backward = [other_seed]
            for i in range(6):
                out_forward = cls._build_pipe(field, out_forward, len(pipe) - len(out_backward),
                                              out_backward[-1], 200, clean=True)
                out_backward = cls._build_pipe(field, out_backward, len(pipe) - len(out_forward),
                                               out_forward[-1], 200, clean=i != 5)
                if len(out_forward) + len(out_backward) == len(pipe):
                    return out_forward + out_backward[::-1]
            print_board(f'Incomplete piping ({len(out_forward)}, {len(pipe) - len(out_forward)})')
            return out_forward


    @classmethod
    def _build_pipe(cls, field, starting_output, target_len, target_point=None, iterations=2000, clean=False) -> list:

        def is_neighbour(pt1: cls.Point, pt2: cls.Point) -> bool:
            return abs(pt1.x - pt2.x) <= 1 and abs(pt1.y - pt2.y) <= 1

        curr = starting_output[-1]
        output = starting_output[:]
        backtracking_stack = []
        backtracking_counter = 0
        while True:
            neighbours = cls.find_neighbours(curr, field)
            if len(neighbours) == 0:
                # see if we've finished all the pipes
                if len(output) == target_len and (not target_point or is_neighbour(output[-1], target_point)):
                    return output

                # know when to fold em
                backtracking_counter += 1
                if backtracking_counter == iterations:
                    if clean:
                        for pt in output[-len(backtracking_stack):]: # clean up temps for next run
                            field[pt.x][pt.y] = 'p'
                    return output[:-len(backtracking_stack)]

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

    def read_annotations(self, comp_id):
        pass

    def close(self):
        self.conn.close()