#!/usr/bin/env python3

import os
import shutil
import sqlite3
import csv

from abc import ABC, abstractmethod
from io import StringIO
from typing import Tuple

import schem


class AbstractWriteBackend(ABC):

    @abstractmethod
    def write_solution(self, db_level_name, player_name, c, s, r, description, replace_base) -> str:
        pass

    @abstractmethod
    def write_component(self, write_level_id, component) -> int:
        pass

    @abstractmethod
    def write_pipe(self, write_comp_id, out_id, ordered_pipe):
        pass

    @abstractmethod
    def write_pipes(self, write_comp_id, pipes):
        pass

    @abstractmethod
    def write_members(self, write_comp_id, members):
        pass

    @abstractmethod
    def write_annotations(self, write_comp_id, annotations):
        pass

    @abstractmethod
    def commit(self, name, validate=False):
        pass

    @abstractmethod
    def close(self):
        pass

class SaveWriteBackend(AbstractWriteBackend):
    def __init__(self, savefile) -> None:
        self.sv_conn = sqlite3.connect(savefile)
        self.sv_cur = self.sv_conn.cursor()

    def write_solution(self, db_level_name, player_name, c, s, r, description, replace_base=True) -> str:

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
                                    [db_level_id, description.strip() or 'Unnamed Solution', c, s, r])
        return db_level_id

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


    def write_component(self, write_level_id, component):
        self.sv_cur.execute(r"""INSERT INTO Component
                                VALUES (NULL, ?, ?, ?, ?, NULL, 200, 255, 0)""",
                            [write_level_id, component['type'], component['x'], component['y']])
        return self.sv_cur.lastrowid

    def write_pipe(self, write_comp_id, out_id, ordered_pipe):
        pipe = [(write_comp_id, out_id, pipe_point.x, pipe_point.y) for pipe_point in ordered_pipe]
        self.sv_cur.executemany(r"INSERT INTO Pipe VALUES (?, ?, ?, ?)", pipe)

    def write_pipes(self, write_comp_id, pipes):
        db_pipes = [(write_comp_id, pipe_point.output_id, pipe_point['x'], pipe_point['y']) for pipe_point in pipes]
        self.sv_cur.executemany(r"INSERT INTO Pipe VALUES (?, ?, ?, ?)", db_pipes)


    def write_members(self, write_comp_id, members):
        db_members = [(write_comp_id, *member) for member in members]
        self.sv_cur.executemany(r"""INSERT INTO Member
                                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", db_members)

    def write_annotations(self, write_comp_id, annotations):
        db_annotations = [(write_comp_id, annotation["output_id"], annotation["expanded"],
                           annotation["x"], annotation["y"], annotation["annotation"])
                          for annotation in annotations]
        self.sv_cur.executemany(r"""INSERT INTO Annotation
                                    VALUES (?, ?, ?, ?, ?, ?)""", db_annotations)

    def commit(self, name, validate=False):
        pass

    def close(self):
        self.sv_conn.commit()
        self.sv_conn.close()

class ExportWriteBackend(AbstractWriteBackend):
    def __init__(self, id2name, folder) -> None:
        self.f = StringIO()
        self.id2name = id2name
        self.folder = folder

        shutil.rmtree(folder, ignore_errors=True)
        os.mkdir(folder)

    def write_solution(self, db_level_name, player_name, c, s, r, description, replace_base=None):
        level_name = self.id2name[db_level_name]
        comma_name = ',' + description.strip() if (description and description != 0) else ''
        print(f"SOLUTION:{level_name},{player_name},{c}-{r}-{s}{comma_name}",
              file=self.f)

    def write_component(self, write_level_id, component):
        print("COMPONENT:'{0}',{1},{2},''".format(component["type"], component["x"], component["y"]),
              file=self.f)

    def write_pipe(self, write_comp_id, out_id, ordered_pipe):
        for pipe_point in ordered_pipe:
            print("PIPE:{},{},{}".format(out_id, pipe_point.x, pipe_point.y),
                  file=self.f)

    def write_pipes(self, write_comp_id, pipes):
        for pipe_point in pipes:
            print("PIPE:{},{},{}".format(pipe_point["output_id"], pipe_point["x"], pipe_point["y"]),
                  file=self.f)

    def write_members(self, write_comp_id, members):
        for member in members:
            print("MEMBER:'{}',{},{},{},{},{},{},{}".format(member["type"], member["arrow_dir"],
                                                            member["choice"], member["layer"],
                                                            member["x"], member["y"],
                                                            member["element_type"], member["element"]),
                  file=self.f)

    def write_annotations(self, write_comp_id, annotations):
        for annotation in annotations:
            annotation_str = annotation["annotation"].replace("\n", "\\n").replace("\r", "\\r")
            print("ANNOTATION:{},{},{},{},'{}'".format(annotation["output_id"], annotation["expanded"],
                                                       annotation["x"], annotation["y"], annotation_str),
                  file=self.f)

    def commit(self, name, validate=False) -> str:
        export = self.f.getvalue()
        if validate:
            try:
                schem.validate(export, verbose=True)
            except Exception as e:
                print(f"{type(e).__name__}: {e}")
                self.f = StringIO()
                return export

        with open(f"{self.folder}/{name}.txt", "a") as f:
            print(export, file=f, end='')

        self.f = StringIO()
        return export

    def close(self):
        pass


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
