#!/usr/bin/python3

import argparse
import pathlib

from write_backends import ExportWriteBackend, make_level_dicts
from read_backends import SaveReadBackend


def main():
    id2name, name2id = make_level_dicts()

    read_backend = SaveReadBackend(args.file)
    write_backend = ExportWriteBackend('exports', id2name)

    level_ids = [name2id[lev] for lev in args.levels] if args.levels else None
    levels = read_backend.read_solutions(level_ids, pareto_only=False)

    for level in levels:
        # CE extra sols are stored as `id!progressive`
        clean_id = level['id'].split('!')[0]
        write_backend.write_solution(clean_id, args.player_name, level['cycles'],
                                    level['symbols'], level['reactors'], level['mastered'])

        components = read_backend.read_components(level["id"])
        for component in components:
            comp_id = component['rowid']
            write_backend.write_component(component)

            members = read_backend.read_members(comp_id)
            write_backend.write_members(members)

            pipes = read_backend.read_pipes(comp_id)
            write_backend.write_pipes(pipes)

            annotations = read_backend.read_annotations(comp_id)
            write_backend.write_annotations(annotations)

        write_backend.commit(clean_id, args.schem, args.check_precog)
    write_backend.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=pathlib.Path, nargs="?", default="saves/12345ieee/000.user")
    parser.add_argument("-n", "--player-name", default="12345ieee")
    parser.add_argument("-l", "--levels", nargs='+')
    parser.add_argument("-s", "--schem", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--check-precog", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    main()
