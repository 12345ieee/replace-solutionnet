import collections
import csv
import itertools
import operator
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List

import psycopg2
import psycopg2.extras
import schem


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

    def read_solutions(self, ids: list|None, pareto_only: bool) -> Iterable:
        # we use cycles != 0 as a good proxy for finished
        query = """SELECT id, cycles, reactors, symbols, mastered
                   FROM Level
                   WHERE cycles != 0"""
        if not ids:
            query += " AND id not like 'custom-%'"
            params = ()
        else:
            query += f""" AND iif(instr(id, '!') > 0,
                                  substr(id, 0, instr(id, '!')),
                                  id)
                              in ({','.join('?' * len(ids))})"""
            params = ids

        query += ' ORDER BY id'
        self.cur.execute(query, params)

        if pareto_only:
            level_sols = itertools.groupby(self.cur, operator.itemgetter('id'))
            return self.clean_to_pareto(level_sols)
        else:
            return self.cur.fetchall()

    def read_components(self, sol_id) -> Iterable:
        self.cur.execute("SELECT rowid,type,x,y,name "
                         "FROM component "
                         "WHERE level_id=? "
                         "ORDER BY rowid",
                         (sol_id,))
        return self.cur.fetchall()

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
            if isinstance(ids[0], int):
                query += ' WHERE solution_id in %s'
            elif isinstance(ids[0], str):
                query += ' WHERE internal_name in %s'
            params = (tuple(ids),)

        if pareto_only:
            self.cur.execute(query + ' ORDER BY internal_name, solution_id', params)
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
        seeds = []
        reordered_pipes = []
        for out_id, raw_pipe in pipes:
            pipe = [self.Point(pipe_point['x'], pipe_point['y']) for pipe_point in raw_pipe]
            seed: SolnetReadBackend.Point = self.seeds[component_type, out_id]
            seeds.append((out_id, seed.x, seed.y))
            reordered_pipes.extend((out_id, x, y) for x, y in self._reorder_pipe(pipe, seed)[1:])
        # print seeds first to avoid the pipe bug
        return seeds + reordered_pipes

    class Field:
        """Bounds: -24;30;-18;21"""
        size_x = 56
        size_y = 41
        base_x = -24
        base_y = -18

        def __init__(self) -> None:
            self.field = [['.']*self.size_x for _ in range(self.size_y)]

        def __getitem__(self, pt: 'SolnetReadBackend.Point'):
            return self.field[pt.y][pt.x]

        def __setitem__(self, pt: 'SolnetReadBackend.Point', value: str):
            self.field[pt.y][pt.x] = value

        def find_neighbours(self, curr: 'SolnetReadBackend.Point',
                            include_end: 'SolnetReadBackend.Point'|None = None):
            neighbours = [SolnetReadBackend.Point(curr.x+dx, curr.y+dy)
                    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
                    if self.field[curr.y+dy][curr.x+dx] == 'p' or (curr.x+dx, curr.y+dy) == include_end]
            return neighbours

        def print(self, header=None):
            if header:
                print(header, sep='')
            print('\n' + '\n'.join(l for l in (''.join(r[self.base_x:] + r[:self.base_x])
                                               for r in self.field[self.base_y:] + self.field[:self.base_y])
                                   if l != '.' * self.size_x))


    @classmethod
    def _reorder_pipe(cls, pipe: List[Point], seed: Point) -> List[Point]:

        field = cls.Field()

        for pt in pipe:
            field[pt] = 'p'

        # check if the pipe end is alone, so we can meet the pipe in the middle
        other_seed = None
        for pt in pipe:
            if len(field.find_neighbours(pt)) == 1 and pt != seed:
                other_seed = pt
                field[other_seed] = 'e'
                break

        # mark the seed after we've found the other seed
        field[seed] = 's'

        if not other_seed:
            # do it on one side, 2k tries
            output = cls._build_pipe(field, [seed], len(pipe), None, 2000)
            if len(output) == len(pipe):
                return output
        else:
            # try meeting in the middle, 2*(1+2+3+4=10)*100 tries
            out_forward = [seed]
            out_backward = [other_seed]
            for i in range(1, 5):
                out_forward = cls._build_pipe(field, out_forward, len(pipe) - len(out_backward),
                                              out_backward[-1], i * 100, clean=True)
                out_backward = cls._build_pipe(field, out_backward, len(pipe) - len(out_forward),
                                               out_forward[-1], i * 100, clean=i != 4)
                if len(out_forward) + len(out_backward) == len(pipe):
                    return out_forward + out_backward[::-1]
            output = out_forward

        field.print(f'Incomplete piping ({len(output)}, {len(pipe) - len(output)})')
        return output


    @classmethod
    def _build_pipe(cls, field: Field, starting_output: List[Point], target_len,
                    target_point: Point|None = None, iterations=2000, clean=False) -> List[Point]:

        def is_neighbour(pt1: SolnetReadBackend.Point, pt2: SolnetReadBackend.Point) -> bool:
            return abs(pt1.x - pt2.x) + abs(pt1.y - pt2.y) == 1

        curr = starting_output[-1]
        output = starting_output[:]
        backtracking_stack = []
        backtracking_counter = 0
        while True:
            neighbours = field.find_neighbours(curr)

            # look 1 ahead to prune paths
            if len(neighbours) > 1:
                # as a side effect the sort sorts same-path length by LUDR, which is exactly reverse-connection order
                npaths = sorted([(len(field.find_neighbours(n, include_end=target_point)), n) for n in neighbours])
                neighbours = []
                for np in npaths:
                    neighbour_paths = np[0]
                    if neighbour_paths == 0:
                        # we have a dead end and we're not finished, surrender so we backtrack
                        break
                    elif neighbour_paths == 1:
                        # that's either the newly discovered end (so we can't go there now)
                        # or it's a forced point of passage, so we go there now
                        neighbours.append(np[1])
                        if target_point:
                            break
                    else:
                        neighbours.append(np[1])

            if len(neighbours) == 0:
                # see if we've finished all the pipes
                if len(output) == target_len and (not target_point or is_neighbour(output[-1], target_point)):
                    return output

                # know when to fold em
                backtracking_counter += 1
                if backtracking_counter == iterations:
                    if clean:
                        for pt in output[-len(backtracking_stack):]: # clean up temps for next run
                            field[pt] = 'p'
                    return output[:-len(backtracking_stack)]

                # find divergence point
                while not neighbours:
                    curr = output.pop()
                    field[curr] = 'p'
                    neighbours = backtracking_stack.pop()

            # we try one, if needed backtrack later
            curr = neighbours[0]
            output.append(curr)
            if len(neighbours) > 1 or len(backtracking_stack) > 0:
                backtracking_stack.append(neighbours[1:])
                field[curr] = 't'
            else:
                field[curr] = 'a'
            # field.print()

    def read_annotations(self, comp_id):
        pass

    def close(self):
        self.conn.close()

