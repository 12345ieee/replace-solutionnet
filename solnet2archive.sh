#!/bin/bash
set -e

suffix=${1:=TEST}

function check {
    time python -u ./mover_solnet.py --all -s --check -e exports_checked${suffix} |& tee log${suffix}.log
}

function pareto {
    # TODO: this collapses same-name levels to one
    ./mover_solnet.py -e exports_temp${suffix} --read-from-folder exports_checked${suffix} --pareto
    mkdir exports_pareto${suffix}
    find exports_temp${suffix} -name '*.txt' -execdir cp ../exports_checked${suffix}/{} ../exports_pareto${suffix} \;
}

pareto