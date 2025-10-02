"""
Minimal shim for Python 3.13 where stdlib aifc was removed.
This only satisfies import-time references from libraries that don't actually
use AIFF functionality at runtime. Any actual use will raise NotImplementedError.
"""

class Error(Exception):
    pass

def open(file, mode='r'):
    raise NotImplementedError("aifc module is unavailable on Python 3.13; AIFF handling not supported in this environment.")


