#!/bin/bash
set -e

function init {
    sudo apt install postgresql
    sudo -u postgres createuser -s $(whoami)
    createdb -T template0 solutionnet
    psql solutionnet < solutionnet_cleaned_dump.sql
}

# Transfer solutions
function transfer {
    echo "Filling save"

    cp data/{new,solnet}.user
    ./mover.py -s data/solnet.user --no-replace-sols --all
}

transfer
