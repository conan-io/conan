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

    def install_recipe(self, cache: Cache, ref: ConanFileReference,
                       writing_to_cache: threading.Event, writing_release: threading.Event):
        # Basically, installing a reference is about getting a write lock on the recipe_layout, but
        # some other threads might be using (writing) the same resource
        recipe_layout, _ = cache.get_or_create_reference_layout(ref)
        try:
            self.log('Request lock for recipe')
            with try_write_else_read_wait(recipe_layout) as writer:
                if writer:
                    self.log('WRITE lock: write files to the corresponding folder')
                    writing_to_cache.set()
                    writing_release.wait(timeout=1)
                    self.log('WRITE lock: released')
                else:
                    self.log('READER lock: Check files are there and use them')

            self.log('Done with the job')
        except Exception as e:
            self.log(f'ERROR: {e}')
        except sqlite3.OperationalError as e:
            self.log(f'ERROR (sqlite3) {e}')


def test_concurrent_install(cache_1level: Cache):
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
                          args=(cache_1level, ref, writing_to_cache, writing_release,))

    # Second thread arrives later
    t2 = threading.Thread(target=conan_ops.install_recipe,
                          args=(cache_1level, ref, writing_to_cache, writing_release,))

    t1.start()
    writing_to_cache.wait(timeout=1)  # Wait for t1 to start writing to cache
    t2.start()
    time.sleep(1)  # Ensure t2 is waiting to write/read

    writing_release.set()
    t1.join(timeout=1)
    t2.join(timeout=1)

    output = '\n'.join(list(conan_ops.q.queue))
    assert output == textwrap.dedent(f'''\
        {t1.name} > Request lock for recipe
        {t1.name} > WRITE lock: write files to the corresponding folder
        {t2.name} > Request lock for recipe
        {t1.name} > WRITE lock: released
        {t1.name} > Done with the job
        {t2.name} > READER lock: Check files are there and use them
        {t2.name} > Done with the job''')
