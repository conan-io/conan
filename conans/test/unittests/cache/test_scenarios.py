import queue
import sqlite3
import textwrap
import threading  # Using threading we can implements the test with memory databases
import time

from conan.cache.cache import Cache
from conan.locks.utils import try_write_else_read_wait
from conans.model.ref import ConanFileReference


class ConanOps:
    def __init__(self):
        self.q = queue.Queue()

    def log(self, msg: str):
        self.q.put(f'{threading.current_thread().name} > {msg}')

    def install_recipe(self, cache, ref, writing_to_cache: threading.Event,
                       writing_release: threading.Event):
        # Basically, installing a reference is about getting a write lock on the recipe_layout, but
        # some other threads might be using (writing) the same resource
        recipe_layout = cache.get_reference_layout(ref)
        try:
            self.log('Request lock for recipe')
            with try_write_else_read_wait(recipe_layout) as writer:
                if writer:
                    self.log('WRITE lock: write files to the corresponding folder')
                    writing_to_cache.set()
                    writing_release.wait()
                    self.log('WRITE lock: released')
                else:
                    self.log('READER lock: Check files are there and use them')

            self.log('Done with the job')
            # with inside_done:
            #    inside_done.notify_all()
        except Exception as e:
            self.log(f'ERROR: {e}')
        except sqlite3.OperationalError as e:
            self.log(f'ERROR (sqlite3) {e}')


def test_concurrent_install(cache_memory: Cache):
    """ When installing/downloading from a remote server, we already know the final revision,
        but still two processes can be running in parallel. The second process doesn't want to
        download **again** if the first one already put the files in place
    """
    ref = ConanFileReference.loads('name/version#111111111')
    writing_to_cache = threading.Event()
    writing_release = threading.Event()

    conan_ops = ConanOps()
    # First thread acquires the lock and starts to write to the cache folder
    t1 = threading.Thread(target=conan_ops.install_recipe,
                          args=(cache_memory, ref, writing_to_cache, writing_release,))

    # Second thread arrives later
    t2 = threading.Thread(target=conan_ops.install_recipe,
                          args=(cache_memory, ref, writing_to_cache, writing_release,))

    t1.start()
    writing_to_cache.wait()  # Wait for t1 to start writing to cache
    t2.start()
    time.sleep(1)  # Ensure t2 is waiting to write/read

    writing_release.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    output = '\n'.join(list(conan_ops.q.queue))
    assert output == textwrap.dedent(f'''\
        Thread-1 > Request lock for recipe
        Thread-1 > WRITE lock: write files to the corresponding folder
        Thread-2 > Request lock for recipe
        Thread-1 > WRITE lock: released
        Thread-1 > Done with the job
        Thread-2 > READER lock: Check files are there and use them
        Thread-2 > Done with the job''')
