### How to run this thing

You need:

* A python3 interpreter

Parsing your save(s), too:

* `saves = [{'saveFile': r'path/to/save.user', 'playerName': '<name>', 'playerOS': '<OS>'}]` at the beginning of `worker.py`

at the beginning of `worker.py`

Don't parse your save:

* `saves = []` at the beginning of `worker.py`

Then just run `./worker` and the table will be printed to stdout

