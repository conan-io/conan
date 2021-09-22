import os
import unittest

from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import RemoteRegistry, Remote, Remotes
from conans.errors import ConanException
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import redirect_output
from conans.util.files import save


class RegistryTest(unittest.TestCase):

    def test_add_remove_update(self):
        f = os.path.join(temp_folder(), "aux_file")
        Remotes().save(f)
        cache = ClientCache(os.path.dirname(f))
        registry = cache.registry

        # Add
        registry.add("local", "http://localhost:9300")
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False)])
        # Add
        registry.add("new", "new_url", False)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False),
                          ("new", "new_url", False, False)])
        with self.assertRaises(ConanException):
            registry.add("new", "new_url")
        # Update
        registry.update("new", "other_url")
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False),
                          ("new", "other_url", True, False)])
        with self.assertRaises(ConanException):
            registry.update("new2", "new_url")

        registry.update("new", "other_url", False)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False),
                          ("new", "other_url", False, False)])

        # Remove
        registry.remove("local")
        self.assertEqual(list(registry.load_remotes().values()),
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
        registry.add("repo1", "url1", True, insert=0)
        self.assertEqual(list(registry.load_remotes().values()), [Remote("repo1", "url1", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False)])
        registry.add("repo2", "url2", True, insert=1)
        self.assertEqual(list(registry.load_remotes().values()), [Remote("repo1", "url1", True, False),
                         Remote("repo2", "url2", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False)])
        registry.add("repo3", "url3", True, insert=5)
        self.assertEqual(list(registry.load_remotes().values()), [Remote("repo1", "url1", True, False),
                         Remote("repo2", "url2", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False),
                         Remote("repo3", "url3", True, False)])

    def test_remote_none(self):
        """ RemoteRegistry should be able to deal when the URL is None
        """
        f = os.path.join(temp_folder(), "add_none_test")
        Remotes().save(f)
        cache = ClientCache(os.path.dirname(f))
        registry = cache.registry
        output = RedirectedTestOutput()
        with redirect_output(output):
            registry.add("foobar", None)
            self.assertEqual(list(registry.load_remotes().values()),
                             [("conancenter", "https://center.conan.io", True, False),
                              ("foobar", None, True, False)])
            self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", output)
            registry.remove("foobar")

        output = RedirectedTestOutput()
        with redirect_output(output):
            registry.update("conancenter", None)
            self.assertEqual(list(registry.load_remotes().values()),
                             [("conancenter", None, True, False)])
            self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", output)

    def test_enable_disable_remotes(self):
        f = os.path.join(temp_folder(), "aux_file")
        Remotes().save(f)
        cache = ClientCache(os.path.dirname(f))
        registry = cache.registry

        registry.add("local", "http://localhost:9300")
        registry.set_disabled_state("local", True)
        self.assertEqual(list(registry.load_remotes().all_values()),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, True)])

        self.assertEqual(list(registry.load_remotes().values()),
                         [("conancenter", "https://center.conan.io", True, False)])

        registry.set_disabled_state("conancenter", True)
        self.assertEqual(list(registry.load_remotes().all_values()),
                         [("conancenter", "https://center.conan.io", True, True),
                          ("local", "http://localhost:9300", True, True)])

        self.assertEqual(list(registry.load_remotes().values()), [])

        registry.set_disabled_state("*", False)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conancenter", "https://center.conan.io", True, False),
                          ("local", "http://localhost:9300", True, False)])

        registry.set_disabled_state("*", True)
        self.assertEqual(list(registry.load_remotes().values()), [])
