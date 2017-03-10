### How to run this thing

You need:

* A python3 interpreter
* The `natsort` PyPi package: `pip3 install natsort`

Parsing your save(s), too:

* Give your savefile(s) as: `savefiles = ['path/to/save1.user', 'path/to/save2.user', ...]`
* Give your name as `playername = '<name>'`

at the beginning of `worker.py`

Don't parse your save:

* `savefiles = []` at the beginning of `worker.py`

Then just run `./worker` and the table will be printed to stdout

