#!/bin/bash
set -e

function init {
    sudo apt install postgresql
    sudo -u postgres createuser -s "$(whoami)"
    createdb -T template0 solutionnet
    psql solutionnet < data/solutionnet_cleaned_dump.sql
}

# Transfer solutions
function transfer {
    echo "Filling save"

    cp data/{new,solnet}.user
    ./solnet_mover.py -s data/solnet.user --no-replace-sols --all
}

transfer
