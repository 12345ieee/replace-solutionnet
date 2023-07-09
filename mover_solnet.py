#!/usr/bin/env python3

import argparse

from read_backends import ExportReadBackend, SolnetReadBackend
from write_backends import ExportWriteBackend, NoopWriteBackend, SaveWriteBackend, make_level_dicts


def main():
    if args.read_from_folder or args.export_folder:
        id2name, name2id = make_level_dicts()
    else:
        id2name, name2id = None, None

    if args.read_from_folder:
        read_backend = ExportReadBackend(args.read_from_folder, name2id)
    else:
        read_backend = SolnetReadBackend()

    if args.file_save:
        write_backend = SaveWriteBackend(args.file_save)
    elif args.export_folder:
        write_backend = ExportWriteBackend(args.export_folder, id2name)
    else:
        write_backend = NoopWriteBackend()

    solutions = read_backend.read_solutions(args.sol_ids or args.levels, args.pareto_only)
    for solution in solutions:
        sol_id, db_level_name, player_name, comment, c, s, r = solution
        print(f'Loading solution {sol_id}')
        write_backend.write_solution(db_level_name, player_name, c, s, r, comment, args.replace_sols)

        reactors = read_backend.read_components(sol_id)
        for reactor in reactors:
            comp_id = reactor['component_id']
            write_backend.write_component(reactor)

            members = read_backend.read_members(comp_id)
            write_backend.write_members(members)

            pipes = read_backend.read_pipes(comp_id, reactor['type'])
            write_backend.write_pipes(pipes)

        write_backend.commit(db_level_name if args.group_exports_by_level else sol_id, args.schem, args.check_precog)

    write_backend.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file-save", nargs="?", const=r'data/solnet.user')
    parser.add_argument("-e", "--export-folder", nargs="?", const=r'exports')
    gr_in = parser.add_mutually_exclusive_group()
    gr_in.add_argument("sol_ids", nargs='*', type=int, default=[])
    gr_in.add_argument("-l", "--levels", nargs='+')
    parser.add_argument("--replace-sols", default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument("--group-exports-by-level", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--pareto-only", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--read-from-folder", nargs="?", const=r'exports')
    parser.add_argument("-s", "--schem", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--check-precog", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    main()
