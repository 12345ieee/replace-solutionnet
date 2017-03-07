### How to run this thing

You need:

* A python3 interpreter
* The `natsort` PyPi package: `pip3 install natsort`

Parsing your save, too:

* Pre-parse your savefile via: `./dump_save.sh path/to/save/.../something.user`
* Give your name as `playername = '<name>'` at the beginning of `worker.py`

Don't parse your save:

* Comment out the 2nd `with` block, not elegant but it works.

Then just run `./worker` and the table will be printed to stdout

