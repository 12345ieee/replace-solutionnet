#!/usr/bin/env python3

import sqlite3
from abc import ABC, abstractmethod
from io import StringIO


class AbstractWriteBackend(ABC):

    @abstractmethod
    def write_solution(self, db_level_name, score, description, replace_base) -> str:
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
    def close(self):
        pass

class SaveWriteBackend(AbstractWriteBackend):
    def __init__(self, savefile) -> None:
        self.sv_conn = sqlite3.connect(savefile)
        self.sv_cur = self.sv_conn.cursor()

    def write_solution(self, db_level_name, score, description, replace_base=True) -> str:

        if replace_base:
            # delete base sol
            self.delete_solution(db_level_name)
            print(f'Adding base solution to {db_level_name}')

            db_level_id = db_level_name
            self.sv_cur.execute(r"""INSERT INTO Level
                                    VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?)""",
                                    [db_level_id, *score, *score])
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
                                    [db_level_id, description or 'Unnamed Solution', *score])
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
        db_pipes = [(write_comp_id, pipe_point.output_id, pipe_point.x, pipe_point.y) for pipe_point in pipes]
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

    def close(self):
        self.sv_conn.commit()
        self.sv_conn.close()

class ExportWriteBackend(AbstractWriteBackend):
    def __init__(self, player_name, save2name) -> None:
        self.f = StringIO()
        self.player_name = player_name
        self.save2name = save2name

    def write_solution(self, db_level_name, score, description, replace_base=None):
        level_name = self.save2name[db_level_name]
        comma_name = ',' + description if description != 0 else ''
        print(f"SOLUTION:{level_name},{self.player_name},{'-'.join(map(str, score))}{comma_name}",
              file=self.f)

    def write_component(self, write_level_id, component):
        print("COMPONENT:'{0}',{1},{2},''".format(component["type"], component["x"], component["y"]),
              file=self.f)

    def write_pipe(self, write_comp_id, out_id, ordered_pipe):
        for pipe_point in ordered_pipe:
            print("PIPE:{},{},{}".format(out_id, pipe_point["x"], pipe_point["y"]),
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

    def close(self) -> str:
        return self.f.getvalue()
