#!/bin/bash

set -e

function get_scores {
    echo "Writing scores file"
    (cd '..'; ./parser.py --no-wiki -n > db/scores.txt)
}

# Build list files
function build {
    echo "Building file lists"
    
    grep -P '^[^|]+? \| Least Cycles(?: - Windows)? \|'    scores.txt > results/cycles_win.txt
    grep -P '^[^|]+? \| Least Cycles(?: - Linux)? \|'      scores.txt > results/cycles_lin.txt
    grep -P '^[^|]+? \| Least Cycles(?: - Unknown OS)? \|' scores.txt > results/cycles_uos.txt

    grep -P '^[^|]+? \| Least Symbols(?: - Windows)? \|'    scores.txt > results/symbols_win.txt
    grep -P '^[^|]+? \| Least Symbols(?: - Linux)? \|'      scores.txt > results/symbols_lin.txt
    grep -P '^[^|]+? \| Least Symbols(?: - Unknown OS)? \|' scores.txt > results/symbols_uos.txt

    grep -P '^[^|]+? \| Least Cycles(?: - Windows)? - N Reactors \|'    scores.txt > results/cycles_win_reac.txt
    grep -P '^[^|]+? \| Least Cycles(?: - Linux)? - N Reactors \|'      scores.txt > results/cycles_lin_reac.txt
    grep -P '^[^|]+? \| Least Cycles(?: - Unknown OS)? - N Reactors \|' scores.txt > results/cycles_uos_reac.txt

    grep -P '^[^|]+? \| Least Symbols(?: - Windows)? - N Reactors \|'    scores.txt > results/symbols_win_reac.txt
    grep -P '^[^|]+? \| Least Symbols(?: - Linux)? - N Reactors \|'      scores.txt > results/symbols_lin_reac.txt
    grep -P '^[^|]+? \| Least Symbols(?: - Unknown OS)? - N Reactors \|' scores.txt > results/symbols_uos_reac.txt
}

# Transfer solutions
function transfer {
    echo "Filling saves"
    
    rm results/*_reac.user
    for file in results/*.user; do cp $file ${file%.user}_reac.user; done

    for file in results/*.txt; do ./mover.py -s ${file%.txt}.user "$@" $(cut -d'|' -f4 $file | tr -d ' '); done
}

#get_scores
#build
transfer "$@"