class ExportReadBackend(AbstractReadBackend):

    def __init__(self, folder:str, name2id) -> None:
        self.folder = folder
        self.name2id = name2id

    def read_solutions(self, ids: list, pareto_only: bool) -> Iterable:
        sols = self._read_solution_files(ids)
        if pareto_only:
            level_sols = itertools.groupby(sorted(sols, key=operator.itemgetter(1)), operator.itemgetter(1))
            return self.clean_to_pareto(level_sols)
        else:
            return sols

    def _read_solution_files(self, ids: list) -> Iterable:
        sol_files = sorted(Path(self.folder).glob('*.txt'), key=lambda f: int(f.stem))
        for sol_file in sol_files:
            sol_id = int(sol_file.stem)
            if not ids or (sol_id in ids):
                with sol_file.open('r') as f:
                    sol = schem.Solution(f.readline())
                    assert sol.expected_score
                yield sol_id, self.name2id[sol.level.name], sol.author, sol.name, \
                      sol.expected_score[0], sol.expected_score[2], sol.expected_score[1]

    def read_components(self, sol_id) -> Iterable:
        return []

    def read_members(self, comp_id):
        return []

    def read_pipes(self, comp_id, component_type=None):
        return []

    def read_annotations(self, comp_id):
        return []

    def close(self):
        pass
