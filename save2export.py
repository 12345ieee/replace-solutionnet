#!/usr/bin/python3

import argparse
import pathlib
import sqlite3

from write_backends import ExportWriteBackend, make_level_dicts


def main():
    id2name, name2id = make_level_dicts()

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

        write_backend = ExportWriteBackend(id2name, 'exports')

        for level in levels:
            # CE extra sols are stored as `id!progressive`
            clean_id = level['id'].split('!')[0]
            write_backend.write_solution(clean_id, args.player_name, level['cycles'],
                                         level['symbols'], level['reactors'], level['mastered'])
            read_solution(conn, level, write_backend)
            write_backend.commit(clean_id, args.schem)
        write_backend.close()


def read_solution(conn, level, write_backend):
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=pathlib.Path, nargs="?", default="saves/12345ieee/000.user")
    parser.add_argument("-n", "--player-name", default="12345ieee")
    parser.add_argument("-l", "--levels", nargs='+')
    parser.add_argument("-s", "--schem", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    main()
