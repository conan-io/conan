import os
import tempfile
import time
from multiprocessing import Process
from string import ascii_lowercase

import fasteners

tmpf = os.path.join(tempfile.gettempdir(), "conan_test", "filelocks")
datafile = os.path.join(tmpf, "data.txt")
lock = os.path.join(tmpf, "data.txt.lock")


def _mywriter():
    for c in ascii_lowercase:
        with fasteners.InterProcessLock(lock):
            open(datafile, "w").write(c * 50)
            for _ in range(4):
                time.sleep(0.1)  # slow writes to cause race conditions
                open(datafile, "a").write(c * 50)
        time.sleep(0.1)


def _myreader():
    while True:
        with fasteners.InterProcessLock(lock):
            contents = open(datafile, "r").read()
            d = contents[0]
            assert contents == d * 250, f"{len(contents)}: {contents}"
            if d == "z":
                break
        time.sleep(0.01)


def test_simple_mutex():
    os.makedirs(os.path.dirname(datafile), exist_ok=True)
    open(datafile, "w+").write("a" * 250)

    pread = Process(target=_myreader)
    pread.start()
    pwrite = Process(target=_mywriter)
    pwrite.start()

    pread.join()
    if pread.exitcode:
        pwrite.terminate()
        raise Exception("pread failed")
    pwrite.join()
