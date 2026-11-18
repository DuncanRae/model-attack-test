"""Model Attack Test: sends known tricks to an AI chat system you own and reports which ones it gave way to.

Standard library only, Python 3.9 or newer. `run.run_suite` is the one door for anything that wants to use this as a
library (a pipeline, or a page in another tool): the command line in `cli.py` is a thin layer over it.
"""

VERSION = "0.5.0"


class Problem(Exception):
    """Something the person running the tool can put right. The message is plain and safe to show as it is."""
