import os
import unittest

from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import RemoteRegistry, Remote
from conans.errors import ConanException
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import redirect_output
from conans.util.files import save


class RegistryTest(unittest.TestCase):

    def test_add_remove_update(self):
        f = os.path.join(temp_folder(), "aux_file")
        cache = ClientCache(os.path.dirname(f))
        registry = cache.remotes_registry

        # Add
        registry.add(Remote("local", "http://localhost:9300"))
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False)])
        # Add
        registry.add(Remote("new", "new_url", False))
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False),
                          ("new", "new_url", False, False)])
        with self.assertRaises(ConanException):
            r = Remote("new", "new_url")
            registry.add(r)
        # Update
        r = Remote("new", "other_url")
        registry.update(r)
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False),
                          ("new", "other_url", True, False)])
        with self.assertRaises(ConanException):
            r = Remote("new2", "new_url")
            registry.update(r)

        r = Remote("new", "other_url", False)
        registry.update(r)
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False),
                          ("new", "other_url", False, False)])

        # Remove
        registry.remove("local")
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("new", "other_url", False, False)])
        with self.assertRaises(ConanException):
            registry.remove("new2")

    def test_insert(self):
        tmp_folder = temp_folder()
        f = os.path.join(tmp_folder, "remotes.json")
        save(f, """
{
 "remotes": [
  {
   "url": "https://server.conan.io",
   "verify_ssl": true,
   "name": "conan.io"
  }
 ]
}
""")
        cache = ClientCache(tmp_folder)
        registry = RemoteRegistry(cache)
        r = Remote("repo1", "url1", True)
        registry.add(r)
        registry.move(r, 0)
        self.assertEqual(registry.list(), [Remote("repo1", "url1", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False)])
        registry.add("repo2", "url2", True, insert=1)
        self.assertEqual(registry.list(), [Remote("repo1", "url1", True, False),
                         Remote("repo2", "url2", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False)])
        registry.add("repo3", "url3", True, insert=5)
        self.assertEqual(registry.list(), [Remote("repo1", "url1", True, False),
                         Remote("repo2", "url2", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False),
                         Remote("repo3", "url3", True, False)])

    def test_remote_none(self):
        """ RemoteRegistry should be able to deal when the URL is None
        """
        output = RedirectedTestOutput()
        with redirect_output(output):
            f = os.path.join(temp_folder(), "add_none_test")
            cache = ClientCache(os.path.dirname(f))
            registry = cache.remotes_registry
            registry.add("foobar", None)
            self.assertEqual(registry.list(),
                             [("conancenter", "https://center.conan.io", True, False),
                              ("foobar", None, True, False)])
            self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", output)
            registry.remove("foobar")
            output.clear()
            registry.update("conancenter", None)
            self.assertEqual(registry.list(),
                             [("conancenter", None, True, False)])
            self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", output)

    def test_enable_disable_remotes(self):
        f = os.path.join(temp_folder(), "aux_file")
        cache = ClientCache(os.path.dirname(f))
        registry = cache.remotes_registry

        registry.add("local", "http://localhost:9300")
        registry.set_disabled_state("local", True)
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, True)])

        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False)])

        registry.set_disabled_state("conancenter", True)
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, True),
                          ("local", "http://localhost:9300", True, True)])

        self.assertEqual(list(registry.load_remotes().values()), [])

        registry.set_disabled_state("*", False)
        self.assertEqual(registry.list(),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False)])

        registry.set_disabled_state("*", True)
        self.assertEqual(list(registry.load_remotes().values()), [])
