#!/bin/bash

if [ "$1" = "" ]
then
	echo "You must enter the name of the savefile."
	exit 1
fi

table="Level"

sqlite3 -header -csv $1 "SELECT * FROM ${table};" > save.csv
