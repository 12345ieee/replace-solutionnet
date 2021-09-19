#!/usr/bin/python3

import argparse
import csv
import os
import pathlib
import shutil
import sqlite3

import schem

from db.write_backends import ExportWriteBackend


def main():
    id2name = dict()
    name2id = dict()

    with open('levels.csv') as levels_csv:
        reader = csv.DictReader(levels_csv, skipinitialspace=True)
        for row in reader:
            id2name[row['saveId']] = row['name']
            name2id[row['name']] = row['saveId']

    shutil.rmtree('exports')
    os.mkdir('exports')

    with sqlite3.connect(args.file) as conn:
        conn.row_factory = sqlite3.Row
        # we use cycles != 0 as a good proxy for finished
        if args.levels is None:
            levels = conn.execute("SELECT id, cycles, reactors, symbols, mastered "
                                  "FROM Level "
                                  "WHERE id not like 'custom-%' AND cycles != 0 ")
        else:
            levels = conn.execute(f"SELECT id, cycles, reactors, symbols, mastered "
                                  f"FROM Level "
                                  f"WHERE id in ({','.join('?' * len(args.levels))}) AND cycles != 0 ",
                                  [name2id[lev] for lev in args.levels])

        for level in levels:
            # CE extra sols are stored as `id!progressive`
            clean_id = level['id'].split('!')[0]
            export = read_solution(clean_id, conn, level, id2name)

            if args.schem:
                try:
                    schem.validate(export, verbose=True)
                except Exception as e:
                    print(f"{type(e).__name__}: {e}")
                    continue

            with open(f"exports/{clean_id}.txt", "a") as f:
                print(export, file=f, end='')


def read_solution(clean_id, conn, level, save2name) -> str:
    write_backend = ExportWriteBackend(args.player_name, save2name)
    write_backend.write_solution(clean_id, level[1:4], level['mastered'])

    components = conn.execute("SELECT rowid,type,x,y,name "
                              "FROM component "
                              "WHERE level_id=? "
                              "ORDER BY rowid",
                              (level["id"],))
    for component in components:
        write_backend.write_component(None, component)

        members = conn.execute("SELECT type,arrow_dir,choice,layer,x,y,element_type,element "
                               "FROM Member "
                               "WHERE component_id=? "
                               "ORDER BY rowid",
                               (component["rowid"],))
        write_backend.write_members(None, members)

        pipes = conn.execute("SELECT output_id,x,y "
                             "FROM Pipe "
                             "WHERE component_id=? "
                             "ORDER BY rowid",
                             (component["rowid"],))
        write_backend.write_pipes(None, pipes)

        annotations = conn.execute("SELECT output_id,expanded,x,y,annotation "
                                   "FROM Annotation "
                                   "WHERE component_id=?",
                                   (component["rowid"],))
        write_backend.write_annotations(None, annotations)

    return write_backend.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=pathlib.Path, nargs="?", default="saves/12345ieee/000.user")
    parser.add_argument("-n", "--player-name", default="12345ieee")
    parser.add_argument("-l", "--levels", nargs='+')
    parser.add_argument("-s", "--schem", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    main()
