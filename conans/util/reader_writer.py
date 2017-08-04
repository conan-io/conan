import fasteners
from conans.util.log import logger
from conans.util.files import load, save
from conans.test.utils.test_files import temp_folder
import time
import os


class Lock(object):

    def __init__(self, folder, index):
        self._index = index
        self._folder = folder
        self._lock = None
        self._count_file = folder + ".count"
        self._count_lock_file = folder + ".count.lock"
        self._lock_file = folder + ".lock"

    def _readers(self):
        try:
            return int(load(self._count_file))
        except IOError:
            return 0


class ReadLock(Lock):

    def _acquire(self):
        self._lock = fasteners.InterProcessLock(self._lock_file, logger=logger)
        if not self._lock.acquire():
            raise Exception("ReadLock Acquire failed")

    def __enter__(self):
        print "** ReadLock enter %s **" % self._index
        while True:
            print "Try to get the ReadLOck over count lock file"
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                readers = self._readers()
                if readers == 0:
                    print "ReadLock.__enter__ %s: No readers, let get the lock and read" % self._index
                    self._lock = fasteners.InterProcessLock(self._lock_file, logger=logger)
                    if not self._lock.acquire(timeout=1):
                        print "ACQUISITION OF LOCK FOR READ FAILED"
                        time.sleep(0.1)
                        continue
                    print "ReadLock.__enter__ %s: Lock acquired for read!! " % self._index
                    save(self._count_file, "1")
                    return
                elif readers > 0:
                    print "ReadLock.__enter__ %s: There are readers, lets increment the count" % self._index
                    save(self._count_file, str(readers + 1))
                    return
                else:
                    print "NUM READERS ", readers
                    break

        if readers == -1:  # writer is writing
            print "Writer is writing, read_lock should wait"
            self._acquire()  # should block and wait
            print "ReadLock acquired it after Writer finished, try to increment readers"
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                readers = self._readers()
                print "After writer released, reader incrementing to ", readers + 1
                save(self._count_file, str(readers + 1))

    def __exit__(self, exc_type, exc_val, exc_tb):
        print "** ReadLock exit %s **" % self._index
        with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
            print "Lets decrement from read_unlock"
            readers = self._readers()
            print "Lets decrement from read_unlock ", readers
            if readers == 1 and self._lock:
                print "Lets try to release read lock "
                self._lock.release()
            save(self._count_file, str(readers - 1))


class WriteLock(Lock):

    def _acquire(self):
        self._lock = fasteners.InterProcessLock(self._lock_file, logger=logger)
        if not self._lock.acquire():
            raise Exception("WriteLock Acquire failed")

    def __enter__(self):
        print "** WriteLock enter %s **" % self._index
        while True:
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                readers = self._readers()
                if readers == 0:
                    print "WriteLock.__enter__ %s: No readers, let get the lock and write" % self._index
                    self._lock = fasteners.InterProcessLock(self._lock_file, logger=logger)
                    if not self._lock.acquire(timeout=1):
                        print "ACQUISITION OF LOCK FOR WRITE FAILED"
                        time.sleep(0.1)
                        continue
                    save(self._count_file, "-1")
                    return
                else:
                    print "NUM READERS WRITERS ", readers
                    break

        if readers != 0:
            self._acquire()
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                save(self._count_file, "-1")

    def __exit__(self, exc_type, exc_val, exc_tb):
        print "** WriteLock exit %s **" % self._index
        with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
            print "WriteLock.__exit__ %s: Release from write_unlock" % self._index
            self._lock.release()
            save(self._count_file, "0")

length_str = 10000


def reader(folder):
    for i in range(100):
        with ReadLock(folder, i):
            print "+++ Loading file ", i
            try:
                content = load(os.path.join(folder, "myfile.txt"))
            except Exception as e:
                print "NO file yet ", str(e)
            else:
                assert len(content) == length_str, "Length is %s: %s" % (len(content), content)
                assert content == len(content) * content[0]
                print "Read consistent file of ", content[0]
        time.sleep(0.100)


def writer(folder):
    for i in range(100):
        with WriteLock(folder, i):
            print "+++ Saving file ", i
            save(os.path.join(folder, "myfile.txt"), str(i%10) * length_str)
        time.sleep(0.100)


if __name__ == "__main__":
    folder = temp_folder()
    from multiprocessing.process import Process
    p = Process(target=reader, kwargs={"folder": folder})
    p.start()
    p2 = Process(target=reader, kwargs={"folder": folder})
    p2.start()
    p3 = Process(target=writer, kwargs={"folder": folder})
    p3.start()

    p.join()
    p2.join()
    p3.join()
