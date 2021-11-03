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
        self.assertEqual(registry.list()[0].name, "conancenter")
        self.assertEqual(registry.list()[1].name, "local")
        self.assertEqual(registry.list()[1].url, "http://localhost:9300")
        self.assertEqual(registry.list()[1].verify_ssl, True)
        self.assertEqual(registry.list()[1].disabled, False)

        # Add
        registry.add(Remote("new", "new_url", False))
        self.assertEqual(registry.list()[0].name, "conancenter")
        self.assertEqual(registry.list()[2].name, "new")
        self.assertEqual(registry.list()[2].url, "new_url")
        self.assertEqual(registry.list()[2].verify_ssl, False)
        self.assertEqual(registry.list()[2].disabled, False)

        with self.assertRaises(ConanException):
            r = Remote("new", "new_url")
            registry.add(r)
        # Update
        r = Remote("new", "other_url")
        registry.update(r)
        self.assertEqual(registry.list()[0].name, "conancenter")
        self.assertEqual(registry.list()[2].url, "other_url")
        self.assertEqual(registry.list()[2].verify_ssl, True)
        self.assertEqual(registry.list()[2].disabled, False)

        with self.assertRaises(ConanException):
            r = Remote("new2", "new_url")
            registry.update(r)

        r = Remote("new", "other_url", False)
        registry.update(r)
        self.assertEqual(registry.list()[0].name, "conancenter")
        self.assertEqual(registry.list()[2].url, "other_url")
        self.assertEqual(registry.list()[2].verify_ssl, False)
        self.assertEqual(registry.list()[2].disabled, False)

        # Remove
        registry.remove("local")
        self.assertEqual(registry.list()[0].name, "conancenter")
        self.assertEqual(registry.list()[1].name, "new")
        self.assertEqual(len(registry.list()), 2)

        with self.assertRaises(ConanException):
            registry.remove("new2")

        self.assertEqual(len(registry.list()), 2)

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
        repo = Remote("repo2", "url2", True)
        registry.add(repo)
        registry.move(repo, 1)
        self.assertEqual(registry.list(), [Remote("repo1", "url1", True, False),
                         Remote("repo2", "url2", True, False),
                         Remote("conan.io", "https://server.conan.io", True, False)])
        repo = Remote("repo3", "url3", True)
        registry.add(repo)
        registry.move(repo, 5)
        self.assertEqual(registry.list(),
                         [Remote("repo1", "url1", True, False),
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
            registry.add(Remote("foobar", None))
            self.assertEqual(registry.list(),
                             [Remote("conancenter", "https://center.conan.io"),
                              Remote("foobar", None)])
            self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", output)
            registry.remove("foobar")
            output.clear()
            registry.update(Remote("conancenter", None))
            self.assertEqual(registry.list(),
                             [Remote("conancenter", None)])
            self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", output)

    def test_enable_disable_remotes(self):
        f = os.path.join(temp_folder(), "aux_file")
        cache = ClientCache(os.path.dirname(f))
        registry = cache.remotes_registry

        local_expected = Remote("local", "http://localhost:9300")
        registry.add(local_expected)
        local_expected.disabled = True
        registry.update(local_expected)
        conan_center_expected = Remote("conancenter", "https://center.conan.io", True)
        conan_center_expected.disabled = False

        self.assertEqual(registry.list(), [conan_center_expected, local_expected])

        cc = registry.read("conancenter")
        cc.disabled = True
        registry.update(cc)
        self.assertEqual(registry.list()[0].disabled, True)
        registry.remove(cc.name)
        registry.remove(local_expected.name)
        self.assertEqual(list(registry.list()), [])
