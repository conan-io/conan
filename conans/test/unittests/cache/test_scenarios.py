from conan.cache.cache import Cache
import threading  # Using threading we can implements the test with memory databases

from conans.model.ref import ConanFileReference


def test_concurrent_install(cache_memory: Cache):
    """ When installing/downloading from a remote server, we already know the final revision,
        but still two processes can be running in parallel. The second process doesn't want to
        download **again** if the first one already put the files in place
    """
    ref = ConanFileReference.loads('name/version#111111111')

    def install_thread():
        # Basically, installing a reference is about getting a write lock on the recipe_layout
        recipe_layout = cache_memory.get_reference_layout(ref)
        with recipe_layout.lock(blocking=True, wait=False):
            pass

    t1 = threading.Thread(target=install_thread,
                          args=())
    t1.start()
    t1.join()





