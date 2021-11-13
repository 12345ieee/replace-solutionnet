import csv
import operator
import os
import re
import shutil
import sqlite3

from abc import ABC, abstractmethod
from io import StringIO
from typing import Tuple

import schem

def make_level_dicts() -> Tuple[dict, dict]:
    """ Returns id2name, name2id"""
    id2name = dict()
    name2id = dict()

    with open('config/levels.csv') as levels_csv:
        reader = csv.DictReader(levels_csv, skipinitialspace=True)
        for row in reader:
            id2name[row['saveId']] = row['name']
            name2id[row['name']] = row['saveId']

    return id2name, name2id

class AbstractWriteBackend(ABC):

    @abstractmethod
    def write_solution(self, db_level_name, author, c, s, r, description, replace_base):
        pass

    @abstractmethod
    def write_component(self, component):
        pass

    @abstractmethod
    def write_members(self, members):
        pass

    @abstractmethod
    def write_pipes(self, pipes):
        pass

    @abstractmethod
    def write_annotations(self, annotations):
        pass

    @abstractmethod
    def commit(self, file_name, validate=False, check_precog=False):
        pass

    @abstractmethod
    def close(self):
        pass


class SaveWriteBackend(AbstractWriteBackend):
    def __init__(self, savefile) -> None:
        self.sv_conn = sqlite3.connect(savefile)
        self.sv_cur = self.sv_conn.cursor()

        self.db_level_id: str
        self.comp_id: int

    def write_solution(self, db_level_name, author, c, s, r, description: str, replace_base=True):

        if replace_base:
            # delete base sol
            self.delete_solution(db_level_name)
            print(f'Adding base solution to {db_level_name}')

            db_level_id = db_level_name
            self.sv_cur.execute(r"""INSERT INTO Level
                                    VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?)""",
                                [db_level_id, c, s, r, c, s, r])
        else:
            # find the largest CE sol used
            self.sv_cur.execute(r"""SELECT MAX(CAST(SUBSTR(id, INSTR(id, '!') + 1) AS int))
                                    FROM Level
                                    WHERE id like ?""", (db_level_name + '%',))
            target = str((self.sv_cur.fetchone()[0] or 0) + 1)
            print(f'Adding solution {target} to {db_level_name}')

            db_level_id = db_level_name + '!' + target
            self.sv_cur.execute(r"""INSERT INTO Level
                                    VALUES (?, 0, ?, ?, ?, ?, 0, 0, 0)""",
                                [db_level_id,
                                 re.sub(r'\r?\n', ' ', description.strip())
                                 if description else 'Unnamed Solution',
                                 c, s, r])
        self.db_level_id = db_level_id

    def delete_solution(self, db_level_id):
        # delete everything (Component, Member, Annotation, Pipe, UndoPtr, Undo) about the old solution
        self.sv_cur.execute(r'SELECT rowid FROM Component WHERE level_id = ?', (db_level_id,))
        comp_ids = [row[0] for row in self.sv_cur]
        if comp_ids:
            qm_list = ','.join('?'*len(comp_ids))
            for table in ['Member', 'Annotation', 'Pipe']:
                self.sv_cur.execute(fr'DELETE FROM {table} WHERE component_id in ({qm_list})', comp_ids)
            for table in ['Component', 'UndoPtr', 'Undo']:
                self.sv_cur.execute(fr'DELETE FROM {table} WHERE level_id = ?', (db_level_id,))

        # delete the solution itself
        self.sv_cur.execute(r'DELETE FROM Level WHERE id = ?', (db_level_id,))

    def delete_all_solutions(self, db_level_name):
        self.sv_cur.execute(r"""SELECT id FROM Level WHERE id like ?""", (db_level_name + '%',))
        for db_level_id in self.sv_cur.fetchall():
            self.delete_solution(db_level_id)

    def write_component(self, component):
        self.sv_cur.execute(r"""INSERT INTO Component
                                VALUES (NULL, ?, ?, ?, ?, NULL, 200, 255, 0)""",
                            [self.db_level_id, component['type'], component['x'], component['y']])
        self.comp_id = self.sv_cur.lastrowid

    def write_members(self, members):
        db_members = [(self.comp_id, *member) for member in members]
        self.sv_cur.executemany(r"""INSERT INTO Member
                                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", db_members)

    def write_pipes(self, pipes):
        db_pipes = [(self.comp_id, output_id, x, y) for output_id, x, y in pipes]
        self.sv_cur.executemany(r"INSERT INTO Pipe VALUES (?, ?, ?, ?)", db_pipes)

    def write_annotations(self, annotations):
        db_annotations = [(self.comp_id, annotation["output_id"], annotation["expanded"],
                           annotation["x"], annotation["y"], annotation["annotation"])
                          for annotation in annotations]
        self.sv_cur.executemany(r"""INSERT INTO Annotation
                                    VALUES (?, ?, ?, ?, ?, ?)""", db_annotations)

    def commit(self, file_name, validate=False, check_precog=False):
        self.db_level_id = None
        self.comp_id = None

    def close(self):
        self.sv_conn.commit()
        self.sv_conn.close()


class ExportWriteBackend(AbstractWriteBackend):

    @staticmethod
    def encode(s: str) -> str:
        return "'" + s.replace("'", "''") + "'" if ',' in s else s

    def __init__(self, folder, id2name) -> None:
        self.f = StringIO()
        self.folder = folder
        self.id2name = id2name

        shutil.rmtree(folder, ignore_errors=True)
        os.mkdir(folder)

    def write_solution(self, db_level_name, author, c, s, r, description: str, replace_base=None):
        level_name = self.encode(self.id2name[db_level_name])
        comma_name = ',' + self.encode(re.sub(r'\r?\n', ' ', description.strip())) \
                     if (description and description != 0) else ''
        print(f"SOLUTION:{level_name},{author},{c}-{r}-{s}{comma_name}",
              file=self.f)

    def write_component(self, component):
        print("COMPONENT:'{0}',{1},{2},''".format(component["type"], component["x"], component["y"]),
              file=self.f)

    def write_members(self, members):
        for member in members:
            print("MEMBER:'{}',{},{},{},{},{},{},{}".format(member["type"], member["arrow_dir"],
                                                            member["choice"], member["layer"],
                                                            member["x"], member["y"],
                                                            member["element_type"], member["element"]),
                  file=self.f)

    def write_pipes(self, pipes):
        for output_id, x, y in pipes:
            print("PIPE:{},{},{}".format(output_id, x, y), file=self.f)

    def write_annotations(self, annotations):
        for annotation in annotations:
            annotation_str = annotation["annotation"].replace("\n", "\\n").replace("\r", "\\r")
            print("ANNOTATION:{},{},{},{},'{}'".format(annotation["output_id"], annotation["expanded"],
                                                       annotation["x"], annotation["y"], annotation_str),
                  file=self.f)

    def commit(self, file_name, validate=False, check_precog=False) -> str:
        export = self.f.getvalue()
        if validate:
            try:
                sol = schem.Solution(export)
                res = sol.run(return_json=True,
                              check_precog=check_precog, verbose=True)

                level_name, _, c, r, s, author, sol_name = operator.itemgetter('level_name', 'resnet_id',
                    'cycles', 'reactors', 'symbols', 'author', 'solution_name')(res)
                if c is None:
                    raise Exception('cycles is None')
                if check_precog and res['precog']:
                    sol_name = '/P ' + (sol_name if sol_name else '')
                comma_name = ',' + self.encode(sol_name) if sol_name else ''
                export = re.sub(r"^(SOLUTION:(?:[^,]+|'(?:[^']|'')+'),[^,]+),"
                                r"(?:\d+-\d+-\d+)"
                                r"(?:,.*)?$",
                                rf"\1,{c}-{r}-{s}{comma_name}", export, 1, re.MULTILINE)

            except Exception as e:
                print(f"{type(e).__name__}: {e}")
                self.f = StringIO()
                return export

        with open(f"{self.folder}/{file_name}.txt", "a") as f:
            print(export, file=f, end='')

        self.f = StringIO()
        return export

    def close(self):
        pass


class NoopWriteBackend(AbstractWriteBackend):

    def write_solution(self, db_level_name, author, c, s, r, description, replace_base):
        print(f'Read [{db_level_name}] {c}-{r}-{s} by {author}')

    def write_component(self, component):
        pass

    def write_members(self, members):
        pass

    def write_pipes(self, pipes):
        # force pipe read to ensure pipe computation
        for _ in pipes:
            pass

    def write_annotations(self, annotations):
        pass

    def commit(self, file_name, validate=False, check_precog=False):
        pass

    def close(self):
        pass
