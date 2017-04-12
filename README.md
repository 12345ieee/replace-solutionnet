### How to run this thing

You need:

* A python3 interpreter

Configuration (at the beginning of `worker.py`):

* Saves: `saves = [{'saveFile': r'path/to/save.user', 'playerName': '<name>', 'playerOS': '<OS>'}]`
* Dump/load: `dumpfile = r'path/to/dumpfile'`
* Wiki: `wikifolder = r'path/to/wiki/folder'`

Runtime options:

    ./parser --help

Then just run `./parser.py` and the table will be printed to stdout

