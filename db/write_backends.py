#!/usr/bin/env python3

from abc import ABC, abstractmethod
import sqlite3

class AbstractWriteBackend(ABC):

    @abstractmethod
    def write_solution(self, solution, replace_base) -> str:
        pass

    @abstractmethod
    def write_component(self, write_level_id, component) -> int:
        pass

    @abstractmethod
    def write_pipe(self, write_comp_id, out_id, ordered_pipe):
        pass

    @abstractmethod
    def write_members(self, write_comp_id, members):
        pass

    @abstractmethod
    def close(self):
        pass

class SaveWriteBackend(AbstractWriteBackend):
    def __init__(self, savefile) -> None:
        self.sv_conn = sqlite3.connect(savefile)
        self.sv_cur = self.sv_conn.cursor()

    def write_solution(self, solution, replace_base=True) -> str:
        db_level_name, comment, *triplet = solution

        if replace_base:
            # delete base sol
            self.delete_solution(db_level_name)
            print(f'Adding base solution to {db_level_name}')

            db_level_id = db_level_name
            self.sv_cur.execute(r"""INSERT INTO Level
                                    VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?)""",
                                    [db_level_id, *triplet, *triplet])
        else:
            # find the largest CE sol used
            self.sv_cur.execute(r"""SELECT MAX(CAST(SUBSTR(id, INSTR(id, '!') + 1) AS int))
                                    FROM Level
                                    WHERE id like ?""", (db_level_name + '%',))
            target = str((self.sv_cur.fetchone()[0] or 0) + 1)
            print(f'Adding solution {target} to {db_level_name}')

            db_level_id = db_level_name + '!' + target
            self.sv_cur.execute(r"""INSERT INTO Level
                                    VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?)""",
                                    [db_level_id, comment, *triplet, 0, 0, 0])
        return db_level_id

    def delete_solution(self, db_level_id):
        # delete everything (Component, Member, Annotation, Pipe, UndoPtr, Undo) about the old solution
        self.sv_cur.execute(r'SELECT rowid FROM Component WHERE level_id = ?', (db_level_id,))
        comp_ids = [row[0] for row in self.sv_cur.fetchall()]
        if not comp_ids:
            # no solution to delete
            return
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

    def write_members(self, write_comp_id, members):
        db_members = [(write_comp_id, *member) for member in members]
        self.sv_cur.executemany(r"""INSERT INTO Member
                                VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", db_members)

    def close(self):
        self.sv_conn.commit()
        self.sv_conn.close()
